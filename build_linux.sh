#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_FILE="$ROOT_DIR/launcher lin.pyw"
ASSETS_DIR="$ROOT_DIR/assets"
HORIZON_DIR="${HORIZON_SOURCE_DIR:-$ROOT_DIR/horizon-linux-x86_64}"
DIST_DIR="${DIST_DIR:-$ROOT_DIR/dist/linux}"
WORK_DIR="${WORK_DIR:-$ROOT_DIR/build/linux}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv-linux-build}"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
    echo "Build this launcher on Linux x86_64." >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required to build the launcher." >&2
    exit 1
fi

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 13))'; then
    echo "Python 3.13 or newer is required." >&2
    exit 1
fi

if [[ ! -f "$SOURCE_FILE" || ! -f "$ASSETS_DIR/app_icon.png" ]]; then
    echo "The Linux launcher source or app icon is missing." >&2
    exit 1
fi

for executable in horizon-client horizon-prepare horizon-ctl horizon-server; do
    if [[ ! -f "$HORIZON_DIR/$executable" ]]; then
        echo "Missing Linux Horizon executable: $HORIZON_DIR/$executable" >&2
        exit 1
    fi
done

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements-linux-build.txt"

mkdir -p "$DIST_DIR"
"$VENV_DIR/bin/python" -m PyInstaller \
    --clean \
    --noconfirm \
    --onefile \
    --windowed \
    --name Crackrizon \
    --add-data "$ASSETS_DIR:assets" \
    --collect-all flet \
    --collect-all flet_desktop \
    --collect-all minecraft_launcher_lib \
    --distpath "$DIST_DIR" \
    --workpath "$WORK_DIR/work" \
    --specpath "$WORK_DIR" \
    "$SOURCE_FILE"

mkdir -p "$DIST_DIR/horizon-linux-x86_64"
cp -a "$HORIZON_DIR/." "$DIST_DIR/horizon-linux-x86_64/"
chmod +x "$DIST_DIR/Crackrizon"
chmod +x "$DIST_DIR/horizon-linux-x86_64"/horizon-client \
    "$DIST_DIR/horizon-linux-x86_64"/horizon-prepare \
    "$DIST_DIR/horizon-linux-x86_64"/horizon-ctl \
    "$DIST_DIR/horizon-linux-x86_64"/horizon-server

echo
echo "Linux build ready:"
echo "  $DIST_DIR/Crackrizon"
echo "  $DIST_DIR/horizon-linux-x86_64/"
