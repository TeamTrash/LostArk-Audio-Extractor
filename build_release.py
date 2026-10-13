# SPDX-License-Identifier: MIT
"""Build separate public source and local-use bundles from explicit allowlists."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from version import __version__

ROOT = Path(__file__).resolve().parent
SOURCE_FILES = (
    'assets/app.png', 'assets/app.ico',
    '.gitignore', 'app.py', 'core.py', 'name_decoder.py', 'version.py',
    'build_release.py', 'build_windows.py', 'exe_entry.py', 'WINDOWS_EXE.md',
    'repair_names.py', 'Iniciar.cmd', 'README.md', 'LICENSE',
    'THIRD_PARTY_NOTICES.md', 'DEPENDENCIES.json', 'CHANGELOG.md',
    'CONTRIBUTING.md', 'RELEASE.md', 'LOCAL_USE_ONLY.md', 'tools/README.md',
    'licenses/lostark-explorer-MIT.txt', 'licenses/Tcl-8.6.12-license.terms',
    'tests/test_core.py', 'tests/test_names.py', 'tests/test_settings.py',
    'tests/test_table.py', 'tests/test_release.py', 'tests/test_repair_names.py', 'tests/test_formats.py',
)
LOCAL_DATA_FILES = ('data/event_names.local.json',)
PREFIX = f'LoaAudioExtractor-{__version__}'
TOOL_FILES = (
    'tools/ffmpeg/ffmpeg.exe', 'tools/ffmpeg/LICENSE.txt',
    'tools/LAUTool_0.3/LAUTool_steam.exe',
    'tools/quickbms/bin/quickbms.exe', 'tools/quickbms/bin/quickbms.txt',
    'tools/quickbms/bin/changelog.txt', 'tools/quickbms/wwise_pck_extractor.bms',
) + tuple('tools/vgmstream/bin/' + name for name in (
    'vgmstream-cli.exe', 'avcodec-vgmstream-59.dll', 'avformat-vgmstream-59.dll',
    'avutil-vgmstream-57.dll', 'libatrac9.dll', 'libcelt-0061.dll', 'libcelt-0110.dll',
    'libg719_decode.dll', 'libmpg123-0.dll', 'libspeex-1.dll', 'libvorbis.dll',
    'swresample-vgmstream-4.dll', 'COPYING', 'README.md', 'USAGE.md',
))


def verify_archive(path):
    with ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError('ZIP CRC validation failed')
        names = z.namelist()
        manifest = json.loads(z.read(f'{PREFIX}/MANIFEST.json'))
        if manifest['version'] != __version__ or manifest['kind'] not in ('source', 'local-tools'):
            raise ValueError('Unexpected release version/kind')
        allowed = SOURCE_FILES + (TOOL_FILES + LOCAL_DATA_FILES if manifest['kind'] == 'local-tools' else ())
        entries = manifest['files']
        expected = {f'{PREFIX}/{name}' for name in allowed} | {f'{PREFIX}/MANIFEST.json'}
        if set(names) != expected or len(names) != len(expected) or set(entries) != set(allowed):
            raise ValueError('Unexpected or missing release file')
        for name, info in entries.items():
            data = z.read(f'{PREFIX}/{name}')
            if len(data) != info['bytes'] or hashlib.sha256(data).hexdigest() != info['sha256']:
                raise ValueError(f'Manifest mismatch: {name}')
    return manifest


def build_release(output, root=ROOT, include_tools=False):
    root, output = Path(root).resolve(), Path(output).resolve()
    payload = {}
    for name in SOURCE_FILES + (TOOL_FILES + LOCAL_DATA_FILES if include_tools else ()):
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError(f'Missing or unsafe source file: {name}')
        payload[name] = path.read_bytes()
    dependencies = json.loads(payload['DEPENDENCIES.json'])
    if dependencies['application_version'] != __version__:
        raise ValueError('DEPENDENCIES.json version differs from version.py')
    kind = 'local-tools' if include_tools else 'source'
    for tool in dependencies['external_tools']:
        tool['bundled'] = include_tools
    if include_tools:
        dependencies['redistribution_review'] = 'Incomplete; local use only'
    else:
        dependencies.pop('redistribution_review', None)
    payload['DEPENDENCIES.json'] = (json.dumps(dependencies, indent=2) + '\n').encode()
    manifest = dict(version=__version__, kind=kind,
                    license='mixed-see-notices' if include_tools else 'MIT',
                    files={name: dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                           for name, data in sorted(payload.items())})
    payload['MANIFEST.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'{PREFIX}-{kind}.zip'
    temporary = archive.with_suffix('.tmp')
    with ZipFile(temporary, 'w', compression=ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(payload.items()):
            info = ZipInfo(f'{PREFIX}/{name}', date_time=(2026, 10, 9, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = ZIP_DEFLATED
            z.writestr(info, data)
    verify_archive(temporary)
    temporary.replace(archive)
    sums = []
    for variant in ('source', 'local-tools'):
        item = output / f'{PREFIX}-{variant}.zip'
        if item.is_file():
            sums.append(f'{hashlib.sha256(item.read_bytes()).hexdigest()}  {item.name}\n')
    (output / 'SHA256SUMS.txt').write_text(''.join(sums), encoding='ascii')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--source-only', action='store_true', help='Build public source without local tools')
    args = parser.parse_args()
    if args.verify:
        verify_archive(args.verify)
        print('Verified:', args.verify)
    else:
        print('Built and verified:', build_release(args.output))
        if not args.source_only:
            print('Built for LOCAL USE ONLY:', build_release(args.output, include_tools=True))
