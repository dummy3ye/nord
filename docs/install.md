# Installing a theme

Themes are UserCSS files meant for the [Stylus](https://addons.mozilla.org/en-US/firefox/addon/styl-us/) browser extension (Firefox and Chrome/Chromium).

## Install

1. Install [Stylus](https://addons.mozilla.org/en-US/firefox/addon/styl-us/).
2. Open the `.user.css` file (e.g. via `file://` in the browser). Stylus recognizes the `==UserStyle==` header and offers a one-click **Install style**.
   - No header support? Use Stylus → **Manage** → **Write new style** → paste the CSS, and keep the `@-moz-document domain(...)` scope.
3. Done — the theme applies on the matching domain.

## Anatomy of a theme file

- **`==UserStyle==` metadata block** — `@name`, `@version`, `@description`, `@updateURL`, … When the file is hosted, Stylus can auto-update.
- **`@-moz-document domain("...")`** — the scope: which site(s) the CSS applies to.
- **`:root { --nord0 … }`** — the palette, inlined per theme so each file installs standalone.
- **`@var color accent "…" #88C0D0`** — a tweakable knob, exposed as `var(--accent)` in the CSS. Users can change it in Stylus' style options without touching raw CSS.

## Tweaking

Stylus → **Manage** → *style* → the gear/options shows each `@var`. Change the accent, background, etc. there.

## Palette

The canonical palette is [`css/_nord.css`](../css/_nord.css). It's not imported at runtime — site themes inline the colors, so they stay self-contained.
