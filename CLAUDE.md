# LU2MET NR Filter

Live HF audio noise reduction for ham radio. PyQt5 desktop app (`audio_processor/`) with a Rust spectral NR extension (`spectral_nr/`, built with maturin as the Python module `spectral_nr`). Packaged with PyInstaller for macOS, Windows and Linux (Linux is experimental). GPL-3.0-only.

## Layout

- `audio_processor/lu2met_nr_gui.py`: Qt window, settings, audio callback, `--self-test`.
- `audio_processor/audio_pipeline.py`: DSP helpers, device lists, `TxGate` (mute during TX), recordings folder.
- `audio_processor/update_check.py`: update banner (stable GitHub releases only).
- `audio_processor/LU2MET_NR.spec` and `build_macos.sh` / `build_windows.ps1` / `build_linux.sh`: packaging. CI runs the same scripts.
- `audio_processor/tests/tests_*.py`: unittest suite, including a regression test against the reference NR output.
- `.github/workflows/build-apps.yml`: builds all platforms; tags `v*` publish a release.

## Commands

From `audio_processor/`, with the dev venv (`venv/`) active:

```bash
python -m unittest discover -s tests -p 'tests_*.py'   # tests
./run_qt_gui.sh                                         # run from source
./build_macos.sh                                        # full packaged build + self-test
```

After changing Rust code, rebuild the extension into the venv: `cd ../spectral_nr && maturin develop --release`.

## Workflow

- Work on `develop`. Never commit directly to `main`.
- Changes reach `main` through a PR from `develop`; the user merges PRs.
- Releases: tag `vMAJOR.MINOR.PATCH` on `main`; CI publishes the release with all zips. A platform added later can be built for an existing release with a manual run and the `version` input (see BUILD.md).
- `0.0.0-dev.*` builds and runs from source never check for updates.
- Run the tests before committing. Changes to DSP code must keep the regression test passing, or explain why the reference changed.
- Measure before changing audio behavior (levels, timing); the user tests with a real radio before merging audio changes.

## Conventions

- Code, comments, docs, commit messages, PRs and release notes are in English. Talk with the user in Spanish.
- Keep docs in sync with behavior: BUILD.md (building, CI, releases), audio_processor/USAGE.md (using the app), SETTINGS_INFO.md, THIRD_PARTY.md.
- Settings use QSettings under the `LU2MET_NR_Filter` key; keep the migration from older keys.
- Packaged builds must not write next to their code: recordings go to `Documents/LU2MET NR Filter/Recordings`, the log to `~/lu2met_nr_debug.log`.
- Keep the `reconfigure(errors='backslashreplace')` on stdout/stderr at the top of `lu2met_nr_gui.py`: the Windows console is cp1252, and an encoding error in the windowed build opens a dialog that hangs startup.
- `third_party/novasdr-wasm/` keeps its name: it is the upstream attribution. Do not add other upstream credits unless asked.
- Pinned build dependencies live in `audio_processor/requirements-build.txt`; `spectral_nr/Cargo.lock` is respected with `--locked`.
