# Changelog

## 1.4.3

- Pestaña activa más oscura, grande y en negrita; botones Examinar compactos y separados.
- Foco por color, sin bordes punteados; teclado conservado.
- Carpetas de salida Windows con desktop.ini oculto FolderType=Generic; respeta INI existentes.

## 1.4.2

- Tamaños en KB enteros redondeados, punto como separador de miles.
- Tema claro verde salvia, controles con contraste y tipografía Segoe UI.

## 1.4.1

- Cabecera Tamaño; valores conservan KB y orden por bytes.
- Icono proporcionado por el usuario en ventana y ejecutable.

## 1.4.0 - 2026-10-13

- New output folders use decoded__original source stems, including numeric names.
  Existing manifests keep their folders; use a new destination for the new layout.
- Format selector offers WAV, MP3 (320 kbps, 44.1 kHz), or both. FFmpeg/libmp3lame
  is bundled locally; public source remains binary-free. More than two channels
  are downmixed to stereo for MP3; WAV preserves decoded PCM.
- Independent MP3 manifests (schema 3) support resume, missing-file recovery,
  SHA256 integrity checks and name repair. WAV schema 2 remains compatible.
- Reuse registered WAVs from the same source for MP3 instead of unpacking again.
  Full MP3 decode validation precedes publication; cancel/error cleans temporary files.

## 1.3.4 - 2026-10-13

- Expanded local dictionary from supplied loa_data_db references and existing banks.
  New mappings require event hash, owning bank, media package and language evidence.
- Indexed package/media lookups avoid scanning the full catalog per WAV.
- Explicit es/en/ko filename markers preserve separate localized media with equal IDs.
  Conflicting language tags cannot override the selected media language; SFX remains SFX.
- Existing WAVs can use the name-repair action without reconversion. Unknown or
  ambiguous associations remain unnamed; already named WAVs stay unchanged.

## 1.3.2 - 2026-10-09

- Resume now restores missing registered WAVs/folders instead of failing with
  FileNotFoundError when completion metadata outlives the audio files.
- Retains valid existing WAVs, known event names and pending recovery across
  failures. Only missing media are reconverted; incomplete recovery stays pending.
- Permission errors, corrupt WAVs and interrupted renames are not mistaken for
  deleted files. Source fingerprint and output-path safeguards remain enforced.
- Local-tools bundle still includes all tools/DLLs and the partial event catalog.

## 1.3.1 - 2026-10-09

- Local-tools bundle now includes a portable, path-free snapshot of known event
  associations, automatically loaded when no explicit catalog CSV is selected.
- Public source stays free of game metadata. Catalog coverage is not universal.
- Added explicit destination name repair in the GUI and repair_names.py CLI:
  exact language/package/media ID only, no audio conversion or guessed titles.
- Metadata backups, previous-name history and hash-checked interruption recovery;
  collisions never overwrite existing WAVs. Unknown media remain sin_evento.
- Extraction log reports loaded association count or missing catalog.

## 1.3.0 - 2026-10-09

- Removed the trailing identity hash from new WAV filenames; original media ID
  and language remain. Known collisions use _2, _3, etc.; unknown files are not overwritten.
- Release CLI builds public source plus a separate local-tools ZIP by default.
- Local-tools bundle contains required EXEs, script, DLLs and available notices;
  it is local-use-only pending third-party redistribution review. Python remains external.
- --source-only builds the public MIT source without external tools.
- Both archives are verified against per-file manifests and listed in SHA256SUMS.txt.
- Earlier releases and previously converted WAV filenames remain unchanged.

## 1.2.0 - 2026-10-09

- Group new inputs whose decoded name starts with a digit into Audios_numericos.
- Other inputs retain their decoded source filename as the output folder name.
- Audio-only flat folders and collision-safe filenames remain unchanged.
- Existing v1.0/v1.1 outputs are reused in place, never automatically moved.

## 1.1.0 - 2026-10-09

- New exports use destination/decoded_package_name/*.wav, with no nested folders.
- Package folders contain audio only: no playlists, JSON, logs, BNK, WEM or PCK.
- One separate .loa_audio directory holds per-source logs and resume metadata.
- Intermediates and partial WAVs are cleaned on success, cancellation and failure.
- Validated WAVs survive partial failures and are reused when retrying.
- Language/media identity suffixes prevent collisions when packages share names.
- Existing v1.0 exports remain untouched and completed jobs are still recognized.
- The v1.0.0 release archive is preserved unchanged.

## 1.0.0 - 2026-10-09

First public source release for Windows and Python 3.10+ with Tcl/Tk.

- Local Tkinter interface with source/destination selection and filtered multi-select.
- Automatic PCK/WEM filename deobfuscation, with original paths visible.
- Ascending/descending headers, exact-byte numeric sorting and KB labels.
- LAUTool, QuickBMS and vgmstream integration using configurable app-local paths.
- Validated WAV output, per-input manifests/playlists, cancellation and logs.
- Completed-job reuse, including folders created before name deobfuscation.
- Optional inventory/catalog CSV mappings for known event names.
- Source/output folder selections are session-only; tool paths remain portable.
- MIT license, upstream decoder attribution, external dependency notices.
- Repeatable source ZIP builder with per-file manifest and SHA256 checksum.

Known limitations: no standalone EXE or Python runtime; external converters not
bundled; no MP3; no automatic BNK event composition; no guaranteed compatibility
with every game version. WAV media IDs are not necessarily song titles.

## Audio naming fix 1.3.3 (2026-10-13)
Confirmed requested ID 60147531 exists as Korean/SOUND_BGM_GLOBAL in local catalog.
Old extraction used arbitrary parent-folder names as language (e.g. WwiseAudioPackage), causing exact catalog lookup failures. New resolver checks known language aliases in media/source ancestors, then allows package+ID lookup only when a single language association exists. Explicit language conflicts and ambiguous IDs remain unknown. Event language tags provide ko/en/es filename suffixes. Extraction and existing-output name repair share resolution.
Validation: 61 tests pass, including simulated PCK conversion producing bgm_global_jukebox_m195_2d_play__ko__60147531.wav. Read-only repair preview on test_audio_res: 1213 recoverable, 2307 unknown, 116 already named. Existing audio not renamed this session; use Actualizar nombres del destino. New EXE: apps/releases/1.3.3/windows/LoaAudioExtractor-1.3.3.exe. No actual game-source conversion performed in this session.
