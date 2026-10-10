import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import App


class TableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App()
        cls.app.withdraw()

    @classmethod
    def tearDownClass(cls):
        for timer in cls.app.tk.splitlist(cls.app.tk.call('after', 'info')):
            cls.app.after_cancel(timer)
        cls.app.destroy()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.app.files = []
        for name, size in [('z/Beta.wem', 10), ('a/alpha.wem', 2), ('m/Gamma.wem', 3)]:
            path = root / name
            path.parent.mkdir()
            path.write_bytes(b'x' * size)
            self.app.files.append(path)
        self.app.scan_root = root
        self.app.names = {}
        self.app.sort_column = None
        self.app.sort_descending = False
        self.app.search.set('')
        self.app.render()

    def order(self):
        return list(self.app.table.get_children())

    def test_repair_uses_destination_without_source_or_converters(self):
        self.app.vars['source'].set('')
        self.app.vars['output'].set(self.temp.name)
        events = {('SFX', 'loose', '123'): 'song'}
        with patch('app.load_names', return_value=({}, events)), \
                patch('app.messagebox.askyesno', return_value=True), \
                patch('app.repair_output') as repair, \
                patch.object(self.app, 'launch', side_effect=lambda work: work()):
            self.app.repair_names()
        repair.assert_called_once()
        self.assertEqual(repair.call_args.args, (Path(self.temp.name).resolve(), events))
        self.assertTrue(repair.call_args.kwargs['apply'])

    def test_header_callback_and_numeric_precision(self):
        callback = self.app.table.heading('size', 'command')
        self.app.tk.call(callback)
        self.assertEqual(self.order(), ['1', '2', '0'])
        self.assertTrue(self.app.table.heading('size', 'text').endswith('\u25b2'))
        self.app.tk.call(callback)
        self.assertEqual(self.order(), ['0', '2', '1'])
        self.assertTrue(self.app.table.heading('size', 'text').endswith('\u25bc'))

    def test_size_display_in_kb(self):
        self.app.files[0].write_bytes(b'x' * 1250)
        self.app.render()
        self.assertEqual(self.app.table.set('0', 'size'), '1.25 KB')
        self.app.sort_by('size')
        self.assertTrue(self.app.table.heading('size', 'text').startswith('KB'))
        self.assertEqual(self.order(), ['1', '2', '0'])

    def test_text_columns_toggle_independently(self):
        self.app.sort_by('name')
        self.assertEqual(self.order(), ['1', '0', '2'])
        self.app.sort_by('name')
        self.assertEqual(self.order(), ['2', '0', '1'])
        self.app.sort_by('path')
        self.assertEqual(self.order(), ['1', '2', '0'])
        self.assertEqual(self.app.table.heading('name', 'text'), 'Nombre desofuscado')
        self.app.sort_by('path')
        self.assertEqual(self.order(), ['0', '2', '1'])

    def test_selection_still_points_to_same_file(self):
        self.app.table.selection_set('0', '2')
        before = {self.app.files[int(i)] for i in self.app.table.selection()}
        self.app.table.focus('2')
        self.app.sort_by('size')
        self.assertEqual({self.app.files[int(i)] for i in self.app.table.selection()}, before)
        self.assertEqual(self.app.table.focus(), '2')

    def test_filter_preserves_sort(self):
        self.app.sort_by('size')
        self.app.sort_by('size')
        self.app.search.set('Beta')
        self.assertEqual(self.order(), ['0'])
        self.app.search.set('')
        self.assertEqual(self.order(), ['0', '2', '1'])

    def test_decoded_name_search_keeps_original_path(self):
        path = self.app.scan_root / 'NV1OQ9OCBH9U2521OP359JOVONUGX5H.pck'
        path.write_bytes(b'x')
        self.app.files = [path]
        self.app.search.set('papunika')
        self.assertEqual(self.order(), ['0'])
        self.assertEqual(self.app.table.set('0', 'name'), 'SOUND_BGM_PAPUNIKA_NONSTREAM')
        self.assertEqual(self.app.table.set('0', 'path'), path.name)

    def test_missing_size_last_in_both_directions(self):
        self.app.files[2].unlink()
        self.app.render()
        self.app.sort_by('size')
        self.assertEqual(self.order(), ['1', '0', '2'])
        self.app.sort_by('size')
        self.assertEqual(self.order(), ['0', '1', '2'])
