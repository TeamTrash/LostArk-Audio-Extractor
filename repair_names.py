# SPDX-License-Identifier: MIT
"""Rename registered unnamed WAVs using known events, without conversion."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from core import Cancelled, Extractor, load_names, slug, validate_saved_audio, resolve_event, event_language, descriptive_name, pet_family, general_folder, language_folder
from name_decoder import audio_name


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def audio_path(output, relative):
    path = (output / relative).resolve()
    if not path.is_relative_to(output) or path.suffix.lower() not in ('.wav', '.mp3'):
        raise ValueError('Ruta de audio fuera del destino o no valida.')
    return path


def finish_pending(output, marker, report):
    pending = report.get('pending_name')
    if not pending:
        return False
    old = audio_path(output, pending['old'])
    new = audio_path(output, pending['new'])
    row = report['wavs'][pending['index']]
    if row['wav'] != pending['old']:
        raise ValueError('Manifiesto y renombrado pendiente no coinciden.')
    pet_move = bool(pet_family(pending['events'])) and new.parent == old.parent / 'pet'
    language_move = False
    if report.get('folder') and pending.get('audio_folder') in ('es', 'en', 'kr', 'SFX'):
        root = (output / report['folder']).resolve()
        expected = root / pending['audio_folder']
        if pet_family(pending['events']):
            expected = expected / 'pet'
        language_move = (root.parent == output and root.name != '.loa_audio'
                         and old.is_relative_to(root) and new.parent == expected
                         and expected.resolve() == expected)
    if old == new or (old.parent != new.parent and not pet_move and not language_move) or old.suffix != new.suffix:
        raise ValueError('Renombrado pendiente no valido.')
    if old.exists():
        if new.exists() or digest(old) != pending['sha256']:
            raise ValueError('Conflicto en renombrado pendiente; no se sobrescribe.')
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
    elif not new.is_file() or digest(new) != pending['sha256']:
        raise ValueError('No se puede recuperar el renombrado pendiente.')
    row.setdefault('previous_names', []).append(pending['old'])
    row['wav'] = pending['new']
    row['events'] = pending['events']
    if 'descriptive_title' in pending:
        row['descriptive_title'] = pending['descriptive_title']
    row['title_only'] = pending.get('title_only', False)
    del report['pending_name']
    Extractor.save_report(marker, report)
    return True


def repair_output(output, events, apply=False, cancel=None, emit=lambda message: None):
    output = Path(output).resolve()
    metadata = output / '.loa_audio'
    if not metadata.is_dir() or metadata.resolve().parent != output:
        raise ValueError('El destino no contiene metadatos .loa_audio validos.')
    if not events:
        raise ValueError('No hay nombres cargados. Selecciona CATALOGO.csv en Herramientas y nombres.')
    summary = dict(renamed=0, planned=0, unknown=0, already_named=0, missing=0)
    reserved = set()
    for marker in sorted(metadata.glob('*.json')):
        if marker.is_symlink():
            raise ValueError('Manifiesto enlazado no admitido.')
        report = json.loads(marker.read_text(encoding='utf-8'))
        if report.get('schema_version') not in (2, 3):
            continue
        if report.get('pending_name'):
            if not apply:
                raise ValueError('Hay un renombrado pendiente. Reanuda con --apply.')
            summary['renamed'] += int(finish_pending(output, marker, report))
        source = Path(report['input']['source'])
        package = 'loose' if source.suffix.lower() == '.wem' else report.get('decoded_name', audio_name(source))
        for index, row in enumerate(report['wavs']):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            old = audio_path(output, row['wav'])
            if not old.exists():
                summary['missing'] += 1
                emit(f'Archivo ausente; se omite y se conserva su registro: {old}')
                continue
            language, names = resolve_event(events, package, row['media_id'],
                                            Path(row.get('media_source', '')).parent, source.parent)
            effective_names = row.get('events') or names
            target_dir = old.parent
            if report.get('folder'):
                root = (output / report['folder']).resolve()
                if root.parent != output or root.name == '.loa_audio' or not old.is_relative_to(root):
                    raise ValueError('Carpeta de origen del manifiesto no valida.')
                target_dir = root / language_folder(language, effective_names)
                if pet_family(effective_names):
                    target_dir = target_dir / 'pet'
                if target_dir.resolve() != target_dir:
                    raise ValueError('Carpeta de idioma enlazada no admitida.')
            elif pet_family(effective_names) and target_dir.name != 'pet':
                target_dir = target_dir / 'pet'
            relocate = target_dir != old.parent
            preserve_name = False
            unnamed = old.name.startswith('sin_evento__') and not row.get('events')
            if not unnamed:
                prior_events = row.get('events', '')
                _, title = descriptive_name(prior_events, events, 160)
                technical = slug(re.sub(r'\{[^}]*\}', '', prior_events.split(' | ')[0]))
                managed_title = bool(row.get('descriptive_title'))
                if ((not title and not managed_title) or
                        (not managed_title and not old.name.startswith(technical + '__'))):
                    if not relocate:
                        summary['already_named'] += 1
                        continue
                    preserve_name = True
                names = prior_events
            if not names:
                summary['unknown'] += 1
                if not relocate:
                    continue
                preserve_name = True
            validate_saved_audio(old, row)
            name = slug(re.sub(r'\{[^}]*\}', '', names.split(' | ')[0]))
            suffix = '__' + slug(event_language(language, names))[:16] + '__' + slug(row['media_id'])[:24]
            if not target_dir.resolve().is_relative_to(output):
                raise ValueError('Carpeta de categoria fuera del archivo de origen.')
            room = min(160, 245 - len(str(target_dir)) - 1 - len(suffix) - len('_9999999.wav'))
            if room < 1:
                raise ValueError('Destino demasiado largo para renombrar.')
            name, title = descriptive_name(names, events, room)
            title_only = bool(pet_family(names) or (title and getattr(events, 'title_only', False)))
            if (not unnamed and row.get('descriptive_title') == title
                    and bool(row.get('title_only')) == title_only and target_dir == old.parent):
                summary['already_named'] += 1
                continue
            stem = name if title_only else name + suffix
            if preserve_name:
                stem = old.stem
                title = row.get('descriptive_title', '')
                title_only = bool(row.get('title_only'))
            dest = target_dir / (stem + old.suffix)
            if dest == old or (not relocate and not unnamed and not title and not row.get('descriptive_title')):
                summary['already_named'] += 1
                continue
            number = 1
            while dest.exists() or dest in reserved:
                number += 1
                dest = target_dir / (stem + f'_{number}' + old.suffix)
            if len(str(dest)) > 245:
                raise ValueError('Destino demasiado largo para renombrar.')
            reserved.add(dest)
            summary['planned'] += 1
            emit(f'{old.name} -> {dest.name}')
            if apply:
                backup = metadata / 'naming_backups'
                if not backup.resolve().is_relative_to(metadata.resolve()):
                    raise ValueError('Carpeta de respaldos fuera del destino.')
                backup.mkdir(exist_ok=True)
                original = backup / marker.name
                if not original.exists():
                    shutil.copyfile(marker, original)
                # Persist intent before moving; interruption recovery checks the audio hash.
                report['pending_name'] = dict(index=index, old=row['wav'],
                                              new=str(dest.relative_to(output)),
                                              sha256=digest(old), events=names, descriptive_title=title,
                                              title_only=title_only, audio_folder=language_folder(language, names))
                Extractor.save_report(marker, report)
                finish_pending(output, marker, report)
                try:
                    general_folder(dest.parent)
                except OSError as error:
                    emit(f'No se pudo configurar la vista de carpeta: {error}')
                summary['renamed'] += 1
    emit(f'Nombres: {summary["renamed"]} actualizados; {summary["unknown"]} sin asociacion en el catalogo; '
         f'{summary["missing"]} archivos ausentes omitidos.')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--catalog', default='')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    _, events = load_names(catalog_csv=args.catalog)
    print(json.dumps(repair_output(args.output, events, args.apply), indent=2))
