import unittest

from name_decoder import audio_name, deobfuscate


class NameTests(unittest.TestCase):
    def test_known_package(self):
        encoded = 'NV1OQ9OCBH9U2521OP359JOVONUGX5H'
        self.assertEqual(deobfuscate(encoded), 'SOUND_BGM_PAPUNIKA_NONSTREAM')
        self.assertEqual(audio_name(encoded + '.pck'), 'SOUND_BGM_PAPUNIKA_NONSTREAM')
        self.assertEqual(audio_name(encoded.lower() + '.PCK'), 'SOUND_BGM_PAPUNIKA_NONSTREAM')

    def test_known_wem(self):
        self.assertEqual(audio_name('333OWAHHICDIL5V88F9GF.wem'), '666957883')

    def test_readable_and_unknown_unchanged(self):
        for name in ('123.wem', 'SOUND_BGM_YORN.pck', 'voice_long_readable_name01.wem',
                     'AAAAAAAAAAAAAAAAAAAA1.pck'):
            self.assertEqual(audio_name(name), name.rsplit('.', 1)[0])

    def test_override_has_precedence(self):
        name = '333OWAHHICDIL5V88F9GF.wem'
        self.assertEqual(audio_name(name, {name.lower(): 'manual_label'}), 'manual_label')

    def test_empty_input(self):
        self.assertEqual(deobfuscate(''), '')
