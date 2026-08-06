# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is this repo

Nord Themepack — UserCSS browser themes, wallpapers, and `nordify` (Python CLI for Nord-ifying images). Built around the [Nord](https://www.nordtheme.com/) color palette.

## Commits

Conventional commits only. Always include `Co-Authored-By: Claude <noreply@anthropic.com>`.

```
feat(theme): add Gmail dark theme
fix(nordify): handle RGBA input in histogram matching
refactor(wallpapers): normalize filenames to nord-<name>.<ext>
docs: update index.md with new themes
```

## Common commands

```bash
# nordify (Python)
uv venv && uv pip install -e .
nordify input.jpg output.png
nordify --preset selfie selfie.jpg out.png
nordify presets

# lint
pylint nordify.py

# build + publish to PyPI
python3 -m build
python3 -m twine upload dist/*

# git
git add <files> && git commit -m "type(scope): message"
```

## Project structure

- **`css/`** — UserCSS themes for Stylus browser extension. Each site gets one `.user.css` file. `_nord.css` is the source-of-truth palette (CSS custom properties). `_template.user.css` is the starting point for new themes.
- **`nordify.py`** — Single-file Python CLI (~1000 lines). Depends only on numpy + Pillow. Processes images in LAB/RGB/HSV space with multiple mapping algorithms. Published to PyPI as `nordify`.
- **`wallpapers/`** — Nord wallpapers organized by resolution (`1920x1080/`, `2560x1440/`, `3840x2160/`). Files named `nord-<name>.<ext>`.
- **`docs/`** — `index.md` (full index of themes/wallpapers/palette), `install.md` (how to install themes).
- **`scripts/`** — `install.sh` (curl one-liner installer), `publish.sh` (PyPI publish helper).

## UserCSS theme conventions

Themes are self-contained CSS files with `==UserStyle==` metadata headers. The `@-moz-document domain(...)` scope limits which site the CSS applies to. Each theme inlines the Nord palette so it installs standalone — no external CSS imports. Tweakable knobs use `@var` so users can change them in Stylus options without editing CSS.

When writing a theme, use the `--nord*` custom property names from `css/_nord.css`. Semantic aliases: `--accent` (nord8), `--bg` (nord0), `--fg` (nord4).

## nordify architecture

Key pipeline stages in `nordify()`:
1. Colour mapping — grade LUT, Reinhard transfer (LAB mean+std), or histogram matching
2. Edge-aware blend — gradient-based mask reduces grade near edges
3. Saturation + contrast (smoothstep S-curve)
4. Skin protection — RGB heuristic with dilation
5. Temperature — LAB a/b shift
6. Optional: posterize (seeded k-means or Floyd-Steinberg dithering), vignette, grain

Colour space conversions: sRGB ↔ linear ↔ XYZ ↔ CIE LAB. All vectorized numpy — no pixel loops (except Floyd-Steinberg which is inherently sequential).

Presets (`PRESETS` dict) override individual parameters. Auto-detection (`--auto`) analyses the image and picks the best preset.

## Python packaging

- Build system: hatchling
- Entry point: `nordify = "nordify:main"` (registered as `nordify` CLI command after install)
- Dependencies: `numpy>=1.22`, `Pillow>=9.0`
- Published at https://pypi.org/project/nordify/
- Also supports conda via `environment.yml`
