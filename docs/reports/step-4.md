# Step 4 report: the graph

Date: 2026-11-09

## Done

- **`/api/graph?scope=all|project:<slug>|note:<slug>`** (`graph.py`): plain JSON, no
  renderer assumptions, so a 3D view can read it later (§7). Each node has `id`, `title`,
  `type`, `category`, `categories`, `bridge`, `status`, `degree`, `public`, `href`, `ghost`,
  `faded` and `focus`; each edge `id`, `source`, `target`, `faded`. The payload also carries
  the categories (key, translated name, color) and the types hidden by default.
  - `all`: every note, every link and the ghost nodes of missing notes.
  - `project:<slug>`: the index note (focus), its notes and the links among them, ghosts
    linked from them, and, faded, the other projects its bridge notes also belong to.
  - `note:<slug>`: the note and everything one link away in either direction.
  - A bad scope answers 400, an unknown slug (or a note asked as a project) 404. No caching.
- **`/explore`**: the graph of everything, full screen, with a side panel: search (by part
  of a title, accents ignored; Enter zooms to the matches or opens the only one; Escape
  clears), filters by type, category and status (journal and source off by default, from
  `graph.hide_by_default`), the 5 latest conversations and every note as a text list.
- **Project and note pages**: "Map of the project" (concentric: project in the middle, its
  notes around it, faded bridges outside) and "Neighborhood" (the note and its 1-hop links).
- **Drawing** (`static/js/graph.js`, `explore.js`, `graph-embed.js`): ES modules, no build
  step. Shapes per §7 (project large circle, note small circle, journal square, source
  triangle, ghost dashed), size grows with links, bridges neutral with a double border.
  Hover shows title, type, status and bridge; click opens the note. Colors come from the
  theme and follow a change of system theme; every node has a ring in the text color, so
  light fills (the yellow category) stay visible on the light theme. Animation is skipped
  under `prefers-reduced-motion`.
- **Cytoscape.js 3.34.4**, vendored in `static/vendor/cytoscape/` with its MIT license and
  the npm integrity hash in `static/vendor/README.md`. A test pins the version.
- **Browser strings**: `/static/locales/<lang>.json`, built at start from the `graph`,
  `type`, `status` and `category` tables of the locale (English fallback merged in).
  Unknown languages answer 404. Served without sign-in, as they are not private.
- **Languages**: every new string in `en` and `es`; a test checks that the Spanish graph
  pages show no English interface text.
- **Navigation**: "Explore" is the first link of the top bar.

Tests: 227 (45 new), coverage 99 %. Checked in Chromium in both themes and languages,
desktop and phone width; no console errors and no CSP violations.

## Decisions taken while building

- Cytoscape.js injects a one-line `<style>` element, which the CSP blocks. It skips that
  when an element with id `__________cytoscape_stylesheet` exists, so `graph.css` is
  linked with that id and carries the rule itself. No CSP change was needed.
- Layouts: `cose` (force-directed) for the global graph, `concentric` around the focus for
  project and note graphs, which reads better with few nodes.
- `degree` is the note's links in the whole vault, not inside the scope, so a node has the
  same size on every graph.
- The global graph sends every node, journal and source included; the page hides them. The
  API stays a plain description of the vault.

## Open points

- Anonymous visitors: `/api/graph` and `/explore` need sign-in today, like every page.
  Step 6 makes them show public notes only (§9), with the leak tests.
- The faded projects on a project graph are not repeated in the page's text list; the
  bridge mark on each note already says it is shared.
- The `cose` layout is not seeded, so the global graph can look slightly different on each
  load. The landing (step 5) uses its own seeded layout.
