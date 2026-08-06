#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/dummy3ye/nord"
BRANCH="main"
METHOD="${METHOD:-auto}"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}▸${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then PYTHON="$cmd"; break; fi
done
[ -n "${PYTHON:-}" ] || err "python3 not found — install Python 3.9+ first"

PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
[ "$PY_MAJOR" -ge 3 ] && { [ "$PY_MINOR" -ge 9 ] || err "Python 3.9+ required"; } \
    || err "Python 3.9+ required"
ok "Python $($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")"

if ! $PYTHON -m pip --version &>/dev/null; then
    info "pip not found — bootstrapping..."
    $PYTHON -m ensurepip --upgrade 2>/dev/null || curl -sS https://bootstrap.pypa.io/get-pip.py | $PYTHON
fi
ok "pip available"

try_pypi() {
    info "Installing nordify from PyPI..."
    $PYTHON -m pip install --quiet --break-system-packages nordify 2>/dev/null \
        && return 0 \
        || $PYTHON -m pip install --quiet nordify 2>/dev/null
}

try_github() {
    info "Installing nordify from GitHub..."
    TMPDIR=$(mktemp -d)
    trap 'rm -rf "$TMPDIR"' EXIT

    RAW="https://raw.githubusercontent.com/dummy3ye/nord/$BRANCH"
    for f in nordify.py pyproject.toml; do
        curl -sSfL "$RAW/$f" -o "$TMPDIR/$f" || err "Failed to download $f"
    done
    ok "Downloaded nordify.py + pyproject.toml"

    $PYTHON -m pip install --quiet --break-system-packages "$TMPDIR" 2>/dev/null \
        || $PYTHON -m pip install --quiet "$TMPDIR"
}

case "$METHOD" in
    pypi)   try_pypi ;;
    github) try_github ;;
    auto)
        if ! try_pypi; then
            info "PyPI failed — falling back to GitHub..."
            try_github
        fi
        ;;
esac

if command -v nordify &>/dev/null; then
    VER=$(nordify version 2>/dev/null || echo "installed")
    ok "nordify installed → $VER"
else
    NORDIFY_PATH=$($PYTHON -c "import shutil; print(shutil.which('nordify') or '')" 2>/dev/null || true)
    if [ -n "$NORDIFY_PATH" ]; then
        ok "nordify installed → $NORDIFY_PATH"
    else
        ok "nordify installed (run: python3 -m nordify)"
    fi
fi
echo ""
echo "  nordify input.jpg output.png"
echo "  nordify presets"
echo "  nordify --help"
