# Report: graph settings panel

Date: 2026-11-10

## Asked

marcos: a settings panel on the graph, from the interface, to set the space between nodes
and the size of the names; long names shown whole only when the cursor is over them; zoom;
and the chosen settings remembered.

## Done

- **Panel** (`static/js/graph.js`, `controls()`): a ⚙ button in the top right corner of
  every graph (Explore, a note's neighborhood, a project's scene) next to + / − / Fit.
  It opens a glass panel with:
  - *Space between nodes*, 50–250 %. It stretches the links, the push between nodes and
    their room in the seeded d3-force layout, so the map stays the same for the same vault
    and setting. It lays the graph out again when the slider is let go.
  - *Size of the names*, 60–200 %, a `--label-zoom` CSS variable multiplied with the
    Appearance size (`--label-scale`), so the owner's site-wide size stays the base.
  - *Shorten long names* (on by default) and *Longest name shown*, 12–60 letters (28).
    Names are cut at a word when one is close, with "…". Projects are shortened too now.
  - *Reset*. Escape or a click outside closes the panel.
- **Whole name on hover**: pointing at a node (or focusing it with the keyboard) shows its
  full name in the palette's sun color, above the other names, also when names are hidden
  because the graph is zoomed far out. The tooltip with type and status stays.
- **Zoom everywhere**: the note's neighborhood and the project's scene now pan and zoom
  too. Inside those reading pages the plain wheel keeps scrolling the page; Ctrl/⌘ +
  wheel (and trackpad pinch) zooms. The note's underground moved to its own layer
  behind the graph so it stays put while the graph moves. The project scene does not zoom
  out past its painting and cannot be dragged off it.
- **Remembered**: `static/js/graph-settings.js` (no DOM) loads, cleans and saves the
  settings under `micelio.graph.v1` in `localStorage`, plus the last zoom per kind of
  graph, applied when the page opens. Fit resets it.
- Strings in `locales/en.toml` and `es.toml`; spec §7 and §15, CHANGELOG.

## Why the browser and not the data folder

These are one viewer's view settings, not the site's look: a phone and a desktop want
different spacing and zoom, and visitors can keep theirs too. In the browser they need no
new endpoint, form token or write on the server, and they cannot leak anything. The
site-wide defaults remain on the Appearance page (names on the graphs, §7b). If marcos
later wants the same settings on every device, they can move to the data folder as
owner-only defaults.

## Tests

- `tests/test_graph_settings.py`: the settings module run under Node.js (skipped without
  it): defaults, cleaning bad or hostile values, save and load, blocked or broken storage,
  shortening at a word; the strings in every language; one shared panel for every mode;
  no request to the server; visitors get the same code.
- `test_look.py`: "Ver todo" is now drawn by `graph.js`, so the test reads it from the
  Spanish browser strings.
- Checked by hand in Chromium (Spanish): Explore, a note and a project; changing every
  setting, reloading (kept), hover, phone width.

`uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`:
all pass (315 tests).
