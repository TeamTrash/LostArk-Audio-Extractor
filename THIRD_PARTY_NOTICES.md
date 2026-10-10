# Third-party notices

The application code is MIT licensed. This does not relicense external tools,
Python, codecs, game assets, trademarks, or third-party contributions.

## Included in the public source release

### lostark-explorer filename decoder

- Upstream: https://github.com/Poyoanon/lostark-explorer
- Author/copyright: Copyright (c) 2026 poyo (anon).
- License: MIT; complete original notice in licenses/lostark-explorer-MIT.txt.
- Source: src/LostArk.Archive.Core/NameObfuscation/LostArkNameDeobfuscator.cs.
- Adaptation: name_decoder.py, Python translation of the filename algorithm,
  with audio-specific format checks and optional CSV overrides.
- This component is not a cipher-key discovery or archive-decryption tool.

## External dependencies - NOT included in the public release

| Component | Purpose | License information / release decision |
|---|---|---|
| Python with Tcl/Tk | Desktop runtime | Separate installation; Python and Tcl/Tk have their own licenses. |
| LAUTool Steam 0.3 | Decode compatible Lost Ark audio wrappers | User-provided binary; no redistribution license identified in local files. Not distributed. |
| QuickBMS | Extract decoded AKPK packages | Local upstream documentation identifies GPL 2.0. Not distributed; obtain from upstream with its notices/source information. |
| wwise_pck_extractor.bms | Wwise package layout | Header credits Nicknine and bnnm; redistribution terms not verified here. Not distributed. |
| vgmstream and codec DLLs | WEM to WAV | Core COPYING is permissive, but linked codec libraries have additional notices/licenses. No binaries or DLLs distributed. |

Authoritative upstream references:

- Python license: https://docs.python.org/3/license.html
- QuickBMS releases, documentation and source: https://aluigi.altervista.org/quickbms.htm
- Wwise script: https://github.com/bnnm/wwiser-utils/blob/master/scripts/wwise_pck_extractor.bms
- vgmstream license: https://github.com/vgmstream/vgmstream/blob/master/COPYING
- vgmstream Windows builds: https://github.com/vgmstream/vgmstream-releases/releases

The local development tools/ directory may contain user-installed copies. The
public release builder deliberately excludes them. It includes only tools/README.md.
The separate local-tools bundle copies user-installed tools for local use only,
with available upstream notices; this does not resolve their redistribution status.
No claim is made that an unverified dependency is public domain or MIT licensed.
Review the exact dependency distribution and its terms before creating a binary
bundle; this source release is not an audit/approval of such a bundle.

## Game content and affiliation

No game files, extracted audio, account data, credentials, keys or local paths
are included in this source release. Lost Ark is a third-party game/trademark.
This is an independent, unofficial project with no claimed endorsement.
The software license does not grant rights to redistribute game content.
