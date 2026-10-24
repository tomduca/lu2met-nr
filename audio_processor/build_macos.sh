#!/bin/bash
# Build the macOS app bundle and a distributable zip for the current CPU
# architecture. Uses a separate build environment (.build-venv), so the
# development venv is not modified.
#
# Environment overrides:
#   PYTHON       Python used to create the build environment (default python3.12)
#   APP_VERSION  Version embedded in the app and zip name (default 0.0.0-dev.<commit>)
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3.12}"
BUILD_VENV=".build-venv"
APP_VERSION="${APP_VERSION:-0.0.0-dev.$(git rev-parse --short HEAD)}"
ARCH="$(uname -m)"
APP="dist/LU2MET_NR.app"
ZIP="dist/LU2MET_NR-macos-${ARCH}-${APP_VERSION}.zip"
export APP_VERSION

echo "==> Building LU2MET NR Filter ${APP_VERSION} for macOS ${ARCH}"

if [ ! -x "${BUILD_VENV}/bin/python" ]; then
    echo "==> Creating build environment with ${PYTHON}"
    "${PYTHON}" -m venv "${BUILD_VENV}"
fi
source "${BUILD_VENV}/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements-build.txt

echo "==> Building spectral_nr Rust extension"
rm -rf build dist
maturin build --release --locked -m ../spectral_nr/Cargo.toml -o build/wheels
python -m pip install --quiet --force-reinstall --no-deps build/wheels/*.whl

echo "==> Running tests"
python -m unittest discover -s tests -p 'tests_*.py'

echo "==> Packaging with PyInstaller"
pyinstaller --noconfirm --clean LU2MET_NR.spec

echo "==> Signing (ad-hoc)"
codesign --force --deep --sign - "${APP}"
codesign --verify --deep --strict "${APP}"

echo "==> Self-test of the packaged app"
if ! QT_QPA_PLATFORM=offscreen "${APP}/Contents/MacOS/LU2MET_NR" --self-test; then
    tail -n 40 "${HOME}/lu2met_nr_debug.log" || true
    echo "Packaged app self-test failed" >&2
    exit 1
fi

echo "==> Creating ${ZIP}"
ditto -c -k --keepParent "${APP}" "${ZIP}"

echo ""
echo "Build complete:"
echo "  App: audio_processor/${APP}"
echo "  Zip: audio_processor/${ZIP}"
