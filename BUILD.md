# Building the Desktop App

This is the canonical guide for packaging the LU2MET NR Filter (PyQt5 interface) for macOS, Windows and Linux. For running from source during development, see [INSTALL.md](INSTALL.md).

The same build scripts run locally and in GitHub Actions. Each script:

1. Creates a separate build environment, `audio_processor/.build-venv` (Python 3.12). The development `venv` is not modified.
2. Installs the pinned versions from [`audio_processor/requirements-build.txt`](audio_processor/requirements-build.txt).
3. Builds the `spectral_nr` Rust extension with `maturin --locked`, so `spectral_nr/Cargo.lock` is respected.
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

## Linux

Experimental: built and self-tested in CI, not yet tested with a real radio.

Requirements (Debian/Ubuntu names): Python 3.12 with `venv`, Rust from <https://rustup.rs>, `zip`, and PortAudio:

```bash
sudo apt install python3.12-venv zip libportaudio2
./audio_processor/build_linux.sh
```

Output:

- `audio_processor/dist/LU2MET_NR/LU2MET_NR` and its supporting files
- `audio_processor/dist/LU2MET_NR-linux-<arch>-<version>.zip`

Like on Windows, the app is a folder. PortAudio is not bundled; the app uses the system `libportaudio2`, so it works with the distribution's ALSA, PulseAudio or PipeWire setup. GitHub Actions builds on Ubuntu 22.04, so the zip runs on distributions with glibc 2.35 or newer.

## Automated Builds (GitHub Actions)

The workflow is [`.github/workflows/build-apps.yml`](.github/workflows/build-apps.yml). It builds on four runners: macOS Apple Silicon (`macos-15`), macOS Intel (`macos-15-intel`), Windows x64 (`windows-latest`), and Linux x86_64 (`ubuntu-22.04`).

| Event | Result |
| --- | --- |
| Pull request to `main` | Builds and tests every platform; the zips are attached to the run as artifacts. |
| Push to `main` (merge) | Same; download the zips from the run's **Artifacts** section for 30 days. |
| Tag `v*` pushed | Same, plus a GitHub Release with the four zips and generated release notes. |
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

Use `vMAJOR.MINOR.PATCH` tags. The version is embedded in the app (window title, macOS `Info.plist`, and `app_version.txt` in the package).

### Update notice in the app

At startup, packaged builds ask GitHub for the latest **stable** release (`/releases/latest`, which excludes drafts and pre-releases). When it is newer than the running version, a banner at the top of the window links to the release. The banner can be dismissed; it stays hidden until a newer version is published. Development builds (`0.0.0-dev.*`) and runs from source do not check. The check runs in the background with a 5-second timeout and is silent when offline.

To preview the banner, set `LU2MET_NR_VERSION` to an older version (for example `LU2MET_NR_VERSION=0.9.0`) when starting the app, once a stable release exists.

The zips in `Download/` are maintained manually and are not touched by the workflow.

## First Launch

**macOS:** the app is not notarized, so Gatekeeper blocks the first launch. Extract the zip, move `LU2MET_NR.app` to Applications, open it once, then go to **System Settings → Privacy & Security** and click **Open Anyway**. Alternatively, run:

```bash
xattr -dr com.apple.quarantine /Applications/LU2MET_NR.app
```

Allow microphone access when asked; it is required to read the audio input device.

**Windows:** SmartScreen may warn about an unknown publisher. Select **More info → Run anyway**.

**Linux:** install PortAudio (`sudo apt install libportaudio2` on Debian/Ubuntu, `sudo dnf install portaudio` on Fedora), extract the zip, and run `LU2MET_NR/LU2MET_NR`. If Qt reports that it could not load the `xcb` platform plugin, install `libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0` (Debian/Ubuntu names).

## Runtime Files

- Recordings from packaged builds are saved to `Documents/LU2MET NR Filter/Recordings`. When running from source they are saved to `audio_processor/recordings`.
- The debug log is `lu2met_nr_debug.log` in the user's home folder.
- MP3 export requires FFmpeg on `PATH`; WAV recording always works.

## Troubleshooting

- **Self-test fails:** the script prints the end of `lu2met_nr_debug.log`. A failure about NR output means the Rust extension is producing wrongly scaled audio; run the unit tests in `audio_processor/tests` to locate it.
- **`maturin` fails with `--locked`:** `Cargo.lock` is out of date. Run `cargo update` in `spectral_nr`, test, and commit the lock file.
- **Linux: `PortAudio library not found`:** install `libportaudio2` (or `portaudio` on Fedora/Arch).
- **Wrong Python version:** delete `audio_processor/.build-venv` and run the script again with `PYTHON` pointing to Python 3.12.
