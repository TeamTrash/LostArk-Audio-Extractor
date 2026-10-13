import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class SettingsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.config = self.home / 'config.local.json'
        for key, relative in app.TOOL_PATHS.items():
            path = self.home / 'tools' / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'test fixture')
        for name, value in [('HERE', self.home), ('CONFIG', self.config)]:
            patcher = patch.object(app, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_defaults_are_inside_app(self):
        self.assertTrue(all(Path(p).is_relative_to(self.home / 'tools') for p in app.defaults().values()))

    def test_frozen_config_is_next_to_executable_not_temporary_resources(self):
        exe = self.home / 'portable' / 'LoaAudioExtractor.exe'
        with patch.object(app.sys, 'frozen', True, create=True), \
                patch.object(app.sys, 'executable', str(exe)):
            self.assertEqual(app.config_path(), exe.parent / 'config.local.json')

    def test_source_config_stays_in_app_directory(self):
        with patch.object(app.sys, 'frozen', False, create=True):
            self.assertEqual(app.config_path(), self.home / 'config.local.json')

    def test_legacy_tool_paths_migrate_and_session_folders_are_ignored(self):
        saved = {k: str(self.home / 'old/tools/audio_converters' / r) for k, r in app.TOOL_PATHS.items()}
        saved.update(source='user source', output='user output')
        self.config.write_text(json.dumps(saved))
        result = app.load_settings()
        self.assertNotIn('source', result)
        self.assertNotIn('output', result)
        for k, value in app.defaults().items():
            self.assertEqual(result[k], value)

    def test_relative_paths_round_trip(self):
        saved = app.portable_settings(app.defaults())
        self.assertTrue(all(p.startswith('tools/') for p in saved.values()))
        self.config.write_text(json.dumps(saved))
        self.assertEqual(app.load_settings(), app.defaults())

    def test_save_excludes_session_folders_without_clearing_live_values(self):
        settings = dict(app.defaults(), source='current input', output='current output',
                        inventory='names.csv', catalog='events.csv')
        saved = app.portable_settings(settings)
        self.assertNotIn('source', saved)
        self.assertNotIn('output', saved)
        self.assertEqual(saved['inventory'], 'names.csv')
        self.assertEqual(saved['catalog'], 'events.csv')
        self.assertEqual(settings['source'], 'current input')
        self.assertEqual(settings['output'], 'current output')
        self.config.write_text(json.dumps(saved))
        loaded = app.load_settings()
        self.assertNotIn('source', loaded)
        self.assertNotIn('output', loaded)
        for key, value in app.defaults().items():
            self.assertEqual(loaded[key], value)

    def test_custom_existing_tool_is_preserved(self):
        custom = self.home / 'custom.exe'
        custom.write_bytes(b'custom')
        self.config.write_text(json.dumps({'lautool': str(custom)}))
        self.assertEqual(app.load_settings()['lautool'], str(custom))
