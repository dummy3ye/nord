# Nord Themepack

A collection of Nord-themed stuff — UserCSS browser themes, wallpapers, and `nordify` (a Python tool that turns any image into Nord art).

[Nord](https://www.nordtheme.com/) is an arctic, north-bluish color palette. This repo puts it on things I use daily.

## What's in here

| Thing | Location | What it does |
|---|---|---|
| UserCSS themes | [`css/`](css/) | Skin websites with Nord via [Stylus](https://addons.mozilla.org/en-US/firefox/addon/styl-us/) |
| Wallpapers | [`wallpapers/`](wallpapers/) | Nord wallpapers in 1080p, 1440p, 4K, and phone sizes |
| `nordify` | [`nordify.py`](nordify.py) | CLI tool — turns any photo/selfie/screenshot into Nord-themed art |
| Palette | [`css/_nord.css`](css/_nord.css) | The 16 Nord colors as CSS custom properties |

## Themes

Install with [Stylus](https://addons.mozilla.org/en-US/firefox/addon/styl-us/). Open the `.user.css` file and hit install. Done.

| Site | File | Version |
|---|---|---|
| GitHub | [`github.user.css`](css/github.user.css) | 0.2.8 |
| Instagram | [`instagram.user.css`](css/instagram.user.css) | 0.1.5 |
| Instagram (aurora) | [`instagram.user.aurora.css`](css/instagram.user.aurora.css) | 0.1.7 |
| — | [`_template.user.css`](css/_template.user.css) | — copy this to start a new one |

See [`docs/install.md`](docs/install.md) for how themes work and how to tweak them.

## Wallpapers

10 wallpapers so far, organized by resolution:

```
wallpapers/
├── 1920x1080/
├── 2560x1440/
├── 3840x2160/
└── phone/
```

Filenames follow `nord-<name>.<ext>`. If you're adding one that isn't original, drop the source/license in [`wallpapers/README.md`](wallpapers/README.md).

## nordify

A Python CLI that transforms images into Nord-themed art. Works on selfies, photos, screenshots, logos — anything.

```bash
pip install nordify

nordify input.jpg output.png
nordify --preset selfie selfie.jpg out.png
nordify --preset dark photo.jpg dark-nord.png
nordify batch ./raw/ ./nord/
```

Presets: `default`, `selfie`, `landscape`, `dark`, `aurora`, `retro`, `posterized`, `minimal`.

See the [PyPI page](https://pypi.org/project/nordify/) or run `nordify --help` for all options.

## Adding a theme

1. `cp css/_template.user.css css/<site>.user.css`
2. Fill in the `==UserStyle==` header — name, version, description, `@updateURL`.
3. Set `@-moz-document domain(...)` to the target site.
4. Use the `--nord*` palette variables. Tweakable knobs go in `@var` so users can change them in Stylus without touching CSS.
5. Add a row to the table in [`docs/index.md`](docs/index.md) and here.

## Docs

- [`docs/install.md`](docs/install.md) — how to install and customize themes
- [`docs/index.md`](docs/index.md) — full index of themes, wallpapers, and palette
- [`wallpapers/README.md`](wallpapers/README.md) — wallpaper naming and sources

## License

MIT.
