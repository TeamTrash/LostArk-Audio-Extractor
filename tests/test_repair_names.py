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
    def test_title_only_collision_repeat_and_restore_full_name(self):
        titles = {'known_song': 'Aldea de las Nia'}
        full = core.EventCatalog(self.events, titles)
        simple = core.EventCatalog(self.events, titles, title_only=True)
        repair_output(self.output, full, apply=True)
        row = json.loads(self.marker.read_text())['wavs'][0]
        old = self.output / row['wav']
        before = digest(old)
        occupied = old.with_name('Aldea de las Nia.wav')
        occupied.write_bytes(b'unrelated')
        self.assertEqual(repair_output(self.output, simple, apply=True)['renamed'], 1)
        row = json.loads(self.marker.read_text())['wavs'][0]
        renamed = self.output / row['wav']
        self.assertEqual(renamed.name, 'Aldea de las Nia_2.wav')
        self.assertEqual(digest(renamed), before)
        self.assertTrue(row['title_only'])
        self.assertEqual(repair_output(self.output, simple, apply=True)['renamed'], 0)
        self.assertEqual(repair_output(self.output, full, apply=True)['renamed'], 1)
        self.assertEqual(digest(old), before)
        self.assertEqual(occupied.read_bytes(), b'unrelated')

    def test_title_only_without_translation_keeps_identity(self):
        catalog = core.EventCatalog(self.events, title_only=True)
        repair_output(self.output, catalog, apply=True)
        row = json.loads(self.marker.read_text())['wavs'][0]
        self.assertEqual(Path(row['wav']).name, 'known_song__es__123.wav')
        reserved = core.EventCatalog({}, {'known_song': 'CON'}, title_only=True)
        self.assertEqual(core.descriptive_name('known_song', reserved, 80)[0], '_CON')

    def test_switch_title_languages_preserves_audio_and_audio_locale(self):
        before = digest(self.wav)
        for title in ('Isabella, mi amor', 'Isabella, My Love', '', '사랑', 'Isabella, mi amor'):
            catalog = core.EventCatalog(self.events, {'known_song': title} if title else {})
            self.assertEqual(repair_output(self.output, catalog, apply=True)['renamed'], 1)
            row = json.loads(self.marker.read_text())['wavs'][0]
            audio = self.output / row['wav']
            prefix = title + '__' if title else ''
            self.assertEqual(audio.name, prefix + 'known_song__es__123.wav')
            self.assertEqual(digest(audio), before)
            self.assertEqual(repair_output(self.output, catalog, apply=True)['renamed'], 0)

    def test_load_selected_title_language_and_legacy_fallback(self):
        local = self.root / 'titles.json'
        data = dict(schema_version=1, entries=[], event_titles={'song': 'Español'}, title_locale='es',
                    event_titles_by_language={'en': {'song': 'English'}, 'ko': {}})
        local.write_text(json.dumps(data), encoding='utf-8')
        with patch.object(core, 'LOCAL_CATALOG', local):
            self.assertEqual(core.load_names(title_language='es')[1].titles, {'song': 'Español'})
            self.assertEqual(core.load_names(title_language='en')[1].titles, {'song': 'English'})
            self.assertEqual(core.load_names(title_language='ko')[1].titles, {})
            with self.assertRaises(ValueError):
                core.load_names(title_language='unknown')

    def test_existing_technical_name_gets_title_without_changing_audio_or_locale(self):
        repair_output(self.output, self.events, apply=True)
        named = self.output / json.loads(self.marker.read_text())['wavs'][0]['wav']
        before = digest(named)
        catalog = core.EventCatalog(self.events, {'known_song': 'Isabella, mi amor'})
        self.assertEqual(repair_output(self.output, catalog)['planned'], 1)
        self.assertTrue(named.exists())
        self.assertEqual(repair_output(self.output, catalog, apply=True)['renamed'], 1)
        row = json.loads(self.marker.read_text())['wavs'][0]
        result = self.output / row['wav']
        self.assertEqual(result.name, 'Isabella, mi amor__known_song__es__123.wav')
        self.assertEqual(digest(result), before)
        self.assertEqual(row['events'], 'known_song {l=es}')
        self.assertEqual(repair_output(self.output, catalog, apply=True)['renamed'], 0)

    def test_title_sanitization_and_short_path_budget(self):
        catalog = core.EventCatalog({}, {'known_song': 'Canción: amor / paz?'})
        name, title = core.descriptive_name('known_song', catalog, 100)
        self.assertEqual(name, 'Canción_ amor _ paz___known_song')
        self.assertEqual(core.descriptive_name('known_song', catalog, 16), ('known_song', ''))
        self.assertEqual(core.descriptive_name('other_song', catalog, 100), ('other_song', ''))

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
        self.assertEqual(new.name, 'known_song__es__123.wav')
        self.assertEqual(new.read_bytes(), before)
        self.assertEqual(updated['wavs'][0]['previous_names'], [self.report['wavs'][0]['wav']])
        self.assertEqual((self.metadata / 'naming_backups' / self.marker.name).read_bytes(), marker_before)
        self.assertEqual(repair_output(self.output, self.events, apply=True)['renamed'], 0)

    def test_unknown_and_other_language_are_not_guessed(self):
        result = repair_output(self.output, {('SFX', 'SOUND_BGM_GLOBAL', '123'): 'wrong'}, True)
        self.assertEqual(result['unknown'], 1)
        self.assertTrue(self.wav.exists())

    def test_existing_target_is_preserved(self):
        other = self.wav.with_name('known_song__es__123.wav')
        other.write_bytes(b'unrelated')
        repair_output(self.output, self.events, True)
        self.assertEqual(other.read_bytes(), b'unrelated')
        self.assertTrue(self.wav.with_name('known_song__es__123_2.wav').is_file())

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
        new = self.wav.with_name('known_song__es__123.wav')
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

