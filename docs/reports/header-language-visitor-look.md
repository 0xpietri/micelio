# Report: header, language flag, a visitor's own look, pinch zoom

Date: 2026-11-11

## Asked (marcos)

- Pinch with two fingers to zoom the graphs on the phone.
- Header in two lines: the logo with a ⚙ that holds the look and the graph settings, a
  sign-out icon (sign-in for visitors) at the top right; Explore, Projects, Journal and
  Health below.
- A flag to switch the language (English and Spanish), for visitors too.
- Visitors may change the look without signing in, only in their browser (decision card,
  2026-11-11).

## Done

- `graph.js`: pinch zoom with two pointers (the point under the fingers stays put);
  embedded graphs keep one-finger vertical scrolling of the page.
- `templates/_menu.html`, `static/js/menu.js`: the header corner. The ⚙ menu builds the
  graph settings on pages with a graph (they left the graphs' corners, which keep + / − /
  Fit) and tells the graphs with a `micelio:graph-settings` event; the owner gets a link to
  Appearance, a visitor `templates/_look_fields.html`. A `<details>` flag menu lists the
  languages; the sign-out form and the sign-in link are icons. The landing shows the same
  corner.
- Languages: `i18n.LanguageMiddleware` (pure ASGI) reads the `micelio_lang` cookie into a
  context variable; `t()`, `{{ language }}`, dates and category names follow it.
  `GET /language/<code>?next=` sets the cookie and goes back (local paths only); it is open
  to visitors. Each locale names its flag and itself (`site.flag`, `site.language_name`).
- A visitor's look: `look-early.js` (in `<head>`, before paint) applies the saved palette
  (`/theme.css?palette=`), fonts and sizes; `look.js` wires the fields. `/theme.css`,
  `/api/graph` and `/api/landing` take `?palette=`, recoloring only that answer; an unknown
  name is the site's own look.
- Swatches are SVG rects: the app's CSP blocks `style=""` attributes.

## Tests

`tests/test_header_and_languages.py` (header layout, flag and cookie, refusing unknown
codes and off-site `next`, the visitor's corner and look, `?palette=` only recoloring that
request) and an updated `tests/test_graph_settings.py`. Checked by hand in Chromium,
desktop and phone width, signed in and as a visitor; pinch checked with emulated touch.
All checks pass (325 tests).
