import csv
import json
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import core
from repair_names import digest, repair_output


class RepairNamesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.output = self.root / 'out'
        self.metadata = self.output / '.loa_audio'
        self.metadata.mkdir(parents=True)
        self.wav = self.output / 'SOUND_BGM_GLOBAL' / 'sin_evento__Spanish_Spain__123.wav'
        self.wav.parent.mkdir()
        with wave.open(str(self.wav), 'wb') as f:
            f.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            f.writeframes(b'\x01\x00' * 80)
        self.marker = self.metadata / 'source.json'
        self.report = dict(schema_version=2, state='complete',
                           input=dict(source=str(self.root / 'Spanish(Spain)' / 'SOUND_BGM_GLOBAL.pck')),
                           wavs=[dict(wav=str(self.wav.relative_to(self.output)), media_id='123',
                                      events='', frames=80)])
        core.Extractor.save_report(self.marker, self.report)
        self.events = {('Spanish(Spain)', 'SOUND_BGM_GLOBAL', '123'): 'known_song {l=es}'}

    def test_dry_run_then_apply_is_idempotent(self):
        before = self.wav.read_bytes()
        marker_before = self.marker.read_bytes()
        result = repair_output(self.output, self.events)
        self.assertEqual(result['planned'], 1)
        self.assertTrue(self.wav.exists())
        self.assertEqual(self.marker.read_bytes(), marker_before)
        result = repair_output(self.output, self.events, apply=True)
        self.assertEqual(result['renamed'], 1)
        self.assertFalse(self.wav.exists())
        updated = json.loads(self.marker.read_text())
        new = self.output / updated['wavs'][0]['wav']
        self.assertEqual(new.name, 'known_song__Spanish_Spain__123.wav')
        self.assertEqual(new.read_bytes(), before)
        self.assertEqual(updated['wavs'][0]['previous_names'], [self.report['wavs'][0]['wav']])
        self.assertEqual((self.metadata / 'naming_backups' / self.marker.name).read_bytes(), marker_before)
        self.assertEqual(repair_output(self.output, self.events, apply=True)['renamed'], 0)

    def test_unknown_and_other_language_are_not_guessed(self):
        result = repair_output(self.output, {('SFX', 'SOUND_BGM_GLOBAL', '123'): 'wrong'}, True)
        self.assertEqual(result['unknown'], 1)
        self.assertTrue(self.wav.exists())

    def test_existing_target_is_preserved(self):
        other = self.wav.with_name('known_song__Spanish_Spain__123.wav')
        other.write_bytes(b'unrelated')
        repair_output(self.output, self.events, True)
        self.assertEqual(other.read_bytes(), b'unrelated')
        self.assertTrue(self.wav.with_name('known_song__Spanish_Spain__123_2.wav').is_file())

    def test_outside_path_is_rejected(self):
        self.report['wavs'][0]['wav'] = '../outside.wav'
        core.Extractor.save_report(self.marker, self.report)
        with self.assertRaises(ValueError):
            repair_output(self.output, self.events, True)

    def test_cancel_before_rename(self):
        event = threading.Event()
        event.set()
        with self.assertRaises(core.Cancelled):
            repair_output(self.output, self.events, True, cancel=event)
        self.assertTrue(self.wav.exists())

    def pending(self):
        new = self.wav.with_name('known_song__Spanish_Spain__123.wav')
        self.report['pending_name'] = dict(index=0, old=self.report['wavs'][0]['wav'],
                                          new=str(new.relative_to(self.output)), sha256=digest(self.wav),
                                          events='known_song {l=es}')
        core.Extractor.save_report(self.marker, self.report)
        return new

    def test_recover_interruption_before_move(self):
        new = self.pending()
        self.assertEqual(repair_output(self.output, self.events, True)['renamed'], 1)
        self.assertTrue(new.is_file())

    def test_recover_interruption_after_move(self):
        new = self.pending()
        self.wav.rename(new)
        self.assertEqual(repair_output(self.output, self.events, True)['renamed'], 1)
        self.assertNotIn('pending_name', json.loads(self.marker.read_text()))

    def test_recovery_rejects_changed_audio(self):
        new = self.pending()
        self.wav.rename(new)
        new.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            repair_output(self.output, self.events, True)

    def test_local_catalog_autoload_and_explicit_csv_override(self):
        local = self.root / 'event_names.local.json'
        local.write_text(json.dumps(dict(schema_version=1, entries=[dict(
            language='Spanish(Spain)', package='SOUND_BGM_GLOBAL', media_id='123', event_names='local_song')])))
        catalog = self.root / 'catalog.csv'
        with catalog.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['language', 'media_id', 'event_names', 'source'])
            writer.writeheader()
            for name in ('manual_song', 'second_song'):
                writer.writerow(dict(language='Spanish(Spain)', media_id='123', event_names=name,
                                     source='raw/Spanish(Spain)/SOUND_BGM_GLOBAL/123.wem'))
        key = ('Spanish(Spain)', 'SOUND_BGM_GLOBAL', '123')
        with patch.object(core, 'LOCAL_CATALOG', local):
            self.assertEqual(core.load_names()[1][key], 'local_song')
            self.assertEqual(core.load_names(catalog_csv=catalog)[1][key], 'manual_song | second_song')
        with patch.object(core, 'LOCAL_CATALOG', self.root / 'missing.json'):
            self.assertEqual(core.load_names()[1], {})
