import hashlib
import json
import tempfile
import unittest
import shutil
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from build_release import PREFIX, ROOT, SOURCE_FILES, TOOL_FILES, LOCAL_DATA_FILES, build_release, verify_archive
from version import __version__


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def test_package_has_licenses_and_no_local_files(self):
        archive = build_release(self.folder)
        manifest = verify_archive(archive)
        self.assertEqual(manifest['version'], __version__)
        with ZipFile(archive) as z:
            names = z.namelist()
            self.assertIn(f'{PREFIX}/LICENSE', names)
            self.assertIn(f'{PREFIX}/licenses/lostark-explorer-MIT.txt', names)
            self.assertFalse(any(n.endswith(('.exe', '.dll', '.bms', '.wem', '.pck', '.wav')) for n in names))
            self.assertFalse(any('config.local' in n or 'este_equipo' in n for n in names))
            self.assertNotIn(f'{PREFIX}/data/event_names.local.json', names)
            for name in names:
                self.assertNotIn(b'C:\\Users\\Codex', z.read(name))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual((self.folder / 'SHA256SUMS.txt').read_text().split()[0], digest)

    def test_identical_inputs_produce_same_zip(self):
        first = build_release(self.folder / 'first')
        second = build_release(self.folder / 'second')
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_tampered_payload_rejected(self):
        archive = build_release(self.folder)
        with ZipFile(archive) as z:
            entries = {n: z.read(n) for n in z.namelist()}
        entries[f'{PREFIX}/app.py'] += b'\n# modified\n'
        altered = self.folder / 'altered.zip'
        with ZipFile(altered, 'w', ZIP_DEFLATED) as z:
            for name, data in entries.items():
                z.writestr(name, data)
        with self.assertRaises(ValueError):
            verify_archive(altered)

    def test_missing_required_source_rejected(self):
        with self.assertRaises(ValueError):
            build_release(self.folder / 'out', root=self.folder)

    def fake_local_root(self):
        root = self.folder / 'app'
        for name in SOURCE_FILES:
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)
        for name in TOOL_FILES + LOCAL_DATA_FILES:
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(('synthetic fixture ' + name).encode())
        return root

    def test_local_bundle_contains_tools_not_private_settings(self):
        root = self.fake_local_root()
        (root / 'config.local.json').write_text('{"source":"private"}')
        build_release(self.folder / 'dist', root=root)
        archive = build_release(self.folder / 'dist', root=root, include_tools=True)
        manifest = verify_archive(archive)
        self.assertEqual(manifest['kind'], 'local-tools')
        with ZipFile(archive) as z:
            self.assertIn(f'{PREFIX}/tools/LAUTool_0.3/LAUTool_steam.exe', z.namelist())
            self.assertIn(f'{PREFIX}/tools/vgmstream/bin/libvorbis.dll', z.namelist())
            self.assertIn(f'{PREFIX}/data/event_names.local.json', z.namelist())
            self.assertNotIn(f'{PREFIX}/config.local.json', z.namelist())
            deps = json.loads(z.read(f'{PREFIX}/DEPENDENCIES.json'))
            self.assertTrue(all(t['bundled'] for t in deps['external_tools']))
        self.assertEqual(len((archive.parent / 'SHA256SUMS.txt').read_text().splitlines()), 2)

    def test_incomplete_tool_bundle_fails(self):
        root = self.fake_local_root()
        (root / 'tools/vgmstream/bin/libvorbis.dll').unlink()
        with self.assertRaises(ValueError):
            build_release(self.folder / 'dist', root=root, include_tools=True)
