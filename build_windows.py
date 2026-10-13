# SPDX-License-Identifier: MIT
"""Build a self-contained local-use Windows EXE with explicit resource allowlists."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from build_release import ROOT, TOOL_FILES, LOCAL_DATA_FILES
from version import __version__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Build on Windows using 64-bit Python with Tk and PyInstaller.')
    import PyInstaller
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = ROOT / 'build' / 'windows'
    work.mkdir(parents=True, exist_ok=True)
    resources = TOOL_FILES + LOCAL_DATA_FILES + (
        'assets/app.png', 'assets/app.ico',
        'LICENSE', 'THIRD_PARTY_NOTICES.md', 'LOCAL_USE_ONLY.md', 'README.md',
        'WINDOWS_EXE.md', 'licenses/lostark-explorer-MIT.txt', 'licenses/Tcl-8.6.12-license.terms',
    )
    data = []
    for name in resources:
        path = ROOT / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f'Missing or unsafe resource: {name}')
        data.append((path, str(Path(name).parent)))
    licenses = {
        'Python-LICENSE.txt': Path(sys.base_prefix) / 'LICENSE.txt',
        'Tk-license.terms': Path(sys.base_prefix) / 'tcl' / 'tk8.6' / 'license.terms',
        'PyInstaller-COPYING.txt': Path(importlib.metadata.distribution('pyinstaller').locate_file(
            'pyinstaller-6.22.3.dist-info/licenses/COPYING.txt')),
    }
    for name, source in licenses.items():
        if not source.is_file():
            raise ValueError(f'Missing runtime license: {source}')
        dest = output / 'licenses' / name
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, dest)
        data.append((dest, 'licenses'))
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile',
               '--windowed', '--noupx', '--icon', str(ROOT / 'assets' / 'app.ico'),
               '--name', f'LoaAudioExtractor-{__version__}',
               '--distpath', str(output), '--workpath', str(work / 'cache'),
               '--specpath', str(work), '--paths', str(ROOT)]
    for path, folder in data:
        command += ['--add-data', str(path) + os.pathsep + folder]
    command.append(str(ROOT / 'exe_entry.py'))
    env = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(work / 'config'))
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    exe = output / f'LoaAudioExtractor-{__version__}.exe'
    manifest = dict(version=__version__, kind='windows-onefile-local-use',
                    python=sys.version, pyinstaller=PyInstaller.__version__,
                    exe=dict(name=exe.name, bytes=exe.stat().st_size,
                             sha256=hashlib.sha256(exe.read_bytes()).hexdigest()),
                    resources={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                               for name in resources})
    (output / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (output / 'SHA256SUMS.txt').write_text(f'{manifest["exe"]["sha256"]}  {exe.name}\n', encoding='ascii')
    for name in ('LICENSE', 'LOCAL_USE_ONLY.md', 'THIRD_PARTY_NOTICES.md', 'WINDOWS_EXE.md'):
        shutil.copyfile(ROOT / name, output / name)
    for name in ('lostark-explorer-MIT.txt', 'Tcl-8.6.12-license.terms'):
        shutil.copyfile(ROOT / 'licenses' / name, output / 'licenses' / name)
    print('Built:', exe)


if __name__ == '__main__':
    main()
