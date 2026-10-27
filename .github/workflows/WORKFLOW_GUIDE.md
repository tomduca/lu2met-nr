# Build Workflow

`build-apps.yml` builds the desktop app for macOS Apple Silicon, macOS Intel, and Windows x64 by running the same scripts used for local builds (`audio_processor/build_macos.sh` and `audio_processor/build_windows.ps1`).

- Pull requests to `main` and pushes to `main`: build, test, and upload the zips as run artifacts (30 days).
- Tags `v*`: additionally publish a GitHub Release; tags containing `-` are pre-releases.
- Manual runs: **Actions → Build apps → Run workflow**.

The workflow declares the permissions it needs; no repository settings changes are required.

See [BUILD.md](../../BUILD.md) for local builds, versioning, releases, and troubleshooting.
