"""Python adaptation of lostark-explorer's LostArkNameDeobfuscator.

Copyright (c) 2026 poyo (anon), MIT. See licenses/lostark-explorer-MIT.txt.
Source: LostArk.Archive.Core/NameObfuscation/LostArkNameDeobfuscator.cs
Only filename obfuscation is handled here, not archive/audio encryption.
"""
import re
from pathlib import Path

SUBSTITUTIONS = (
    ('QP', 'Q', 0), ('QD', 'Q', 1), ('QW', 'Q', 2), ('Q4', 'Q', 3),
    ('QL', '-', 0), ('QB', '-', 1), ('QO', '-', 2), ('Q5', '-', 3),
    ('QC', '_', 0), ('QN', '_', 1), ('QT', '_', 2), ('Q9', '_', 3),
    ('XU', 'X', 0), ('XN', 'X', 1), ('XH', 'X', 2), ('X3', 'X', 3),
    ('XW', '!', 0), ('XS', '!', 1), ('XZ', '!', 2), ('X0', '!', 3),
)


def deobfuscate(source):
    if not source or not source.strip():
        return source
    text = ''.join(source.split()).upper()
    mapped = []
    for char in text:
        value = ord(char) + (43 if '0' <= char <= '9' else 0)
        value = (31 * (value - len(text) - 65)) % 36 + 65
        mapped.append(chr(value - 43 if value >= 91 else value))
    text = ''.join(mapped)
    output = []
    i = 0
    while i < len(text):
        for pair, replacement, position in SUBSTITUTIONS:
            if i % 4 == position and text.startswith(pair, i):
                output.append(replacement)
                i += len(pair)
                break
        else:
            output.append(text[i])
            i += 1
    return ''.join(output).split('!', 1)[0]


def audio_name(path, overrides=None):
    path = Path(path)
    if overrides and path.name.lower() in overrides:
        return overrides[path.name.lower()]
    stem = path.stem
    # Apply the reference heuristic only to supported audio filenames; reject
    # implausible results rather than converting readable or unrelated names.
    if len(stem) < 20 or not re.fullmatch(r'[A-Za-z0-9]+', stem) or not re.search(r'[0-9]', stem):
        return stem
    decoded = deobfuscate(stem)
    if path.suffix.lower() == '.pck' and re.fullmatch(r'SOUND_[A-Z0-9_-]+', decoded):
        return decoded
    if path.suffix.lower() == '.wem' and re.fullmatch(r'[0-9]{1,10}', decoded) and int(decoded) <= 0xffffffff:
        return decoded
    return stem
