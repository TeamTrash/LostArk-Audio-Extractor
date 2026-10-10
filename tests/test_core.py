import json
import tempfile
import threading
import sys
import unittest
import wave
import hashlib
from pathlib import Path
from unittest.mock import patch

from core import Cancelled, Extractor, TOOL_KEYS, inventory, validate_paths, wav_info


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.out = self.root / 'out'
        self.wem = self.source / '123.wem'
        self.wem.write_bytes(b'RIFFtest')
        self.tools = {k: __file__ for k in TOOL_KEYS}

    def fake_command(self, args, cwd, log):
        wav = Path(args[args.index('-o') + 1])
        with wave.open(str(wav), 'wb') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(8000)
            f.writeframes(b'\x01\x00' * 80)

    def test_boundaries(self):
        for dest in (self.source, self.source / 'out', self.root):
            with self.assertRaises(ValueError):
                validate_paths(self.source, dest)

    def test_inventory_and_cancel(self):
        (self.source / 'ignored.txt').write_text('x')
        self.assertEqual(inventory(self.source, threading.Event()), [self.wem])
        event = threading.Event()
        event.set()
        with self.assertRaises(Cancelled):
            inventory(self.source, event)

    def test_conversion_resume_and_source_change(self):
        engine = Extractor(self.tools)
        before = self.wem.read_bytes()
        with patch.object(engine, 'command', side_effect=self.fake_command) as command:
            report = engine.extract(self.wem, self.source, self.out)
            self.assertEqual(report['wav_count'], 1)
            self.assertEqual(Path(report['wavs'][0]['wav']).name, 'sin_evento__SFX__123.wav')
            engine.extract(self.wem, self.source, self.out)
            self.assertEqual(command.call_count, 1)
        self.assertEqual(self.wem.read_bytes(), before)
        self.assertTrue((self.out / 'Audios_numericos').is_dir())
        self.assertTrue(all(p.is_file() and p.suffix == '.wav' for p in (self.out / 'Audios_numericos').iterdir()))
        self.assertFalse(list(self.out.rglob('work_*')))
        self.wem.write_bytes(before + b'changed')
        with self.assertRaises(ValueError):
            engine.extract(self.wem, self.source, self.out)

    def test_failure_has_no_completion_marker(self):
        engine = Extractor(self.tools)
        with patch.object(engine, 'command', side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):
                engine.extract(self.wem, self.source, self.out)
        states = list((self.out / '.loa_audio').glob('*.json'))
        self.assertEqual(len(states), 1)
        self.assertEqual(json.loads(states[0].read_text())['state'], 'in_progress')
        self.assertFalse(list(self.out.rglob('work_*')))
        self.assertFalse(list(self.out.rglob('*.partial.wav')))

    def test_decoded_wem_labels_and_legacy_resume(self):
        encoded = self.source / '333OWAHHICDIL5V88F9GF.wem'
        encoded.write_bytes(b'RIFFtest')
        engine = Extractor(self.tools)
        with patch.object(engine, 'command', side_effect=self.fake_command) as command:
            decoded = engine.extract(encoded, self.source, self.out)
            self.assertEqual(decoded['wavs'][0]['media_id'], '666957883')
            self.assertEqual(decoded['folder'], 'Audios_numericos')
            legacy_out = self.root / 'legacy'
            token = hashlib.sha256(str(encoded.relative_to(self.source)).encode()).hexdigest()[:12]
            old_job = legacy_out / 'paquetes' / (encoded.stem[:55] + '__' + token)
            old_job.mkdir(parents=True)
            self.fake_command(['-o', old_job / 'old.wav'], old_job, None)
            old_report = dict(input=decoded['input'], wav_count=1, wavs=[dict(wav='old.wav')])
            (old_job / 'completado.json').write_text(json.dumps(old_report))
            engine.extract(encoded, self.source, legacy_out)
            self.assertEqual(command.call_count, 1)
            self.assertEqual(len(list(legacy_out.rglob('completado.json'))), 1)

    def test_bad_header(self):
        self.wem.write_bytes(b'BAD!')
        with self.assertRaises(ValueError):
            Extractor(self.tools).extract(self.wem, self.source, self.out)

    def test_deleted_output_folder_recovers_without_catalog_and_keeps_known_event(self):
        engine = Extractor(self.tools)
        events = {('SFX', 'loose', '123'): 'known_song'}
        with patch.object(engine, 'command', side_effect=self.fake_command):
            report = engine.extract(self.wem, self.source, self.out, events=events)
        wav = self.out / report['wavs'][0]['wav']
        before = wav.read_bytes()
        wav.unlink()
        wav.parent.rmdir()
        with patch.object(engine, 'command', side_effect=self.fake_command) as command:
            report = engine.extract(self.wem, self.source, self.out)
            self.assertEqual(command.call_count, 1)
            engine.extract(self.wem, self.source, self.out)
            self.assertEqual(command.call_count, 1)
        self.assertEqual(report['state'], 'complete')
        self.assertEqual(report['wav_count'], 1)
        self.assertNotIn('missing_wavs', report)
        self.assertEqual(wav.read_bytes(), before)
        self.assertEqual(report['wavs'][0]['events'], 'known_song')

    def test_failed_missing_wav_recovery_is_resumable(self):
        engine = Extractor(self.tools)
        with patch.object(engine, 'command', side_effect=self.fake_command):
            report = engine.extract(self.wem, self.source, self.out)
        (self.out / report['wavs'][0]['wav']).unlink()
        with patch.object(engine, 'command', side_effect=RuntimeError('conversion failed')):
            with self.assertRaises(RuntimeError):
                engine.extract(self.wem, self.source, self.out)
        marker = next((self.out / '.loa_audio').glob('*.json'))
        pending = json.loads(marker.read_text())
        self.assertEqual(pending['state'], 'in_progress')
        self.assertEqual(len(pending['missing_wavs']), 1)
        with patch.object(engine, 'command', side_effect=self.fake_command):
            report = engine.extract(self.wem, self.source, self.out)
        self.assertEqual(report['state'], 'complete')
        self.assertNotIn('missing_wavs', report)

    def test_permission_error_does_not_mark_audio_missing(self):
        engine = Extractor(self.tools)
        with patch.object(engine, 'command', side_effect=self.fake_command):
            engine.extract(self.wem, self.source, self.out)
        marker = next((self.out / '.loa_audio').glob('*.json'))
        before = marker.read_bytes()
        with patch('core.wav_info', side_effect=PermissionError('locked')), \
                patch.object(engine, 'command') as command:
            with self.assertRaises(PermissionError):
                engine.extract(self.wem, self.source, self.out)
            command.assert_not_called()
        self.assertEqual(marker.read_bytes(), before)

    def test_pending_name_recovery_is_not_treated_as_deleted_audio(self):
        engine = Extractor(self.tools)
        with patch.object(engine, 'command', side_effect=self.fake_command):
            report = engine.extract(self.wem, self.source, self.out)
        marker = next((self.out / '.loa_audio').glob('*.json'))
        report['pending_name'] = {'old': report['wavs'][0]['wav']}
        engine.save_report(marker, report)
        with patch.object(engine, 'command') as command:
            with self.assertRaisesRegex(ValueError, 'renombrado pendiente'):
                engine.extract(self.wem, self.source, self.out)
            command.assert_not_called()

    def test_only_missing_package_media_are_converted(self):
        pck = self.source / 'SOUND_TEST.pck'
        pck.write_bytes(b'AKPKtest')
        engine = Extractor(self.tools)
        conversions = []
        media_ids = ['1', '2']
        def fake(args, cwd, log):
            if '-Y' in args:
                for mid in media_ids:
                    (Path(args[-1]) / (mid + '.wem')).write_bytes(b'RIFFtest')
            else:
                conversions.append(Path(args[-1]).stem)
                self.fake_command(args, cwd, log)
        with patch.object(engine, 'command', side_effect=fake):
            report = engine.extract(pck, self.source, self.out)
            first = self.out / report['wavs'][0]['wav']
            second = self.out / report['wavs'][1]['wav']
            preserved = (first.read_bytes(), first.stat().st_mtime_ns)
            second.unlink()
            media_ids[:] = ['1']
            with self.assertRaisesRegex(ValueError, 'medios pendientes'):
                engine.extract(pck, self.source, self.out)
            media_ids[:] = ['1', '2']
            restored = engine.extract(pck, self.source, self.out)
        self.assertEqual(conversions, ['1', '2', '2'])
        self.assertEqual((first.read_bytes(), first.stat().st_mtime_ns), preserved)
        self.assertTrue(second.is_file())
        self.assertEqual(restored['wav_count'], 2)

    def test_unpack_converts_all_media_and_names_only_dictionary_matches(self):
        pck = self.source / 'SOUND_TEST.pck'
        pck.write_bytes(b'AKPKtest')
        engine = Extractor(self.tools)
        def fake(args, cwd, log):
            if '-Y' in args:
                for mid in ('1', '2'):
                    (Path(args[-1]) / (mid + '.wem')).write_bytes(b'RIFFtest')
            else:
                self.fake_command(args, cwd, log)
        events = {('SFX', 'SOUND_TEST', '1'): 'known_music'}
        with patch.object(engine, 'command', side_effect=fake):
            report = engine.extract(pck, self.source, self.out, events=events)
        self.assertEqual(report['wav_count'], 2)
        self.assertEqual({Path(row['wav']).name for row in report['wavs']},
                         {'known_music__SFX__1.wav', 'sin_evento__SFX__2.wav'})
        self.assertTrue(all((self.out / row['wav']).is_file() for row in report['wavs']))

    def test_corrupt_existing_wav_is_not_silently_replaced(self):
        engine = Extractor(self.tools)
        with patch.object(engine, 'command', side_effect=self.fake_command):
            report = engine.extract(self.wem, self.source, self.out)
        wav = self.out / report['wavs'][0]['wav']
        wav.write_bytes(b'broken')
        with patch.object(engine, 'command') as command:
            with self.assertRaises((EOFError, wave.Error)):
                engine.extract(self.wem, self.source, self.out)
            command.assert_not_called()
        self.assertEqual(wav.read_bytes(), b'broken')

    def test_truncated_wav(self):
        wav = self.root / 'bad.wav'
        self.fake_command(['-o', wav], self.root, None)
        wav.write_bytes(wav.read_bytes()[:-5])
        with self.assertRaises(ValueError):
            wav_info(wav, full=True)

    def test_subprocess_cancellation(self):
        event = threading.Event()
        engine = Extractor(self.tools, cancel=event)
        timer = threading.Timer(.2, event.set)
        timer.start()
        try:
            with self.assertRaises(Cancelled):
                engine.command([sys.executable, '-c', 'import time; time.sleep(30)'],
                               self.root, self.root / 'cancel.log')
        finally:
            timer.cancel()

    def test_reject_external_source(self):
        outside = self.root / 'outside.wem'
        outside.write_bytes(b'RIFFtest')
        with self.assertRaises(ValueError):
            Extractor(self.tools).extract(outside, self.source, self.out)

    def test_same_name_in_different_folders(self):
        other = self.source / 'Korean' / self.wem.name
        other.parent.mkdir()
        other.write_bytes(self.wem.read_bytes())
        engine = Extractor(self.tools)
        with patch.object(engine, 'command', side_effect=self.fake_command):
            engine.extract(self.wem, self.source, self.out)
            engine.extract(other, self.source, self.out)
        self.assertEqual(len(list((self.out / '.loa_audio').glob('*.json'))), 2)
        self.assertEqual(len(list((self.out / 'Audios_numericos').glob('*.wav'))), 2)
        self.assertEqual(len(list((self.out / 'Audios_numericos').iterdir())), 2)

    def test_pck_flattens_internal_folders_and_cleans_intermediates(self):
        pck = self.source / 'NV1OQ9OCBH9U2521OP359JOVONUGX5H.pck'
        pck.write_bytes(b'AKPKtest')
        engine = Extractor(self.tools)
        def fake(args, cwd, log):
            if '-Y' in args:
                for language in ('english', 'korean'):
                    media = Path(args[-1]) / 'nested' / language / '42.wem'
                    media.parent.mkdir(parents=True)
                    media.write_bytes(b'RIFFtest')
                (Path(args[-1]) / 'bank.bnk').write_bytes(b'bank')
            else:
                self.fake_command(args, cwd, log)
        with patch.object(engine, 'command', side_effect=fake):
            result = engine.extract(pck, self.source, self.out)
        folder = self.out / 'SOUND_BGM_PAPUNIKA_NONSTREAM'
        self.assertEqual(result['wav_count'], 2)
        self.assertEqual({p.name for p in folder.iterdir()},
                         {'sin_evento__SFX__42.wav', 'sin_evento__SFX__42_2.wav'})
        self.assertEqual(len(list(folder.iterdir())), 2)
        self.assertTrue(all(p.is_file() and p.suffix == '.wav' for p in folder.iterdir()))
        self.assertFalse(list(self.out.rglob('*.wem')))
        self.assertFalse(list(self.out.rglob('*.bnk')))
        self.assertFalse(list(self.out.rglob('work_*')))

    def test_cancel_cleans_partial_wav_then_retries(self):
        event = threading.Event()
        engine = Extractor(self.tools, cancel=event)
        def cancel_conversion(args, cwd, log):
            self.fake_command(args, cwd, log)
            event.set()
        with patch.object(engine, 'command', side_effect=cancel_conversion):
            with self.assertRaises(Cancelled):
                engine.extract(self.wem, self.source, self.out)
        self.assertFalse(list(self.out.rglob('*.wav')))
        self.assertFalse(list(self.out.rglob('work_*')))
        event.clear()
        with patch.object(engine, 'command', side_effect=self.fake_command):
            report = engine.extract(self.wem, self.source, self.out)
        self.assertEqual(report['state'], 'complete')
        self.assertEqual(len(list((self.out / 'Audios_numericos').iterdir())), 1)

    def test_numeric_prefixes_share_folder_but_named_files_keep_their_name(self):
        engine = Extractor(self.tools)
        with patch.object(engine, 'command', side_effect=self.fake_command):
            for name, expected in [('123', 'Audios_numericos'), ('456', 'Audios_numericos'),
                                   ('7voice', 'Audios_numericos'), ('voice7', 'voice7')]:
                with self.subTest(name=name):
                    path = self.source / (name + '.wem')
                    path.write_bytes(b'RIFFtest')
                    result = engine.extract(path, self.source, self.out)
                    self.assertEqual(result['folder'], expected)
        numeric = list((self.out / 'Audios_numericos').iterdir())
        self.assertEqual(len(numeric), 3)
        self.assertTrue(all(p.is_file() and p.suffix == '.wav' for p in numeric))
        self.assertEqual(len(list((self.out / 'voice7').iterdir())), 1)
        self.assertFalse((self.out / '123').exists())
        self.assertFalse((self.out / '456').exists())

    def test_identical_names_from_other_sources_get_simple_counter(self):
        first = self.source / 'a' / '123.wem'
        second = self.source / 'b' / '123.wem'
        first.parent.mkdir()
        second.parent.mkdir()
        first.write_bytes(b'RIFFtest')
        second.write_bytes(b'RIFFtest')
        engine = Extractor(self.tools)
        with patch.object(engine, 'command', side_effect=self.fake_command):
            one = engine.extract(first, first.parent, self.out)
            two = engine.extract(second, second.parent, self.out)
            engine.extract(first, first.parent, self.out)
            engine.extract(second, second.parent, self.out)
        self.assertEqual(Path(one['wavs'][0]['wav']).name, 'sin_evento__SFX__123.wav')
        self.assertEqual(Path(two['wavs'][0]['wav']).name, 'sin_evento__SFX__123_2.wav')
        self.assertEqual(len(list((self.out / 'Audios_numericos').iterdir())), 2)

    def test_existing_v11_folder_is_reused_without_moving_audio(self):
        metadata = self.out / '.loa_audio'
        metadata.mkdir(parents=True)
        folder = self.out / '123'
        folder.mkdir()
        wav = folder / 'old.wav'
        self.fake_command(['-o', wav], folder, None)
        stat = self.wem.stat()
        report = dict(schema_version=2, state='complete',
                      input=dict(source=str(self.wem.resolve()), bytes=stat.st_size, modified=stat.st_mtime_ns),
                      folder='123', wav_count=1,
                      wavs=[dict(wav='123/old.wav', frames=80, media_source='123.wem')])
        token = hashlib.sha256(str(self.wem.resolve()).casefold().encode()).hexdigest()[:16]
        (metadata / (token + '.json')).write_text(json.dumps(report))
        engine = Extractor(self.tools)
        with patch.object(engine, 'command') as command:
            self.assertEqual(engine.extract(self.wem, self.source, self.out), report)
            command.assert_not_called()
        self.assertTrue(wav.is_file())
        self.assertFalse((self.out / 'Audios_numericos').exists())

    def test_untracked_audio_is_not_overwritten(self):
        engine = Extractor(self.tools)
        with patch.object(engine, 'command', side_effect=self.fake_command):
            report = engine.extract(self.wem, self.source, self.out)
        manifest = next((self.out / '.loa_audio').glob('*.json'))
        manifest.unlink()
        wav = self.out / report['wavs'][0]['wav']
        before = wav.read_bytes()
        with self.assertRaises(ValueError):
            engine.extract(self.wem, self.source, self.out)
        self.assertEqual(wav.read_bytes(), before)

    def test_partial_package_retry_reuses_completed_audio(self):
        pck = self.source / 'SOUND_TEST.pck'
        pck.write_bytes(b'AKPKtest')
        engine = Extractor(self.tools)
        conversions = []
        fail = [True]
        def fake(args, cwd, log):
            if '-Y' in args:
                for mid in ('1', '2'):
                    (Path(args[-1]) / (mid + '.wem')).write_bytes(b'RIFFtest')
            else:
                mid = Path(args[-1]).stem
                conversions.append(mid)
                if mid == '2' and fail[0]:
                    fail[0] = False
                    raise RuntimeError('interrupted second media')
                self.fake_command(args, cwd, log)
        with patch.object(engine, 'command', side_effect=fake):
            with self.assertRaises(RuntimeError):
                engine.extract(pck, self.source, self.out)
            self.assertEqual(len(list((self.out / 'SOUND_TEST').iterdir())), 1)
            self.assertFalse(list(self.out.rglob('work_*')))
            report = engine.extract(pck, self.source, self.out)
        self.assertEqual(conversions, ['1', '2', '2'])
        self.assertEqual(report['wav_count'], 2)
        self.assertEqual(len(list((self.out / 'SOUND_TEST').iterdir())), 2)


if __name__ == '__main__':
    unittest.main()
