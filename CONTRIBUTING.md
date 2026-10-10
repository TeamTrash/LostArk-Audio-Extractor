# Contributing

Python 3.10+ with Tkinter is sufficient for development. No pip dependencies.
New contributions are offered under this project's MIT license; retain existing
third-party copyright and license notices. Do not change upstream attribution.

1. Keep changes focused and include regression tests.
2. Run `python -m unittest discover -s tests -v` on a graphical Windows session.
3. Never commit config.local.json, private paths, game archives, extracted media,
   third-party binaries/DLLs, downloads or personal launchers.
4. Use synthetic test fixtures for shared tests. Do not publish copyrighted samples.
5. Keep source files immutable during extraction; no game modifications or key research.

For a release, update version.py, CHANGELOG.md and DEPENDENCIES.json, then follow
RELEASE.md. Do not add converter binaries to the public package without a separate
license/provenance review. Report reproducible issues without private source paths.

No remote repository or issue tracker has been configured by this release process.
