# Build Versioning

## Version Format

Each build uses a version string in this format:

```text
v1.0.0-beta-YYYYMMDD-HHMMSS-commit
```

- `v1.0.0-beta`: project base version.
- `YYYYMMDD`: build date.
- `HHMMSS`: build time.
- `commit`: short Git commit hash (7 characters).

Example:

```text
v1.0.0-beta-20260429-091530-a3f2c1b
```

## Build Artifacts

macOS and Windows archives include the version string in their filenames:

```text
LU2MET_NR-macos-v1.0.0-beta-20260429-091530-a3f2c1b.zip
LU2MET_NR-windows-v1.0.0-beta-20260429-091530-a3f2c1b.zip
```

GitHub Actions artifacts are configured to be retained for 90 days. Their availability and build triggers are defined in `.github/workflows/build-apps.yml`.

## Releases

Release tags use the same version format. Release contents include the platform archives and the commit message configured by the workflow. Releases remain available until manually deleted.

## Find Previous Builds

From **Actions**:

1. Open the required workflow run.
2. Scroll to **Artifacts**.
3. Download the archive for that build.

From **Releases**:

1. Open the required release.
2. Download the macOS or Windows archive.

## Compare Builds

Compare timestamps in version strings or inspect the corresponding commit range:

```bash
git log a3f2c1b..c5a1f8e --oneline
```

## Change the Base Version

Edit the version assignment in `.github/workflows/build-apps.yml`, then commit the change. For example:

```yaml
VERSION="v1.0.0-$(date +'%Y%m%d-%H%M%S')-$(git rev-parse --short HEAD)"
VERSION="v1.1.0-beta-$(date +'%Y%m%d-%H%M%S')-$(git rev-parse --short HEAD)"
```

The examples show alternative values; use only the intended assignment in the workflow.
