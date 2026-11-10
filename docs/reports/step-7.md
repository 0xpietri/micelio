# Step 7 report: the look on every page

Date: 2026-11-10

## How it was decided

marcos asked, after step 6, that the landing's painting be part of the whole interface and
that every graph be drawn as mycelium instead of plain circles. It became a new step
before the release (§14, which now has eight steps). It started with a static mockup of
Explore, a project, a note, the projects list and the journal with the four palettes.
marcos then asked for the owner to choose the titles, the fonts and the sizes as well as
the colors, and the mockup grew a "Names and lettering" section. He approved it and
decided two more things:

- **No light theme.** One dark look built from the palette.
- **The landing's engine replaces Cytoscape.js** for every graph.

All of it is written into the spec: the new §7c, §7 (drawing, shapes, layout), §7b
(names and lettering), §4 (`[typography]`, `graph.max_nodes`), §14 and §15.

## Done

- **Background on every page**: `base.html` draws the painting (or the uploaded image)
  as a fixed SVG behind the page, cropped from the template so it works without
  JavaScript: reading pages show the horizon at the top, `/explore` only the
  underground. When the background is recolored, `static/js/backdrop.js` adds the same
  SVG filter the landing uses. The landing keeps its own scene.
- **Glass and pills**: `micelio.css` is rewritten around the palette: ink glass panels
  with the dark outline, pill navigation, titles in the title font with the poster
  effect. No `prefers-color-scheme` is left in any stylesheet.
- **One engine**: the landing's drawing moved to `static/js/draw.js` (species, clouds,
  hyphae, crystals, the recolor filter, seeded random, strings). `landing.js`,
  `graph.js` and `specimens.js` import it.
- **Graphs as mycelium** (`graph.js`): projects are their category's mushroom grown by
  status, notes spore clouds glowing in their category's color (dashed ring for a
  bridge), journal notes golden spores, sources crystals, missing notes faint dashed
  rings; links are glowing hyphae with twigs and sparks. Seeded `d3-force`, so the same
  vault draws the same map. Three modes:
  - `free` (`/explore`): drag to pan, wheel and buttons to zoom, Fit; names of notes
    hide when zoomed far out; over `graph.max_nodes` (400) only the most connected are
    drawn and the hint says how many more there are.
  - `box` (the note's neighborhood): a fixed picture over the underground of the
    painting.
  - `forest` (the top of a project page): the project's mushroom on the soil line, its
    notes below, the other projects its bridge notes reach standing faded at the sides;
    the title over the sky.
  - Search, filters, Escape, Enter (opens the only match or zooms to the matches) work
    as before. Filters are chips; the checkboxes stay for keyboards and forms. The type
    chips and the "How to read it" legend show the real marks.
- **Lists**: projects are cards with their mushroom on a strip of the painting and a few
  threads, grouped by category; "Part of" on a note shows each project's mushroom;
  notes, sources and journal notes in lists get a small spore, crystal or golden icon;
  the journal is a timeline of golden spores.
- **Names and lettering** (Appearance page and `[typography]`): site name (empty uses
  `site.title`), title font (Shrikhand, Righteous, Bagel Fat One, Fraunces Black), title
  effect (poster or plain), text font (system, Atkinson Hyperlegible, Literata, Space
  Grotesk), and sizes for titles (70–140 %), text (14–20 px) and names on the graphs
  (80–150 %). The page previews changes live and shows the matching `micelio.toml`
  lines. Values saved on the page win over the config; bad values are ignored and keep
  what was there.
- **`/theme.css`** now also carries the stem, spore and crystal colors and the type
  settings as custom properties; font stacks live in `static/css/fonts.css`.
- **`/api/graph`** categories carry their `species`.
- **Fonts**: seven more Latin subsets vendored from `@fontsource` 5.1.0, each with its
  `OFL.txt`; listed in `static/vendor/README.md`.
- **Removed**: `static/vendor/cytoscape/` (434 KB) and the stylesheet-id workaround.
- **Languages**: every new string in `en` and `es`, font descriptions included.

Tests: 298 (14 new in `tests/test_look.py`, others updated), coverage 98 %. `ruff`,
`ruff format` and `mypy --strict` clean. Checked in Chromium at 1440 x 900 and
390 x 844, in English and Spanish, with the Psychedelic and Tokyo Night palettes, a
saved title font, text font, site name and title size: no console errors and no CSP
violations.

## Decisions taken while building

- The backdrop's crop is set by the template, not by JavaScript, so a page without
  scripts still shows the painting; only the recolor filter needs the browser.
- In the explore graph only projects are in the Tab order; the side panel already lists
  every note as a link. On project and note pages, where graphs are small, every node is.
- The project page no longer has a separate "Map of the project" box: the map is the
  scene at the top. Its heading stays for screen readers.
- The site name lives with the other Appearance choices; the landing's default title
  follows it when there is no `site.owner`.

## Open points

- On a phone the project scene hides the notes' names (they overlap); the tooltip and
  the list below the scene still name them.
- Very large vaults: the SVG draws up to `graph.max_nodes` nodes; beyond that the least
  connected notes are left out of `/explore` and listed in the side panel only.
- Fonts cover Latin scripts; other scripts fall back to the system font.
