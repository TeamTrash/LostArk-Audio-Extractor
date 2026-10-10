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
from name_decoder import audio_name

TOOL_KEYS = ('lautool', 'quickbms', 'script', 'vgmstream')
LOCAL_CATALOG = Path(__file__).resolve().parent / 'data' / 'event_names.local.json'


class Cancelled(Exception):
    pass


def slug(value):
    value = re.sub(r'[^A-Za-z0-9_-]+', '_', value).strip('_')
    return (value or 'audio')[:80]


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


def load_names(inventory_csv='', catalog_csv=''):
    packages, events = {}, {}
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
    return packages, events


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
            if not path.is_file():
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

    def extract(self, path, source, output, packages=None, events=None):
        source, output = validate_paths(source, output)
        path = Path(path).resolve()
        if not path.is_relative_to(source) or path.suffix.lower() not in ('.pck', '.wem'):
            raise ValueError('Archivo fuera del origen o formato no admitido.')
        packages, events = packages or {}, events or {}
        stat = path.stat()
        relative = path.relative_to(source)
        fingerprint = dict(source=str(path), bytes=stat.st_size, modified=stat.st_mtime_ns)
        token = hashlib.sha256(str(path).casefold().encode()).hexdigest()[:16]
        label = slug(audio_name(path, packages))
        metadata = output / '.loa_audio'
        if not metadata.resolve().is_relative_to(output):
            raise ValueError('Directorio de metadatos fuera del destino.')
        marker = metadata / (token + '.json')
        report = dict(schema_version=2, state='in_progress', input=fingerprint,
                      folder='Audios_numericos' if label[0].isdigit() else label,
                      wav_count=0, wavs=[])
        if marker.exists():
            report = json.loads(marker.read_text(encoding='utf-8'))
            if report.get('schema_version') != 2 or report['input'] != fingerprint:
                raise ValueError(f'El origen cambio; elige otro destino: {relative}')
            if report.get('pending_name'):
                raise ValueError('Hay un renombrado pendiente; usa Actualizar nombres del destino antes de extraer.')
            present, missing = [], []
            for row in report['wavs']:
                wav = (output / row['wav']).resolve()
                if not wav.is_relative_to(output) or wav.suffix.lower() != '.wav':
                    raise ValueError('Ruta de manifiesto no valida.')
                try:
                    info = wav_info(wav)
                except FileNotFoundError:
                    missing.append(row)
                    continue
                if info['frames'] != row['frames']:
                    raise ValueError(f'WAV modificado: {wav}')
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
                self.emit(f'Recuperando {len(report["missing_wavs"])} WAV ausentes; '
                          f'{len(report["wavs"])} existentes se conservan: {relative}')
            if report['state'] == 'complete':
                self.emit(f'Ya completado: {relative}')
                return report
        else:
            # Preserve completed v1.0 exports in place, without duplicating or
            # reorganizing the user's existing audio library.
            old_token = hashlib.sha256(str(relative).encode()).hexdigest()[:12]
            for old_label in dict.fromkeys((label, slug(path.stem))):
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
        self.emit(f'Completado: {relative} -> {report["wav_count"]} WAV')
        return report

    @staticmethod
    def save_report(marker, report):
        temporary = marker.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
        temporary.replace(marker)

    def convert_media(self, path, relative, source, output, label, job, attempt,
                      log, token, packages, events, marker, report):
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
            media = sorted(raw.rglob('*.wem'))
        else:
            if magic not in (b'RIFF', b'RIFX'):
                raise ValueError('WEM no compatible: falta firma RIFF/RIFX.')
            raw, media = decoded.parent, [decoded]
        language = relative.parts[-2] if len(relative.parts) > 1 else (
            source.name if source.name in ('English(US)', 'Korean', 'Spanish(Spain)') else 'SFX')
        completed_media = {row['media_source'] for row in report['wavs']}
        claimed = set()
        for manifest in marker.parent.glob('*.json'):
            data = json.loads(manifest.read_text(encoding='utf-8'))
            if data.get('schema_version') == 2:
                for row in data.get('wavs', []):
                    candidate = (output / row['wav']).resolve()
                    if candidate.is_relative_to(output):
                        claimed.add(candidate)
        for index, wem in enumerate(media, 1):
            if self.cancel.is_set():
                raise Cancelled()
            media_source = wem.relative_to(raw).as_posix()
            if media_source in completed_media:
                continue
            mid = audio_name(path, packages) if path.suffix.lower() == '.wem' else wem.stem
            package = 'loose' if path.suffix.lower() == '.wem' else label
            prior = report.get('missing_wavs', {}).get(media_source, {})
            names = events.get((language, package, mid), '') or prior.get('events', '')
            name = slug(re.sub(r'\{[^}]*\}', '', names.split(' | ')[0])) if names else 'sin_evento'
            identity = hashlib.sha256((token + '/' + media_source).encode()).hexdigest()[:12]
            suffix = '__' + slug(language)[:16] + '__' + slug(mid)[:24]
            room = min(80, 245 - len(str(job)) - 1 - len(suffix) - len('_9999999.wav'))
            if room < 1:
                raise ValueError('Ruta demasiado larga; elige un destino mas corto.')
            stem = name[:room] + suffix
            dest = job / (stem + '.wav')
            number = 1
            while dest.exists() or dest.resolve() in claimed:
                if dest.resolve() not in claimed:
                    raise ValueError(f'Archivo no registrado ya existe; no se sobrescribe: {dest}')
                number += 1
                dest = job / (stem + f'_{number}.wav')
            if len(str(dest)) > 245:
                raise ValueError('Ruta demasiado larga; elige un destino mas corto.')
            dest.parent.mkdir(parents=True, exist_ok=True)
            temporary = attempt / (identity + '.partial.wav')
            self.emit(f'{label}: {index}/{len(media)} - {dest.name}')
            self.command([self.tools['vgmstream'], '-i', '-o', temporary, wem], attempt, log)
            info = wav_info(temporary, full=True)
            if self.cancel.is_set():
                raise Cancelled()
            # On Windows rename fails if a destination appeared meanwhile.
            temporary.rename(dest)
            row = dict(prior, wav=str(dest.relative_to(output)), media_source=media_source,
                       media_id=mid, events=names, **info)
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
