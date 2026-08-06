# Index

## Palette
- [`css/_nord.css`](../css/_nord.css) — the 16 Nord colors as CSS custom properties, plus semantic aliases.

## Themes
| Site | File | Version | Status |
|---|---|---|---|
| GitHub | [`css/github.user.css`](../css/github.user.css) | 0.2.8 | ✅ done |
| — | [`css/_template.user.css`](../css/_template.user.css) | 0.1.0 | template |
| Instagram | [`css/instagram.user.css`](../css/instagram.user.css) | 0.1.3 | ✅ done (v4, expect DOM iterations) |
| Gmail | — | — | planned |
| YouTube | — | — | planned |
| Wikipedia | — | — | planned |

## Wallpapers
See [`wallpapers/README.md`](../wallpapers/README.md).

## How to add a theme
1. `cp css/_template.user.css css/<site>.user.css`
2. Fill in the `==UserStyle==` header (name, description, `@updateURL`).
3. Set the `@-moz-document domain(...)` to the site.
4. Style against the `--nord*` palette and the `--accent` / `--bg` / `--fg` knobs.
5. Add a row to the theme table here and in the repo [`README.md`](../README.md).
