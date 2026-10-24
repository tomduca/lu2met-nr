# Build Workflow Guide

The workflow definition is `.github/workflows/build-apps.yml`.

## Current Trigger

Only `workflow_dispatch` is enabled. Push and pull-request triggers are present as comments and are currently disabled. Start a build manually from **GitHub → Actions → Build macOS and Windows Apps → Run workflow**.

## Build Jobs

- `build-macos` runs on a macOS runner, builds the Rust extension and PyInstaller app, then uploads a ZIP artifact.
- `build-windows` runs on a Windows runner, builds the Rust extension and executable, then uploads a ZIP artifact.
- Artifacts are configured for 90-day retention.

## Release Job Status

The workflow contains a `create-release` job whose condition requires a push to `main`. Since the current workflow trigger only enables manual dispatch, that condition cannot be met with the current triggers. Review this condition when changing release automation.

## Run a Build

1. Open the repository's **Actions** tab.
2. Select **Build macOS and Windows Apps**.
3. Select **Run workflow** and choose the desired branch.
4. Open the completed run and download the platform ZIPs from **Artifacts**.

## Troubleshooting

- Inspect the failing job's logs in the Actions run.
- Check that the Python, Rust, Maturin, and PyInstaller setup steps completed.
- Check the platform build scripts under `audio_processor/`.
- Compare the workflow's Python version and dependency install commands with the local [BUILD.md](../../BUILD.md) guide.
