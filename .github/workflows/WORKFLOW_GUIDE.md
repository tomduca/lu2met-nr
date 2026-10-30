# Build Workflow

`build-apps.yml` builds the desktop app for macOS Apple Silicon, macOS Intel, Windows x64, and Linux x86_64 (experimental) by running the same scripts used for local builds (`audio_processor/build_macos.sh`, `audio_processor/build_windows.ps1`, and `audio_processor/build_linux.sh`).

- Pull requests to `main` and pushes to `main`: build, test, and upload the zips as run artifacts (30 days).
- Tags `v*`: additionally publish a GitHub Release; tags containing `-` are pre-releases.
- Manual runs: **Actions → Build apps → Run workflow**. The optional **version** input builds zips for an existing release, for example to add a platform without a new tag.
- Pull requests and pushes that only change Markdown files or `docs/` skip the build. Tags always build.

The workflow declares the permissions it needs; no repository settings changes are required.

See [BUILD.md](../../BUILD.md) for local builds, versioning, releases, and troubleshooting.
