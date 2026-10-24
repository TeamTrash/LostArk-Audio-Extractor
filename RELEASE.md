# Release procedure

## v1.4.7 deliverables

LoaAudioExtractor-1.4.7-source.zip is the public source package. It includes MIT
licenses, source, tests, documentation, the Windows launcher and a file manifest.
It is not a standalone executable and does not include external audio tools.
The user's local tools/ installation remains separate and is not altered.

LoaAudioExtractor-1.4.7-local-tools.zip includes copies of the required local tools,
DLLs and available documentation. Local use only: no claim of redistribution
permission for LAUTool or all codec dependencies. See LOCAL_USE_ONLY.md.
It also includes data/event_names.local.json: a local, path-free snapshot from
CATALOGO.csv, with provenance hash and only language/package/media ID/event names.
This is not a complete game dictionary and is excluded from public source.
The local build requires this snapshot as well as tools; preserve it on upgrades.

## Build and verify

Run in this directory with Python 3.10+:

```text
python -m unittest discover -s tests -v
python app.py --version
python build_release.py
python build_release.py --verify dist/LoaAudioExtractor-1.4.7-source.zip
python build_release.py --verify dist/LoaAudioExtractor-1.4.7-local-tools.zip
```

Default outputs: both versioned ZIPs and dist/SHA256SUMS.txt listing both hashes.
All required tools must be present locally; missing DLLs fail the local build.
For a public source-only build (including from a clean source distribution):

```text
python build_release.py --source-only
```

`--output PATH` selects another release directory. To verify a download checksum:

```powershell
Get-FileHash -Algorithm SHA256 .\LoaAudioExtractor-1.4.7-local-tools.zip
```

Compare with SHA256SUMS.txt. Checksums detect differences; they are not a digital
signature or proof of author identity. No code signing has been performed.

Build uses an explicit file allowlist, fixed ZIP timestamps, deterministic order
and a manifest with SHA256 per file. Identical inputs on the same Python/zlib
toolchain produce identical ZIP bytes. No Git state or local config is embedded.

Before publication, extract the source ZIP into a clean folder and run its tests.
Check that no .exe/.dll/.bms, game assets, local config or personal launcher appears.
Do not zip the entire development directory: its tools/ may contain private local
dependencies. Publish the generated source archive, not the development folder.
Do not publish the local-tools bundle while dependency distribution rights remain unverified.

No automatic uploads, Git tags, commits or repository creation are performed.

