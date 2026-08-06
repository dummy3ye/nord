#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}▸${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

MODE="${1:-build}"

rm -rf dist/ build/ *.egg-info
info "Building sdist + wheel..."
python3 -m pip install --quiet --break-system-packages build 2>/dev/null \
    || python3 -m pip install --quiet build
python3 -m build
ok "Built:"
ls -lh dist/

if [ "$MODE" = "--build" ] || [ "$MODE" = "build" ]; then
    echo ""
    ok "Done. Upload with: ./scripts/publish.sh --upload"
    exit 0
fi

python3 -m pip install --quiet --break-system-packages twine 2>/dev/null \
    || python3 -m pip install --quiet twine

if [ "$MODE" = "--test" ]; then
    info "Uploading to TestPyPI..."
    twine upload --repository testpypi dist/*
    ok "Done → pip install --index-url https://test.pypi.org/simple/ nordify"
else
    info "Uploading to PyPI..."
    twine upload dist/*
    ok "Done → pip install nordify"
fi
