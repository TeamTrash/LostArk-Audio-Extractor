import json
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from core import Cancelled, Extractor, TOOL_KEYS, file_digest
from repair_names import repair_output


class FormatTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.wem = self.source / '123.wem'
        self.wem.write_bytes(b'RIFFtest')
        self.out = self.root / 'out'
        self.engine = Extractor({k: __file__ for k in TOOL_KEYS})
        self.commands = []

    def fake(self, args, cwd, log):
        self.commands.append(args)
        if '-o' in args:
            with wave.open(str(args[args.index('-o') + 1]), 'wb') as stream:
                stream.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
                stream.writeframes(b'\x01\x00' * 800)
        elif args[-1] != '-':
            Path(args[-1]).write_bytes(b'ID3test-encoded-MP3')

    def extract(self, mode):
        with patch.object(self.engine, 'command', side_effect=self.fake):
            return self.engine.extract(self.wem, self.source, self.out, output_format=mode)

    def test_mp3_only_has_own_manifest_and_no_published_wav(self):
        report = self.extract('mp3')
        self.assertEqual(report['schema_version'], 3)
        self.assertEqual(report['output_format'], 'mp3')
        self.assertEqual(report['folder'], '123__123')
        self.assertEqual(len(list(self.out.rglob('*.mp3'))), 1)
        self.assertFalse(list(self.out.rglob('*.wav')))
        self.assertFalse(list(self.out.rglob('work_*')))
        self.assertEqual(len(self.commands), 3)  # decode, encode, verify decode
        self.extract('mp3')
        self.assertEqual(len(self.commands), 3)

    def test_both_reuses_wav_and_modes_resume_independently(self):
        report = self.extract('both')
        self.assertEqual(len(report['wavs']), 2)
        self.assertEqual(len([c for c in self.commands if '-o' in c]), 1)
        wav = next(self.out.rglob('*.wav'))
        mp3 = next(self.out.rglob('*.mp3'))
        self.assertEqual(wav.stem, mp3.stem)
        self.assertEqual(wav.parent, mp3.parent)
        before = (wav.read_bytes(), wav.stat().st_mtime_ns)
        self.extract('wav')
        self.extract('mp3')
        self.assertEqual(len(self.commands), 3)
        mp3.unlink()
        self.extract('mp3')
        self.assertEqual(len(self.commands), 5)
        self.assertEqual((wav.read_bytes(), wav.stat().st_mtime_ns), before)
        self.assertTrue(mp3.is_file())
        self.assertEqual(len(list((self.out / '.loa_audio').glob('*.json'))), 2)

    def test_encoding_failure_preserves_wav_then_retries_without_decode(self):
        self.extract('wav')
        with patch.object(self.engine, 'command', side_effect=RuntimeError('encoding failed')):
            with self.assertRaises(RuntimeError):
                self.engine.extract(self.wem, self.source, self.out, output_format='mp3')
        self.assertEqual(len(list(self.out.rglob('*.wav'))), 1)
        self.assertFalse(list(self.out.rglob('*.mp3')))
        self.assertFalse(list(self.out.rglob('work_*')))
        self.extract('mp3')
        self.assertEqual(len([c for c in self.commands if '-o' in c]), 1)

    def test_modified_mp3_refused(self):
        self.extract('mp3')
        path = next(self.out.rglob('*.mp3'))
        path.write_bytes(b'ID3modified-MP3-data')
        with self.assertRaisesRegex(ValueError, 'MP3 modificado'):
            self.extract('mp3')

    def test_cancel_during_encode_leaves_no_mp3_or_intermediates(self):
        def cancel(args, cwd, log):
            self.fake(args, cwd, log)
            if args[-1] != '-' and '-o' not in args:
                self.engine.cancel.set()
        with patch.object(self.engine, 'command', side_effect=cancel):
            with self.assertRaises(Cancelled):
                self.engine.extract(self.wem, self.source, self.out, output_format='mp3')
        self.assertFalse(list(self.out.rglob('*.mp3')))
        self.assertFalse(list(self.out.rglob('*.wav')))
        self.assertFalse(list(self.out.rglob('work_*')))

    def test_mp3_name_repair_preserves_bytes_and_resume(self):
        self.extract('mp3')
        old = next(self.out.rglob('*.mp3'))
        digest = file_digest(old)
        summary = repair_output(self.out, {('SFX', 'loose', '123'): 'known_song'}, apply=True)
        self.assertEqual(summary['renamed'], 1)
        new = old.with_name('known_song__SFX__123.mp3')
        self.assertEqual(file_digest(new), digest)
        self.extract('mp3')
        self.assertEqual(len(self.commands), 3)

    def test_untracked_mp3_not_overwritten(self):
        self.extract('mp3')
        for marker in (self.out / '.loa_audio').glob('*.json'):
            marker.unlink()
        with self.assertRaisesRegex(ValueError, 'no registrado'):
            self.extract('mp3')

    def test_ffmpeg_optional_for_wav_required_before_both(self):
        tools = {k: __file__ for k in TOOL_KEYS if k != 'ffmpeg'}
        engine = Extractor(tools)
        with self.assertRaisesRegex(ValueError, 'FFmpeg'):
            engine.extract(self.wem, self.source, self.out, output_format='both')
        self.assertFalse(self.out.exists())
