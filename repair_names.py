# SPDX-License-Identifier: MIT
"""Rename registered unnamed WAVs using known events, without conversion."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from core import Cancelled, Extractor, load_names, slug, validate_saved_audio, resolve_event, event_language
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
    if old == new or old.parent != new.parent or old.suffix != new.suffix:
        raise ValueError('Renombrado pendiente no valido.')
    if old.exists():
        if new.exists() or digest(old) != pending['sha256']:
            raise ValueError('Conflicto en renombrado pendiente; no se sobrescribe.')
        old.rename(new)
    elif not new.is_file() or digest(new) != pending['sha256']:
        raise ValueError('No se puede recuperar el renombrado pendiente.')
    row.setdefault('previous_names', []).append(pending['old'])
    row['wav'] = pending['new']
    row['events'] = pending['events']
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
    summary = dict(renamed=0, planned=0, unknown=0, already_named=0)
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
            if not old.name.startswith('sin_evento__') or row.get('events'):
                summary['already_named'] += 1
                continue
            language, names = resolve_event(events, package, row['media_id'],
                                            Path(row.get('media_source', '')).parent, source.parent)
            if not names:
                summary['unknown'] += 1
                continue
            validate_saved_audio(old, row)
            name = slug(re.sub(r'\{[^}]*\}', '', names.split(' | ')[0]))
            suffix = '__' + slug(event_language(language, names))[:16] + '__' + slug(row['media_id'])[:24]
            room = min(80, 245 - len(str(old.parent)) - 1 - len(suffix) - len('_9999999.wav'))
            if room < 1:
                raise ValueError('Destino demasiado largo para renombrar.')
            stem = name[:room] + suffix
            dest = old.with_name(stem + old.suffix)
            number = 1
            while dest.exists() or dest in reserved:
                number += 1
                dest = old.with_name(stem + f'_{number}' + old.suffix)
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
                                              sha256=digest(old), events=names)
                Extractor.save_report(marker, report)
                finish_pending(output, marker, report)
                summary['renamed'] += 1
    emit(f'Nombres: {summary["renamed"]} actualizados; {summary["unknown"]} sin asociacion en el catalogo.')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--catalog', default='')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    _, events = load_names(catalog_csv=args.catalog)
    print(json.dumps(repair_output(args.output, events, args.apply), indent=2))
