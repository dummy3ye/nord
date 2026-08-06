# Index

Everything in the Nord Themepack, in one place.

## Palette

[`css/_nord.css`](../css/_nord.css) — the 16 Nord colors as CSS custom properties, plus semantic aliases (`--accent`, `--bg`, `--fg`, etc.). Site themes inline these so each file installs standalone; `_nord.css` is the source of truth to copy from.

## Themes

| Site | File | Version | Status |
|---|---|---|---|
| GitHub | [`css/github.user.css`](../css/github.user.css) | 0.2.8 | done |
| Instagram | [`css/instagram.user.css`](../css/instagram.user.css) | 0.1.5 | done — nord1 bubbles + comment section |
| Instagram (aurora) | [`css/instagram.user.aurora.css`](../css/instagram.user.aurora.css) | 0.1.7 | variant — aurora-gradient sent bubbles + comment section |
| — | [`css/_template.user.css`](../css/_template.user.css) | 0.1.0 | template — copy to start a new theme |
| Gmail | — | — | planned |
| YouTube | — | — | planned |
| Wikipedia | — | — | planned |

## Wallpapers

### 3840×2160 (4K)

| File | Resolution | Format |
|---|---|---|
| `nord-city.jpg` | 6512×4341 | JPG |
| `nord-lake.png` | 3840×2160 | PNG |
| `nord-mountains.png` | 3840×2160 | PNG |
| `nord-scenery.png` | 3840×2160 | PNG |
| `nord-space.png` | 3180×1931 | PNG |

### 2560×1440

| File | Resolution | Format |
|---|---|---|
| `nord-wild.png` | 2560×1440 | PNG |
| `nord-street-blues.png` | 2560×1280 | PNG |

### 1920×1080

| File | Resolution | Format |
|---|---|---|
| `nord-utility.png` | 1920×1200 | PNG |
| `nord-alone-tree.png` | 1920×1080 | PNG |
| `nord-waves.jpg` | 1920×1080 | JPG |

See [`wallpapers/README.md`](../wallpapers/README.md) for naming conventions and how to add more.

## nordify

Python CLI that turns any image into Nord-themed art. Install:

```bash
pip install nordify
```

| Preset | What it's good for |
|---|---|
| `default` | General purpose |
| `selfie` | Faces — edge preservation + skin protection |
| `landscape` | Outdoor scenery — stronger grade, vignette |
| `dark` | Moody — heavy Polar Night, grain |
| `aurora` | Accent-forward — Reinhard transfer |
| `retro` | Vintage — dithered + grain |
| `posterized` | Flat graphic look |
| `minimal` | Subtle tint |

See [PyPI](https://pypi.org/project/nordify/) or `nordify --help` for the full list of flags.

## Adding a theme

1. `cp css/_template.user.css css/<site>.user.css`
2. Fill in the `==UserStyle==` header (name, description, `@updateURL`).
3. Set `@-moz-document domain(...)` to the site.
4. Style against `--nord*` palette variables. Use `@var` for tweakable knobs.
5. Add a row to the table here and in the repo [`README.md`](../README.md).
