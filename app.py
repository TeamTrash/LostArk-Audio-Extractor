# SPDX-License-Identifier: MIT
"""Tk desktop interface. Python 3.10+ / Windows, standard library only."""
import argparse
import json
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core import Cancelled, Extractor, TOOL_KEYS, inventory, load_names, validate_paths
from name_decoder import audio_name
from repair_names import repair_output
from version import __version__

HERE = Path(__file__).resolve().parent


def config_path():
    home = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else HERE
    return home / 'config.local.json'


CONFIG = config_path()
TOOL_PATHS = dict(lautool='LAUTool_0.3/LAUTool_steam.exe',
                  quickbms='quickbms/bin/quickbms.exe',
                  script='quickbms/wwise_pck_extractor.bms',
                  vgmstream='vgmstream/bin/vgmstream-cli.exe',
                  ffmpeg='ffmpeg/ffmpeg.exe')


def defaults():
    paths = {key: HERE / 'tools' / relative for key, relative in TOOL_PATHS.items()}
    for key in paths:
        bundled = HERE / 'tools' / paths[key].name
        if not paths[key].is_file() and bundled.is_file():
            paths[key] = bundled
    return {k: str(p) if p.is_file() else '' for k, p in paths.items()}


def load_settings():
    settings = defaults()
    try:
        saved = json.loads(CONFIG.read_text(encoding='utf-8'))
        if not isinstance(saved, dict):
            return settings
    except (ValueError, OSError):
        return settings
    for key, value in saved.items():
        if key in ('source', 'output') or not isinstance(value, str):
            continue
        if key in TOOL_KEYS:
            legacy = value.replace('\\', '/').casefold().endswith(
                '/tools/audio_converters/' + TOOL_PATHS[key].casefold())
            candidate = (HERE / value).resolve() if value else None
            if settings[key] and (legacy or candidate is None or not candidate.is_file()):
                continue
            value = str(candidate) if candidate is not None else ''
        settings[key] = value
    return settings


def portable_settings(settings):
    saved = {key: value for key, value in settings.items() if key not in ('source', 'output')}
    for key in TOOL_KEYS:
        if saved.get(key):
            path = Path(saved[key]).resolve()
            if path.is_relative_to((HERE / 'tools').resolve()):
                saved[key] = path.relative_to(HERE.resolve()).as_posix()
    return saved


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'Lost Ark Audio Extractor {__version__}')
        self.app_icon = tk.PhotoImage(file=str(HERE / 'assets' / 'app.png'))
        self.iconphoto(True, self.app_icon)
        self.apply_theme()
        self.geometry('1080x760')
        self.minsize(820, 620)
        self.messages = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.closing = False
        self.files = []
        self.scan_root = None
        self.names = {}
        self.sort_column = None
        self.sort_descending = False
        self.file_sizes = {}
        self.headings = {'name': 'Nombre desofuscado', 'path': 'Carpeta / archivo original', 'size': 'Tamaño'}
        saved = load_settings()
        self.vars = {k: tk.StringVar(value=saved.get(k, '')) for k in
                     ('source', 'output', 'inventory', 'catalog', 'output_format', 'title_language', 'title_only', *TOOL_KEYS)}
        if self.vars['title_language'].get() not in ('Español', 'Inglés', 'Coreano'):
            self.vars['title_language'].set('Español')
        if self.vars['output_format'].get() not in ('WAV', 'MP3', 'WAV + MP3'):
            self.vars['output_format'].set('WAV')
        self.search = tk.StringVar()
        self.status = tk.StringVar(value='Listo')
        self.controls = []
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        tabs = ttk.Notebook(self)
        tabs.grid(row=0, column=0, sticky='nsew', padx=12, pady=12)
        self.main = ttk.Frame(tabs, padding=12)
        settings = ttk.Frame(tabs, padding=12)
        tabs.add(self.main, text='Audios')
        tabs.add(settings, text='Herramientas y nombres')
        for frame in (self.main, settings):
            frame.columnconfigure(1, weight=1)
        self.path_row(self.main, 0, 'Carpeta de audios', 'source', directory=True)
        self.path_row(self.main, 1, 'Destino', 'output', directory=True)
        bar = ttk.Frame(self.main)
        bar.grid(row=2, column=0, columnspan=3, sticky='ew', pady=10)
        self.button(bar, 'Buscar archivos', self.scan).pack(side='left')
        ttk.Label(bar, text='Filtro').pack(side='left', padx=(18, 6))
        ttk.Entry(bar, textvariable=self.search).pack(side='left', fill='x', expand=True)
        ttk.Label(bar, text='Formato').pack(side='left', padx=(12, 6))
        self.output_selector = ttk.Combobox(bar, textvariable=self.vars['output_format'],
                                           values=('WAV', 'MP3', 'WAV + MP3'), state='readonly', width=13)
        self.output_selector.pack(side='left')
        self.controls.append(self.output_selector)
        title_bar = ttk.Frame(self.main)
        title_bar.grid(row=8, column=0, columnspan=3, sticky='ew', pady=(8, 0))
        ttk.Label(title_bar, text='Idioma de los nombres').pack(side='left', padx=(0, 8))
        self.title_selector = ttk.Combobox(title_bar, textvariable=self.vars['title_language'],
            values=('Español', 'Inglés', 'Coreano'), state='readonly', width=11)
        self.title_selector.pack(side='left')
        self.controls.append(self.title_selector)
        title_option = ttk.Checkbutton(self.main, text='Solo nombre descriptivo',
            variable=self.vars['title_only'], onvalue='1', offvalue='0')
        title_option.grid(row=9, column=0, columnspan=3, sticky='w', pady=(4, 0))
        self.controls.append(title_option)
        ttk.Label(title_bar, text='  Sin título traducido: nombre técnico. Coreano sin títulos locales.').pack(side='left')
        self.search.trace_add('write', lambda *_: self.render())
        table_frame = ttk.Frame(self.main)
        table_frame.grid(row=3, column=0, columnspan=3, sticky='nsew')
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.main.rowconfigure(3, weight=1)
        self.table = ttk.Treeview(table_frame, columns=('name', 'path', 'size'), show='headings', selectmode='extended')
        for key, title, width in [('name', 'Nombre desofuscado', 260), ('path', 'Carpeta / archivo original', 430), ('size', 'Tamaño', 120)]:
            self.table.heading(key, text=title, command=lambda column=key: self.sort_by(column))
            self.table.column(key, width=width, minwidth=60)
        self.table.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.table.configure(yscrollcommand=scrollbar.set)
        actions = ttk.Frame(self.main)
        actions.grid(row=4, column=0, columnspan=3, sticky='ew', pady=10)
        self.button(actions, 'Seleccionar visibles', lambda: self.table.selection_set(self.table.get_children())).pack(side='left')
        self.button(actions, 'Extraer seleccion', self.start).pack(side='left', padx=8)
        self.stop = ttk.Button(actions, text='Cancelar', command=self.cancel.set, state='disabled')
        self.stop.pack(side='left')
        self.button(actions, 'Abrir destino', self.open_output).pack(side='right')
        self.button(self.main, 'Actualizar nombres del destino', self.repair_names).grid(
            row=7, column=0, columnspan=3, sticky='w', pady=(8, 0))
        self.progress = ttk.Progressbar(self.main, mode='determinate')
        self.progress.grid(row=5, column=0, columnspan=3, sticky='ew')
        self.log = tk.Text(self.main, height=8, state='disabled', wrap='word',
                           background='#FFFFFF', foreground='#243D38',
                           selectbackground='#CBE7DF', selectforeground='#173D33',
                           relief='flat', highlightthickness=1, highlightbackground='#CCDCD6',
                           padx=10, pady=8, font=('Consolas', 9))
        self.log.grid(row=6, column=0, columnspan=3, sticky='ew', pady=(8, 0))
        labels = [('lautool', 'LAUTool Steam (.exe)'), ('quickbms', 'QuickBMS (.exe)'),
                  ('script', 'Extractor Wwise (.bms)'), ('vgmstream', 'vgmstream-cli (.exe)'),
                  ('ffmpeg', 'FFmpeg (.exe, para MP3 a 320 kbps)'),
                  ('inventory', 'Inventario de nombres (.csv, opcional)'), ('catalog', 'Catalogo de eventos (.csv, opcional)')]
        for i, (key, label) in enumerate(labels):
            self.path_row(settings, i, label, key)
        self.button(settings, 'Verificar herramientas', self.verify).grid(row=7, column=1, sticky='w', pady=12)
        ttk.Label(self, textvariable=self.status, anchor='w').grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 8))
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(100, self.poll)

    def apply_theme(self):
        self.configure(background='#F0F5F3')
        style = ttk.Style(self)
        style.theme_use('clam')
        # Keep keyboard focus visible through color, without dotted focus elements.
        def without_focus(layout):
            result = []
            for element, options in layout:
                options = dict(options)
                children = without_focus(options.pop('children', []))
                if element.endswith('.focus'):
                    result.extend(children)
                else:
                    if children:
                        options['children'] = children
                    result.append((element, options))
            return result
        for widget_style in ('TButton', 'TNotebook.Tab'):
            style.layout(widget_style, without_focus(style.layout(widget_style)))
        style.configure('.', font=('Segoe UI', 10), background='#F0F5F3',
                        foreground='#243D38', bordercolor='#CCDCD6',
                        lightcolor='#F0F5F3', darkcolor='#CCDCD6')
        style.configure('TButton', background='#E0ECE7', padding=(10, 6), relief='flat')
        style.map('TButton', background=[('disabled', '#EDF1EF'), ('pressed', '#BBD6CB'),
                                       ('active', '#CFE2D9'), ('focus', '#CFE2D9')],
                  foreground=[('disabled', '#7B8C86')])
        style.configure('Accent.TButton', background='#286B58', foreground='#FFFFFF')
        style.map('Accent.TButton', background=[('disabled', '#DCE5E1'),
                    ('pressed', '#194A3C'), ('active', '#337E68'), ('focus', '#337E68')],
                  foreground=[('disabled', '#7B8C86'), ('!disabled', '#FFFFFF')])
        style.configure('TEntry', fieldbackground='#FFFFFF', padding=5)
        style.configure('Browse.TButton', font=('Segoe UI', 9), padding=(8, 3))
        style.configure('TCombobox', padding=5, arrowsize=14)
        style.map('TCombobox', fieldbackground=[('readonly', '#FFFFFF')],
                  foreground=[('disabled', '#7B8C86'), ('readonly', '#243D38')],
                  selectbackground=[('readonly', '#FFFFFF')],
                  selectforeground=[('readonly', '#243D38')])
        style.configure('TNotebook', borderwidth=0)
        style.configure('TNotebook.Tab', padding=(14, 8), background='#E0ECE7')
        style.map('TNotebook.Tab', background=[('selected', '#BFD5CA'), ('active', '#D3E3DB')],
                  foreground=[('selected', '#173D33')],
                  font=[('selected', ('Segoe UI', 11, 'bold'))],
                  padding=[('selected', (18, 10))])
        style.configure('Treeview', background='#FFFFFF', fieldbackground='#FFFFFF',
                        rowheight=29, borderwidth=0)
        style.configure('Treeview.Heading', background='#DFEBE5', foreground='#284C40',
                        font=('Segoe UI', 10, 'bold'), padding=(8, 8), relief='flat')
        style.map('Treeview.Heading', background=[('active', '#CFE2D9')])
        style.map('Treeview', background=[('selected', '#CBE7DF')],
                  foreground=[('selected', '#173D33')])
        style.configure('Horizontal.TProgressbar', background='#43866B',
                        troughcolor='#E0ECE7', borderwidth=0)
        self.option_add('*TCombobox*Listbox.background', '#FFFFFF')
        self.option_add('*TCombobox*Listbox.foreground', '#243D38')
        self.option_add('*TCombobox*Listbox.selectBackground', '#CBE7DF')
        self.option_add('*TCombobox*Listbox.selectForeground', '#173D33')

    def button(self, frame, text, command):
        button = ttk.Button(frame, text=text, command=command)
        if text == 'Extraer seleccion':
            button.configure(style='Accent.TButton')
        self.controls.append(button)
        return button

    def path_row(self, frame, row, label, key, directory=False):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=(0, 8), pady=5)
        entry = ttk.Entry(frame, textvariable=self.vars[key])
        entry.grid(row=row, column=1, sticky='ew')
        self.controls.append(entry)
        def choose():
            path = filedialog.askdirectory() if directory else filedialog.askopenfilename()
            if path:
                self.vars[key].set(path)
        browse = self.button(frame, 'Examinar...', choose)
        browse.configure(style='Browse.TButton')
        browse.grid(row=row, column=2, padx=(8, 0), pady=5)

    def save(self):
        saved = portable_settings({k: v.get() for k, v in self.vars.items()})
        CONFIG.write_text(json.dumps(saved, indent=2), encoding='utf-8')

    def verify(self):
        try:
            engine = Extractor({k: self.vars[k].get() for k in TOOL_KEYS})
            if self.vars['output_format'].get() != 'WAV' and not engine.tools['ffmpeg'].is_file():
                raise ValueError('Configura FFmpeg para exportar MP3.')
            self.save()
            messagebox.showinfo('Herramientas', 'Herramientas disponibles para el formato elegido. La compatibilidad se valida al extraer.')
        except Exception as e:
            messagebox.showerror('Herramientas', str(e))

    def launch(self, function):
        self.busy = True
        self.cancel.clear()
        for control in self.controls:
            control.configure(state='disabled')
        self.stop.configure(state='normal')
        def worker():
            try:
                function()
            except Cancelled:
                self.messages.put(('log', 'Cancelado. Se conservan los audios validados y se eliminan los temporales.'))
            except Exception as e:
                self.messages.put(('error', str(e)))
            finally:
                self.messages.put(('done', None))
        threading.Thread(target=worker, daemon=False).start()

    def scan(self):
        try:
            root = Path(self.vars['source'].get()).resolve()
            if not self.vars['source'].get() or not root.is_dir():
                raise ValueError('Selecciona la carpeta WwiseAudioPackage o una carpeta de muestras.')
            self.save()
            inv, cat = self.vars['inventory'].get(), self.vars['catalog'].get()
            def work():
                names, _ = load_names(inv, cat)
                files = inventory(root, self.cancel)
                self.messages.put(('files', (root, files, names)))
            self.status.set('Buscando PCK/WEM en la carpeta seleccionada...')
            self.launch(work)
        except Exception as e:
            messagebox.showerror('Origen', str(e))

    def render(self):
        self.table.delete(*self.table.get_children())
        self.file_sizes.clear()
        query = self.search.get().lower()
        for i, path in enumerate(self.files):
            name = audio_name(path, self.names)
            relative = str(path.relative_to(self.scan_root))
            if query in (name + ' ' + relative).lower():
                try:
                    self.file_sizes[str(i)] = path.stat().st_size
                    size = f'{(self.file_sizes[str(i)] + 500) // 1_000:,}'.replace(',', '.') + ' KB'
                except OSError:
                    self.file_sizes[str(i)] = None
                    size = '?'
                self.table.insert('', 'end', iid=str(i), values=(name, relative, size))
        self.apply_sort()

    def sort_by(self, column):
        self.sort_descending = not self.sort_descending if self.sort_column == column else False
        self.sort_column = column
        self.apply_sort()

    def apply_sort(self):
        if self.sort_column is None:
            return
        items = list(self.table.get_children())
        if self.sort_column == 'size':
            known = [iid for iid in items if self.file_sizes[iid] is not None]
            unknown = [iid for iid in items if self.file_sizes[iid] is None]
            items = sorted(known, key=self.file_sizes.get, reverse=self.sort_descending) + unknown
        else:
            items.sort(key=lambda iid: self.table.set(iid, self.sort_column).casefold(),
                       reverse=self.sort_descending)
        # Keep stable row IDs: extraction maps each ID to self.files, not visual order.
        for position, iid in enumerate(items):
            self.table.move(iid, '', position)
        for column, title in self.headings.items():
            marker = (' \u25bc' if self.sort_descending else ' \u25b2') if column == self.sort_column else ''
            self.table.heading(column, text=title + marker)

    def start(self):
        try:
            selected = [self.files[int(i)] for i in self.table.selection()]
            if not selected:
                raise ValueError('Selecciona al menos un archivo.')
            if not self.vars['output'].get():
                raise ValueError('Selecciona una carpeta de destino.')
            source, output = validate_paths(self.vars['source'].get(), self.vars['output'].get())
            if source != self.scan_root:
                raise ValueError('El origen cambio; vuelve a buscar archivos.')
            emit = lambda s: self.messages.put(('log', s))
            engine = Extractor({k: self.vars[k].get() for k in TOOL_KEYS}, self.cancel, emit)
            output_format = {'WAV': 'wav', 'MP3': 'mp3', 'WAV + MP3': 'both'}[self.vars['output_format'].get()]
            if output_format != 'wav' and not engine.tools['ffmpeg'].is_file():
                raise ValueError('Configura FFmpeg para exportar MP3.')
            names, events = load_names(self.vars['inventory'].get(), self.vars['catalog'].get(),
                {'Español': 'es', 'Inglés': 'en', 'Coreano': 'ko'}[self.vars['title_language'].get()],
                title_only=self.vars['title_only'].get() == '1')
            emit(f'Catalogo: {len(events)} asociaciones cargadas.' if events else
                 'Sin catalogo de eventos: los audios saldran como sin_evento + ID.')
            self.save()
            self.progress.configure(maximum=len(selected), value=0)
            def work():
                failed = 0
                for i, path in enumerate(selected, 1):
                    if self.cancel.is_set():
                        raise Cancelled()
                    try:
                        engine.extract(path, source, output, names, events, output_format)
                    except Cancelled:
                        raise
                    except Exception as e:
                        failed += 1
                        emit(f'ERROR {path.name}: {e}')
                    self.messages.put(('progress', i))
                emit(f'Terminado: {len(selected) - failed} archivos fuente completados; {failed} errores.')
            self.launch(work)
        except Exception as e:
            messagebox.showerror('Extraccion', str(e))

    def repair_names(self):
        try:
            if not self.vars['output'].get():
                raise ValueError('Selecciona una carpeta de destino.')
            output = Path(self.vars['output'].get()).resolve()
            _, events = load_names(catalog_csv=self.vars['catalog'].get(),
                title_language={'Español': 'es', 'Inglés': 'en', 'Coreano': 'ko'}[self.vars['title_language'].get()],
                title_only=self.vars['title_only'].get() == '1')
            if not events:
                raise ValueError('Selecciona CATALOGO.csv en Herramientas y nombres.')
            if not messagebox.askyesno('Actualizar nombres',
                    'Renombrar WAV/MP3 registrados con eventos conocidos en el destino, sin reconvertir audio?'):
                return
            self.launch(lambda: repair_output(output, events, apply=True, cancel=self.cancel,
                                             emit=lambda s: self.messages.put(('log', s))))
        except Exception as e:
            messagebox.showerror('Nombres', str(e))

    def open_output(self):
        path = Path(self.vars['output'].get())
        if self.vars['output'].get() and path.is_dir():
            os.startfile(path)

    def poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind in ('log', 'error'):
                    self.log.configure(state='normal')
                    self.log.insert('end', value + '\n')
                    self.log.see('end')
                    self.log.configure(state='disabled')
                    self.status.set(value[:120])
                elif kind == 'files':
                    self.scan_root, self.files, self.names = value
                    self.render()
                    self.status.set(f'{len(self.files)} archivos encontrados')
                elif kind == 'progress':
                    self.progress.configure(value=value)
                elif kind == 'done':
                    self.busy = False
                    for control in self.controls:
                        control.configure(state='normal')
                    self.output_selector.configure(state='readonly')
                    self.title_selector.configure(state='readonly')
                    self.stop.configure(state='disabled')
                    if self.closing:
                        self.destroy()
                        return
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def close(self):
        if self.busy:
            if messagebox.askyesno('Salir', 'Cancelar el trabajo actual y cerrar?'):
                self.closing = True
                self.cancel.set()
        else:
            self.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Lost Ark Audio Extractor')
    parser.add_argument('--version', action='version', version=__version__)
    parser.parse_args()
    App().mainloop()
