# Building the Desktop App

This is the canonical guide for packaging the LU2MET NR Filter (PyQt5 interface) for macOS and Windows. For running from source during development, see [INSTALL.md](INSTALL.md).

The same build scripts run locally and in GitHub Actions. Each script:

1. Creates a separate build environment, `audio_processor/.build-venv` (Python 3.12). The development `venv` is not modified.
2. Installs the pinned versions from [`audio_processor/requirements-build.txt`](audio_processor/requirements-build.txt).
3. Builds the `novasdr_nr` Rust extension with `maturin --locked`, so `novasdr_nr_py/Cargo.lock` is respected.
4. Runs the unit tests, including a regression test that compares the filter output with the reference build.
5. Packages the app with PyInstaller using [`audio_processor/LU2MET_NR.spec`](audio_processor/LU2MET_NR.spec).
6. Runs the packaged app with `--self-test`, which checks that the bundled DSP chain loads and produces correctly scaled output.
7. Creates a zip in `audio_processor/dist/`.

## macOS

Requirements: Xcode Command Line Tools (`xcode-select --install`), Python 3.12 (`brew install python@3.12`), and Rust (<https://rustup.rs>).

```bash
./audio_processor/build_macos.sh
```

Output:

- `audio_processor/dist/LU2MET_NR.app`
- `audio_processor/dist/LU2MET_NR-macos-<arch>-<version>.zip`

The app is built for the CPU of the machine that runs the script: `x86_64` on Intel Macs and `arm64` on Apple Silicon. GitHub Actions builds both. The microphone permission text and version are set in the spec file. The bundle is ad-hoc signed; it is not notarized.

Set `PYTHON=/path/to/python3.12` if `python3.12` is not on `PATH`.

## Windows

Requirements: Python 3.12 from <https://www.python.org> (the `py` launcher is used when present), Rust from <https://rustup.rs>, and the Visual Studio Build Tools with "Desktop development with C++" (required by Rust).

From PowerShell:

```powershell
.\audio_processor\build_windows.ps1
```

Or double-click `audio_processor\build_windows.bat`, which runs the same script.

Output:

- `audio_processor\dist\LU2MET_NR\LU2MET_NR.exe` and its supporting files
- `audio_processor\dist\LU2MET_NR-windows-x64-<version>.zip`

The Windows app is a folder (PyInstaller one-dir), not a single `.exe`. It starts faster and is less likely to be flagged by antivirus software than a self-extracting single file. Users extract the zip and run `LU2MET_NR.exe` inside the folder.

## Automated Builds (GitHub Actions)

The workflow is [`.github/workflows/build-apps.yml`](.github/workflows/build-apps.yml). It builds on three runners: macOS Apple Silicon (`macos-15`), macOS Intel (`macos-15-intel`), and Windows x64 (`windows-latest`).

| Event | Result |
| --- | --- |
| Pull request to `main` | Builds and tests every platform; the zips are attached to the run as artifacts. |
| Push to `main` (merge) | Same; download the zips from the run's **Artifacts** section for 30 days. |
| Tag `v*` pushed | Same, plus a GitHub Release with the three zips and generated release notes. |
| Manual run | **Actions → Build apps → Run workflow**, on any branch. |

Builds are versioned `0.0.0-dev.<commit>` unless they come from a tag.

### Publishing a release

```bash
git checkout main
git pull
git tag v1.1.0
git push origin v1.1.0
```

Tags with a suffix, such as `v1.1.0-beta.1`, are published as pre-releases.

The zips in `Download/` are maintained manually and are not touched by the workflow.

## First Launch

**macOS:** the app is not notarized, so Gatekeeper blocks the first launch. Extract the zip, move `LU2MET_NR.app` to Applications, open it once, then go to **System Settings → Privacy & Security** and click **Open Anyway**. Alternatively, run:

```bash
xattr -dr com.apple.quarantine /Applications/LU2MET_NR.app
```

Allow microphone access when asked; it is required to read the audio input device.

**Windows:** SmartScreen may warn about an unknown publisher. Select **More info → Run anyway**.

## Runtime Files

- Recordings from packaged builds are saved to `Documents/LU2MET NR Filter/Recordings`. When running from source they are saved to `audio_processor/recordings`.
- The debug log is `novasdr_debug.log` in the user's home folder.
- MP3 export requires FFmpeg on `PATH`; WAV recording always works.

## Troubleshooting

- **Self-test fails:** the script prints the end of `novasdr_debug.log`. A failure about NR output means the Rust extension is producing wrongly scaled audio; run the unit tests in `audio_processor/tests` to locate it.
- **`maturin` fails with `--locked`:** `Cargo.lock` is out of date. Run `cargo update` in `novasdr_nr_py`, test, and commit the lock file.
- **Wrong Python version:** delete `audio_processor/.build-venv` and run the script again with `PYTHON` pointing to Python 3.12.
