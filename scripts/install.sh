#!/usr/bin/env bash
# nordify installer — run via:
#   curl -sSL https://raw.githubusercontent.com/dummy3ye/nord/main/scripts/install.sh | bash
set -euo pipefail

REPO="https://github.com/dummy3ye/nord"
BRANCH="main"
BIN_DIR="${INSTALL_DIR:-/usr/local/bin}"

# ── colours for output ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}▸${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

# ── check python ────────────────────────────────────────────────────────
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done
[ -n "${PYTHON:-}" ] || err "python3 not found — install Python 3.9+ first"

PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    err "Python 3.9+ required, found $PY_VER"
fi
ok "Python $PY_VER"

# ── check pip ───────────────────────────────────────────────────────────
if ! $PYTHON -m pip --version &>/dev/null; then
    info "pip not found — bootstrapping..."
    $PYTHON -m ensurepip --upgrade 2>/dev/null || {
        curl -sS https://bootstrap.pypa.io/get-pip.py | $PYTHON
    }
fi
ok "pip available"

# ── create temp working dir ─────────────────────────────────────────────
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
info "Downloading nordify..."

# ── fetch files from GitHub ─────────────────────────────────────────────
RAW="https://raw.githubusercontent.com/dummy3ye/nord/$BRANCH"
for f in nordify.py pyproject.toml; do
    curl -sSfL "$RAW/$f" -o "$TMPDIR/$f" || err "Failed to download $f"
done
ok "Downloaded nordify.py + pyproject.toml"

# ── install ─────────────────────────────────────────────────────────────
info "Installing nordify..."
$PYTHON -m pip install --quiet --break-system-packages "$TMPDIR" 2>/dev/null \
    || $PYTHON -m pip install --quiet "$TMPDIR"

# ── verify ──────────────────────────────────────────────────────────────
if command -v nordify &>/dev/null; then
    VER=$(nordify version 2>/dev/null || echo "installed")
    ok "nordify installed → $VER"
    echo ""
    echo "  usage:  nordify input.jpg output.png"
    echo "  presets: nordify presets"
    echo "  help:   nordify --help"
else
    # pip installed it but not on PATH — find and link
    NORDIFY_PATH=$($PYTHON -c "import shutil; print(shutil.which('nordify') or '')" 2>/dev/null || true)
    if [ -z "$NORDIFY_PATH" ]; then
        # manual fallback: just put nordify.py on PATH
        DEST="$BIN_DIR/nordify"
        cp "$TMPDIR/nordify.py" "$DEST"
        chmod +x "$DEST"
        ok "nordify installed → $DEST"
    else
        ok "nordify installed → $NORDIFY_PATH"
    fi
    echo ""
    echo "  usage:  nordify input.jpg output.png"
    echo "  presets: nordify presets"
    echo "  help:   nordify --help"
fi
