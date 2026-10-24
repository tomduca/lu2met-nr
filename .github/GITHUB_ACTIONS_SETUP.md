# GitHub Actions Setup

## Step 1: Push the Workflow

```bash
cd /Users/tomasduca/CascadeProjects/nr_filter

# Stage the files
git add .github/

# Commit
git commit -m "Add automated build workflow for macOS and Windows"

# Push
git push origin main
```

## Step 2: Configure GitHub Permissions

1. Open the repository: `https://github.com/tomduca/novasdr-audio-processor`.
2. Select **Settings** → **Actions** → **General**.
3. Under **Workflow permissions**:
   - Select **Read and write permissions**.
   - Select **Allow GitHub Actions to create and approve pull requests**.
4. Select **Save**.

## Step 3: Verify the Workflow

1. Open **Actions** in GitHub.
2. Find the **Build macOS and Windows Apps** workflow run.
3. Allow approximately 15-20 minutes for both builds to finish.
4. When it completes:
   - Open the workflow run.
   - Scroll to **Artifacts**.
   - Download `LU2MET_NR-macos.zip` and `LU2MET_NR-windows.zip`.

## Automatic Builds

The workflow configuration determines when builds run. Check `.github/workflows/build-apps.yml` for the current triggers.

## Automatic Versioning

Each build receives a unique version:

**Formato:** `v1.0.0-beta-YYYYMMDD-HHMMSS-commit`

**Ejemplo:** `v1.0.0-beta-20260429-091500-a3f2c1b`

- **Date and time:** Build timestamp
- **Commit:** Short Git commit hash
- **No overwrites:** Each build is stored separately
- **Retention:** 90 days for artifacts

### Download Builds

**Option 1: From Actions** (all builds)
- GitHub → Actions → Open a run → Artifacts
- Each artifact has a unique version.
- Artifacts are retained for 90 days.

**Option 2: From Releases** (when a release is created)
- GitHub → Releases → Select the required version.
- Each release has a unique tag.
- **No overwrites:** all published versions remain available.

### Run Manually

1. Open GitHub → Actions.
2. Select **Build macOS and Windows Apps**.
3. Select **Run workflow** → **Run workflow**.

---

## Checklist

- [ ] Workflow pushed to GitHub
- [ ] Permissions configured
- [ ] First build succeeds
- [ ] Artifacts can be downloaded
- [ ] Applications work as expected

## Troubleshooting

See the detailed guide: `.github/workflows/WORKFLOW_GUIDE.md`.

---

**73 de LU2MET**
