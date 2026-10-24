# SPDX-License-Identifier: MIT
"""Windows executable entry point and opt-in packaged-runtime diagnostics."""
import argparse
import json
import sys
import traceback
from pathlib import Path

from app import App, CONFIG, defaults
from core import Extractor, load_names
from version import __version__


def self_test(report_path, samples, output, output_format='wav'):
    report = dict(version=__version__, frozen=bool(getattr(sys, 'frozen', False)),
                  config_path=str(CONFIG), ok=False)
    window = None
    try:
        window = App()
        window.withdraw()
        window.update_idletasks()
        report['tk_version'] = window.tk.call('info', 'patchlevel')
        report['title'] = window.title()
        report['session_paths_empty'] = not any(window.vars[k].get() for k in ('source', 'output'))
        assert report['session_paths_empty']
        tools = defaults()
        engine = Extractor(tools)
        _, events = load_names()
        report['associations'] = len(events)
        report['descriptive_titles'] = len(events.titles)
        report['example_title'] = events.titles.get('bgm_jukebox_m235_2d_play')
        report['title_languages'] = {}
        for language in ('es', 'en', 'ko'):
            catalog = load_names(title_language=language)[1]
            report['title_languages'][language] = dict(count=len(catalog.titles),
                example=catalog.titles.get('bgm_jukebox_m235_2d_play'))
        report['tools_available'] = all(Path(p).is_file() for p in tools.values())
        report['samples'] = []
        for sample in samples:
            sample = sample.resolve()
            result = engine.extract(sample, sample.parent, output, events=events, output_format=output_format)
            report['samples'].append(dict(input=sample.name, wav_count=result['wav_count'],
                                          names=[Path(row['wav']).name for row in result['wavs']]))
        report['ok'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        if window is not None:
            for timer in window.tk.splitlist(window.tk.call('after', 'info')):
                window.after_cancel(timer)
            window.destroy()
        report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Lost Ark Audio Extractor ' + __version__)
    parser.add_argument('--self-test', type=Path, metavar='REPORT_JSON')
    parser.add_argument('--sample', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--format', choices=['wav', 'mp3', 'both'], default='wav')
    args = parser.parse_args()
    if args.self_test:
        if args.sample and args.output is None:
            parser.error('--sample requires --output')
        sys.exit(self_test(args.self_test, args.sample, args.output, args.format))
    App().mainloop()
