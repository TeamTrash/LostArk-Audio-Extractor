# SPDX-License-Identifier: MIT
"""Local extraction with audio-only package folders and separate job metadata."""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import tempfile
import wave
from pathlib import Path
from collections.abc import Mapping
from name_decoder import audio_name

TOOL_KEYS = ('lautool', 'quickbms', 'script', 'vgmstream', 'ffmpeg')
LOCAL_CATALOG = Path(__file__).resolve().parent / 'data' / 'event_names.local.json'


def general_folder(path):
    """Hint General items for new Windows output folders; preserve existing INI."""
    if os.name != 'nt':
        return
    import ctypes
    ini = Path(path) / 'desktop.ini'
    try:
        # Never replace a user's existing folder customization or follow a link.
        with ini.open('x', encoding='utf-16') as stream:
            stream.write('[ViewState]\nFolderType=Generic\n')
    except FileExistsError:
        return
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
    kernel.GetFileAttributesW.restype = ctypes.c_uint32
    kernel.SetFileAttributesW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.SetFileAttributesW.restype = ctypes.c_int
    for target, flags in ((ini, 6), (Path(path), 1)):
        current = kernel.GetFileAttributesW(str(target))
        if current == 0xFFFFFFFF or not kernel.SetFileAttributesW(str(target), current | flags):
            raise ctypes.WinError(ctypes.get_last_error())


class Cancelled(Exception):
    pass


class EventCatalog(Mapping):
    """Read-only catalog with package/media index; avoids scanning all events per WAV."""
    def __init__(self, events, titles=None, title_only=False):
        self.title_only = title_only
        self._events = dict(events)
        self.titles = titles or {}
        self.by_media = {}
        for (language, package, mid), names in self._events.items():
            if names:
                self.by_media.setdefault((package.casefold(), str(mid)), []).append((language, names))

    def __getitem__(self, key):
        return self._events[key]

    def __iter__(self):
        return iter(self._events)

    def __len__(self):
        return len(self._events)


def detect_language(path):
    aliases = {'korean': 'Korean', 'ko': 'Korean', 'english(us)': 'English(US)',
               'english': 'English(US)', 'en': 'English(US)',
               'spanish(spain)': 'Spanish(Spain)', 'spanish': 'Spanish(Spain)',
               'es': 'Spanish(Spain)', 'sfx': 'SFX'}
    return next((aliases[p.casefold()] for p in reversed(Path(path).parts)
                 if p.casefold() in aliases), None)


def resolve_event(events, package, mid, *paths):
    language = next((lang for p in paths if (lang := detect_language(p))), None)
    if isinstance(events, EventCatalog):
        candidates = [(lang, names) for lang, names in events.by_media.get((package.casefold(), str(mid)), [])
                      if language is None or lang == language]
    else:
        candidates = [(lang, names) for (lang, pkg, media), names in events.items()
                      if pkg.casefold() == package.casefold() and str(media) == str(mid)
                      and names and (language is None or lang == language)]
    # An ID alone is not sufficient: preserve package and reject ambiguous languages.
    if len(candidates) == 1:
        return candidates[0]
    return language or 'SFX', ''


def event_language(language, names):
    # Language comes from the selected media association, never a conflicting name tag.
    short = {'Spanish(Spain)': 'es', 'English(US)': 'en', 'Korean': 'ko'}
    if language in short:
        return short[language]
    match = re.search(r'\{l=([^}]+)\}', names.split(' | ')[0])
    return language if language == 'SFX' else (match.group(1) if match else language)


def slug(value):
    value = re.sub(r'[^A-Za-z0-9_-]+', '_', value).strip('_')
    return (value or 'audio')[:80]


def descriptive_name(names, events, room):
    event = re.sub(r'\{[^}]*\}', '', names.split(' | ')[0]).strip()
    technical = slug(event) if names else 'sin_evento'
    title = getattr(events, 'titles', {}).get(event.lower(), '')
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title).strip(' .')
    if title and getattr(events, 'title_only', False):
        title = title[:room].rstrip(' .')
        if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', title, re.I):
            title = '_' + title
        return title, title
    # Keep the technical event intact when adding a title; omit the prefix if tight.
    space = min(64, room - len(technical) - 2)
    if title and space >= 8:
        prefix = title[:space].rstrip(' .')
        return prefix + '__' + technical, title
    return technical[:min(80,room)], ''


def source_folder(label, path):
    original = re.sub(r'[^A-Za-z0-9_-]+', '_', Path(path).stem).strip('_') or 'audio'
    return label + '__' + original


def file_digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def validate_saved_audio(path, row):
    if path.suffix.lower() == '.wav':
        if wav_info(path)['frames'] != row['frames']:
            raise ValueError(f'WAV modificado: {path}')
    elif path.suffix.lower() == '.mp3':
        if path.stat().st_size != row['bytes'] or file_digest(path) != row['sha256']:
            raise ValueError(f'MP3 modificado: {path}')
    else:
        raise ValueError('Formato de audio no admitido.')


def validate_paths(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir():
        raise ValueError('La carpeta de origen no existe.')
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Origen y destino deben estar separados, sin contenerse.')
    return source, output


def inventory(root, cancel):
    root = Path(root).resolve()
    rows = []
    for parent, dirs, files in os.walk(root, followlinks=False):
        if cancel.is_set():
            raise Cancelled()
        dirs[:] = [d for d in dirs if not (Path(parent) / d).is_symlink()
                   and (Path(parent) / d).resolve().is_relative_to(root)]
        for name in files:
            path = Path(parent) / name
            if path.suffix.lower() not in ('.pck', '.wem') or path.is_symlink():
                continue
            if path.resolve().is_relative_to(root):
                rows.append(path)
    return sorted(rows)


def load_names(inventory_csv='', catalog_csv='', title_language='es', title_only=False):
    if title_language not in ('es', 'en', 'ko'):
        raise ValueError('Idioma de titulos no compatible.')
    packages, events = {}, {}
    titles = {}
    if inventory_csv:
        with Path(inventory_csv).open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                packages[Path(row['Path']).name.lower()] = row['Decoded']
    if not catalog_csv and LOCAL_CATALOG.is_file():
        data = json.loads(LOCAL_CATALOG.read_text(encoding='utf-8'))
        if data.get('schema_version') != 1:
            raise ValueError('Catalogo local no compatible.')
        events = {(r['language'], r['package'], r['media_id']): r['event_names']
                  for r in data['entries']}
        titles = data.get('event_titles_by_language', {}).get(title_language, {})
        if not titles and title_language == data.get('title_locale', 'es'):
            titles = data.get('event_titles', {})
    if catalog_csv:
        with Path(catalog_csv).open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                if not row['media_id'] or not row['event_names']:
                    continue
                parts = row['source'].replace('\\', '/').split('/')
                if 'raw' in parts and len(parts) > parts.index('raw') + 2:
                    pos = parts.index('raw')
                    package = parts[pos + 2]
                    key = (row['language'], package, row['media_id'])
                    values = set(events.get(key, '').split(' | ')) | set(row['event_names'].split(' | '))
                    events[key] = ' | '.join(sorted(values - {''}))
    return packages, EventCatalog(events, titles, title_only)


def wav_info(path, full=False):
    with wave.open(str(path), 'rb') as f:
        frames, rate = f.getnframes(), f.getframerate()
        if not frames or not rate or f.getcomptype() != 'NONE':
            raise ValueError(f'WAV PCM vacio o invalido: {path}')
        expected = frames * f.getnchannels() * f.getsampwidth()
        if full:
            actual = 0
            while data := f.readframes(65536):
                actual += len(data)
            if actual != expected:
                raise ValueError(f'WAV truncado: {path}')
        elif path.stat().st_size < expected:
            raise ValueError(f'WAV truncado: {path}')
        return dict(seconds=frames / rate, frames=frames, rate=rate, channels=f.getnchannels())


class Extractor:
    def __init__(self, tools, cancel=None, emit=lambda message: None):
        self.tools = {k: Path(tools.get(k, '')).resolve() for k in TOOL_KEYS}
        for key, path in self.tools.items():
            if key != 'ffmpeg' and not path.is_file():
                raise ValueError(f'Herramienta no disponible: {key}: {path}')
        self.cancel = cancel or threading.Event()
        self.emit = emit

    def command(self, args, cwd, log, timeout=1800):
        if self.cancel.is_set():
            raise Cancelled()
        with log.open('ab') as stream:
            stream.write(('\n' + subprocess.list2cmdline([str(a) for a in args]) + '\n').encode())
            stream.flush()
            process = subprocess.Popen([str(a) for a in args], cwd=cwd,
                                       stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            start = time.monotonic()
            while process.poll() is None:
                if self.cancel.wait(.1) or time.monotonic() - start > timeout:
                    process.kill()
                    process.wait()
                    if self.cancel.is_set():
                        raise Cancelled()
                    raise TimeoutError('Tiempo limite de herramienta; revisar registro.')
            if process.returncode:
                raise RuntimeError(f'Error {process.returncode}: {Path(args[0]).name}. Ver {log}')

    def extract(self, path, source, output, packages=None, events=None, output_format='wav'):
        if output_format not in ('wav', 'mp3', 'both'):
            raise ValueError('Formato de salida no valido.')
        if output_format != 'wav' and not self.tools['ffmpeg'].is_file():
            raise ValueError('MP3 requiere FFmpeg. Configuralo en Herramientas y nombres.')
        if output_format == 'both':
            wav = self.extract(path, source, output, packages, events, 'wav')
            mp3 = self.extract(path, source, output, packages, events, 'mp3')
            return dict(state='complete', output_format='both', reports={'wav': wav, 'mp3': mp3},
                        wav_count=wav['wav_count'] + mp3['wav_count'], wavs=wav['wavs'] + mp3['wavs'])
        source, output = validate_paths(source, output)
        path = Path(path).resolve()
        if not path.is_relative_to(source) or path.suffix.lower() not in ('.pck', '.wem'):
            raise ValueError('Archivo fuera del origen o formato no admitido.')
        packages, events = packages or {}, events or {}
        stat = path.stat()
        relative = path.relative_to(source)
        fingerprint = dict(source=str(path), bytes=stat.st_size, modified=stat.st_mtime_ns)
        token = hashlib.sha256(str(path).casefold().encode()).hexdigest()[:16]
        if output_format == 'mp3':
            token += '_mp3'
        label = slug(audio_name(path, packages))
        metadata = output / '.loa_audio'
        if not metadata.resolve().is_relative_to(output):
            raise ValueError('Directorio de metadatos fuera del destino.')
        marker = metadata / (token + '.json')
        report = dict(schema_version=3 if output_format == 'mp3' else 2,
                      output_format=output_format, decoded_name=audio_name(path, packages),
                      original_name=path.name, state='in_progress', input=fingerprint,
                      folder=source_folder(label, path),
                      wav_count=0, wavs=[])
        if marker.exists():
            report = json.loads(marker.read_text(encoding='utf-8'))
            if (report.get('schema_version') not in (2, 3) or report['input'] != fingerprint
                    or report.get('output_format', 'wav') != output_format):
                raise ValueError(f'El origen cambio; elige otro destino: {relative}')
            if report.get('pending_name'):
                raise ValueError('Hay un renombrado pendiente; usa Actualizar nombres del destino antes de extraer.')
            present, missing = [], []
            for row in report['wavs']:
                wav = (output / row['wav']).resolve()
                if not wav.is_relative_to(output) or wav.suffix.lower() != '.' + output_format:
                    raise ValueError('Ruta de manifiesto no valida.')
                try:
                    validate_saved_audio(wav, row)
                except FileNotFoundError:
                    missing.append(row)
                    continue
                present.append(row)
            if missing:
                pending = report.setdefault('missing_wavs', {})
                pending.update((row['media_source'], row) for row in missing)
                report['wavs'] = present
                report['wav_count'] = len(present)
                report['state'] = 'in_progress'
                self.save_report(marker, report)
            if report.get('missing_wavs'):
                report['state'] = 'in_progress'
                self.emit(f'Recuperando {len(report["missing_wavs"])} {output_format.upper()} ausentes; '
                          f'{len(report["wavs"])} existentes se conservan: {relative}')
            if report['state'] == 'complete':
                self.emit(f'Ya completado: {relative}')
                return report
        else:
            # Preserve completed v1.0 exports in place, without duplicating or
            # reorganizing the user's existing audio library.
            old_token = hashlib.sha256(str(relative).encode()).hexdigest()[:12]
            for old_label in (dict.fromkeys((label, slug(path.stem))) if output_format == 'wav' else ()):
                old_job = output / 'paquetes' / (old_label[:55] + '__' + old_token)
                old_marker = old_job / 'completado.json'
                if old_marker.is_file():
                    old = json.loads(old_marker.read_text(encoding='utf-8'))
                    if old['input'] != fingerprint:
                        raise ValueError(f'El origen cambio; elige otro destino: {relative}')
                    for row in old['wavs']:
                        wav = (old_job / row['wav']).resolve()
                        if not wav.is_relative_to(output):
                            raise ValueError('Ruta de manifiesto antiguo no valida.')
                        wav_info(wav)
                    self.emit(f'Ya completado en formato v1.0 (sin reorganizar): {relative}')
                    return old
        output.mkdir(parents=True, exist_ok=True)
        try:
            general_folder(output)
        except OSError as error:
            self.emit(f'No se pudo configurar la vista de carpeta: {error}')
        if shutil.disk_usage(output).free < max(100_000_000, stat.st_size * 4):
            raise ValueError('Espacio libre insuficiente para iniciar este archivo.')
        metadata.mkdir(exist_ok=True)
        job = (output / report['folder']).resolve()
        if job.parent != output or job == metadata:
            raise ValueError('Carpeta de audio no valida.')
        log = metadata / (token + '.log')
        self.save_report(marker, report)
        # TemporaryDirectory is constrained to the resolved metadata directory;
        # its unique workspace is removed on success, failure and cancellation.
        with tempfile.TemporaryDirectory(prefix='work_', dir=metadata) as temporary:
            attempt = Path(temporary).resolve()
            if not attempt.is_relative_to(metadata.resolve()):
                raise ValueError('Directorio temporal fuera del destino.')
            self.convert_media(path, relative, source, output, label, job, attempt,
                               log, token, packages, events, marker, report)
        if report.get('missing_wavs'):
            raise ValueError('El paquete no produjo todos los medios pendientes; se conserva el progreso para reintentar.')
        report['state'] = 'complete'
        self.save_report(marker, report)
        self.emit(f'Completado: {relative} -> {report["wav_count"]} {output_format.upper()}')
        return report

    @staticmethod
    def save_report(marker, report):
        temporary = marker.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
        temporary.replace(marker)

    def reusable_wavs(self, output, marker, report):
        """Reuse only registered, unchanged WAVs from the same source fingerprint."""
        wav_marker = marker.with_name(marker.name.replace('_mp3.json', '.json'))
        if not wav_marker.is_file():
            return {}, False
        cached = json.loads(wav_marker.read_text(encoding='utf-8'))
        if (cached.get('schema_version') != 2 or cached.get('input') != report['input']
                or cached.get('pending_name')):
            return {}, False
        rows = {}
        for row in cached['wavs']:
            path = (output / row['wav']).resolve()
            if not path.is_relative_to(output) or path.suffix.lower() != '.wav':
                raise ValueError('Ruta de WAV registrado no valida.')
            try:
                validate_saved_audio(path, row)
            except FileNotFoundError:
                continue
            rows[row['media_source']] = (path, row)
        complete = (cached['state'] == 'complete' and not cached.get('missing_wavs')
                    and len(rows) == len(cached['wavs']))
        return rows, complete

    def encode_mp3(self, wav, target, info, attempt, log):
        args = [self.tools['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-nostdin',
                '-n', '-i', wav, '-map', '0:a:0', '-vn', '-map_metadata', '-1',
                '-codec:a', 'libmp3lame', '-b:a', '320k', '-ar', '44100']
        if info['channels'] > 2:
            args += ['-ac', '2']
        self.command(args + ['-f', 'mp3', target], attempt, log)
        # Decode the full result before publishing it; extension alone is not validation.
        self.command([self.tools['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-nostdin',
                      '-xerror', '-err_detect', 'explode', '-i', target, '-f', 'null', '-'], attempt, log)
        if target.stat().st_size == 0:
            raise ValueError('MP3 vacio.')
        return dict(bytes=target.stat().st_size, sha256=file_digest(target),
                    bitrate_kbps=320, encoded_rate=44100, encoded_channels=min(2, info['channels']))

    def convert_media(self, path, relative, source, output, label, job, attempt,
                      log, token, packages, events, marker, report):
        output_format = report.get('output_format', 'wav')
        cached, complete = self.reusable_wavs(output, marker, report) if output_format == 'mp3' else ({}, False)
        if complete:
            media = [(name, value[0]) for name, value in sorted(cached.items())]
            self.emit(f'MP3: reutilizando {len(media)} WAV registrados de {relative}')
        else:
            with path.open('rb') as f:
                magic = f.read(4)
            decoded = path
            if magic == bytes.fromhex('3ecea674'):
                decoded = attempt / (label + path.suffix.lower())
                self.command([self.tools['lautool'], '-d', path, decoded], attempt, log)
            with decoded.open('rb') as f:
                magic = f.read(4)
            if path.suffix.lower() == '.pck':
                if magic != b'AKPK':
                    raise ValueError('PCK no compatible: falta firma AKPK despues de LAUTool.')
                raw = attempt / 'medios'
                raw.mkdir()
                self.command([self.tools['quickbms'], '-o', '-Y', self.tools['script'], decoded, raw], attempt, log)
                paths = sorted(raw.rglob('*.wem'))
            else:
                if magic not in (b'RIFF', b'RIFX'):
                    raise ValueError('WEM no compatible: falta firma RIFF/RIFX.')
                raw, paths = decoded.parent, [decoded]
            media = [(wem.relative_to(raw).as_posix(), wem) for wem in paths]
        completed_media = {row['media_source'] for row in report['wavs']}
        claimed = set()
        for manifest in marker.parent.glob('*.json'):
            data = json.loads(manifest.read_text(encoding='utf-8'))
            if data.get('schema_version') in (2, 3):
                for row in data.get('wavs', []):
                    candidate = (output / row['wav']).resolve()
                    if candidate.is_relative_to(output):
                        claimed.add(candidate)
        for index, (media_source, wem) in enumerate(media, 1):
            if self.cancel.is_set():
                raise Cancelled()
            if media_source in completed_media:
                continue
            mid = audio_name(path, packages) if path.suffix.lower() == '.wem' else Path(media_source).stem
            package = 'loose' if path.suffix.lower() == '.wem' else label
            prior = report.get('missing_wavs', {}).get(media_source, {})
            language, names = resolve_event(events, package, mid, Path(media_source).parent, path.parent)
            names = names or prior.get('events', '') or cached.get(media_source, (None, {}))[1].get('events', '')
            name = slug(re.sub(r'\{[^}]*\}', '', names.split(' | ')[0])) if names else 'sin_evento'
            identity = hashlib.sha256((token + '/' + media_source).encode()).hexdigest()[:12]
            suffix = '__' + slug(event_language(language, names))[:16] + '__' + slug(mid)[:24]
            room = min(160, 245 - len(str(job)) - 1 - len(suffix) - len('_9999999.wav'))
            if room < 1:
                raise ValueError('Ruta demasiado larga; elige un destino mas corto.')
            name, descriptive_title = descriptive_name(names, events, room)
            title_only = bool(descriptive_title and getattr(events, 'title_only', False))
            stem = name if title_only else name + suffix
            dest = job / (stem + '.' + output_format)
            number = 1
            while dest.exists() or dest.resolve() in claimed:
                if dest.resolve() not in claimed and not title_only:
                    raise ValueError(f'Archivo no registrado ya existe; no se sobrescribe: {dest}')
                number += 1
                dest = job / (stem + f'_{number}.' + output_format)
            if len(str(dest)) > 245:
                raise ValueError('Ruta demasiado larga; elige un destino mas corto.')
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                general_folder(dest.parent)
            except OSError as error:
                self.emit(f'No se pudo configurar la vista de carpeta: {error}')
            temporary = attempt / (identity + '.partial.wav')
            self.emit(f'{label}: {index}/{len(media)} - {dest.name}')
            if media_source in cached:
                decoded_wav = cached[media_source][0]
            else:
                self.command([self.tools['vgmstream'], '-i', '-o', temporary, wem], attempt, log)
                decoded_wav = temporary
            info = wav_info(decoded_wav, full=True)
            if output_format == 'mp3':
                mp3 = attempt / (identity + '.partial.mp3')
                info.update(self.encode_mp3(decoded_wav, mp3, info, attempt, log))
                if decoded_wav == temporary:
                    temporary.unlink()
                temporary = mp3
            if self.cancel.is_set():
                raise Cancelled()
            # On Windows rename fails if a destination appeared meanwhile.
            temporary.rename(dest)
            row = dict(prior, wav=str(dest.relative_to(output)), media_source=media_source,
                       media_id=mid, events=names, descriptive_title=descriptive_title, title_only=title_only, **info)
            report['wavs'].append(row)
            if prior:
                report['missing_wavs'].pop(media_source)
                if not report['missing_wavs']:
                    del report['missing_wavs']
            report['wav_count'] = len(report['wavs'])
            self.save_report(marker, report)
            claimed.add(dest.resolve())
        if self.cancel.is_set():
            raise Cancelled()
