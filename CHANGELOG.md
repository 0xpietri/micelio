# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Write your own words into a note from its page: said bubbles with your profile picture.
  On a computer a floating "Add a note" button puts one between the paragraphs at its height;
  on a phone hold a blank space between paragraphs and tap "Write a note". Bubbles can be
  edited, dragged (or moved with arrows) between paragraphs and deleted. Off unless
  `[editing] enabled = true`; a note changed meanwhile by the MCP or Obsidian is never
  overwritten.

- Two callouts for study notes. `> [!said]` shows the owner's own words in a speech bubble
  pointing at the speaker: a little mushroom in the category's color, or the owner's profile
  picture. `> [!takeaway]` closes a concept under "What you should know", handwritten in chalk on
  a chalkboard framed by logs, leaves and fly agarics. The Appearance page picks the board
  (black, green or white) and the handwriting (three hands); the chalk follows the palette.
- A profile picture on the Appearance page (PNG, JPEG or WebP, cut to a circle); without one,
  the little mushroom.
- The guide is a numbered outline: sections and sub-sections (1, 1.1, 1.1.1) come from the
  project's `## Guide` list and renumber themselves when a line is inserted. The order is a
  dropdown, previous / next skip the kinds you unticked, and the project's conversations
  sit at the top of the guide.
- Who wrote each note: `created_by` and `edited_by` (a Claude model or a person) in a small
  card with the dates, at the right of the note's title.
- Tags are pills that open the graph with every note carrying them.

- A guide at the left of every project and of each of its notes: the project's notes in
  order, structured (the default, as the project's `## Guide` section lists them, in
  stretches) or by date, with checkboxes for concepts, questions and gaps, and previous /
  next at the foot of each note. On a phone it folds above the page.
- Two new kinds of note: questions (`type: question`), asked along the way and drawn as a
  drifting spore, and gaps (`type: gap`), primordia of what is still missing to understand
  a topic, drawn dashed and see-through until they become notes.

- A Share switch on each project's page, a card on the soil line at the right like the growth card: a mushroom
  ("Spores in the air") when the project is shared, only its mycelium ("Underground") when
  it is private, in the growth card's colors. On a phone both cards share one row. The owner clicks it to share a project and the notes
  it links to with anyone, no account needed; visitors see the mushroom. Shared projects
  carry a badge on the projects list.

### Changed

- Graph threads are drawn once per pair: a note that links back to its project (or two
  notes that link each other) no longer shows two threads. Threads are almost straight
  now, with one soft bow, so they cross and tangle less.
- A project's growth card stands on the soil line, beside the mushrooms (on a phone it
  sits under the title), with a small mushroom that grows with the stage and breathes.
- A project's scene grows down with its underground: more notes or more spacing make it
  taller. Its + / − / ⚙ sit on the soil line, and + / − spread the notes and threads
  apart (names keep their size) while the sky and the mushrooms stay put.
- A project's title is smaller than the site's name, on one line when it fits.
- A third title effect on the Appearance page, "Sign": titles on a small dark sign in the
  theme's colors. "Poster" stays the default.
- On a phone a graph's corner shows only the ⚙; opening it brings + / − / Fit.
- The Appearance page has a button to put the soil line back where it started.
- The owner's hint on a project or source page moved into the mushroom's (or mineral's)
  hover text and says what a click does.
- A project's created and updated dates moved into its growth card, in numbers.
- In the graphs a thread shows what it joins: a project's notes hang on solid threads in
  its color, journal entries on gold dots, sources on dashes, and links between notes are
  thin and faint. The threads no longer glow, so names read better.

### Fixed

- Pages no longer flash the background in its original colors before the chosen palette
  recolors it: the recoloring comes with the page itself. The landing waits until its
  scene is drawn and then fades in, instead of jumping from one framing to another.

## [0.1.1] - 2026-11-11

### Added

- A ⚙ in every graph's top right corner with the viewer's settings: space between nodes,
  size of the names, and shortened long names that show whole while their node is
  pointed at or focused. The choices and the zoom are remembered in the browser
  (`localStorage`).
- Every graph pans and zooms, with + / − / Fit buttons, including the note's neighborhood
  and the project's scene; inside a reading page the wheel zooms only with Ctrl or ⌘.
- The Appearance page saves every change by itself and repaints the page at once; the
  Save buttons only remain without JavaScript. A chosen background uploads at once.
- "Make your own background" is folded on the Appearance page.
- A click outside the Appearance panel goes back to the previous page.
- Pinch with two fingers to zoom any graph on a phone or tablet.
- A two-line header: the site's name (larger on wide screens), Appearance, a language
  flag and a sign-out (or sign-in) icon; the sections below.
- Visitors can choose their own look (palette, fonts, sizes) under Appearance. It is kept
  in their browser and never changes the site for anyone else.
- Anyone can switch the interface language (English, Español) with the flag; the choice
  is kept in a cookie.
- A small, faint version in the bottom corner of every page but the landing, with a dot
  when the build brought news; it leads to `/changes`, which lists every change, newest
  first (the build's commit shows on hover). The changelog ships inside the package and the image, so the
  site never asks GitHub.
- On a project's page the owner clicks its mushroom to choose its species, color and
  size; on a source's page, its mineral (diamond, emerald, amber, quartz, amethyst) and
  color. Saved at once in the data folder, never in the notes, and shown on every graph,
  the project list and the landing.
- A project's scene shows how it grows: a small card in its corner with twelve weekly
  bars (notes added or edited, journal entries) and a stage, Dormant, Germinating,
  Growing or Fruiting, from the last thirty days. It replaces the category, type and
  status line over the title.
- Clicking a note on the landing dives underground: the sky slides up, the soil fills
  the view, and `/explore` rises centered on that note with its neighbors lit
  (`/explore?focus=<note>`). Ctrl/⌘-click still opens the note; reduced motion skips
  the animation.

### Changed

- An empty tagline on the Appearance page now shows no tagline instead of the default.
- The header is one line: the name, the sections, then Appearance, the language and
  signing out (the sections wrap below on a phone). On the landing the two buttons sit
  on the headline's line.
- Space between nodes goes up to 600 %. Zoomed out, names keep a readable size, and
  names that would overlap hide behind the better connected node's (pointing at a node
  shows its name). Better connected nodes show longer names.
- How to use a graph moved behind a small ⓘ in its corner.
- A project's scene is taller, starts at the very top under the header (the painting
  is one piece, no seam) and shows the sky, as on the landing.
- In the graphs, notes are plain dots in their category's color and the links show
  clearly (no more spore clouds or twigs there; the landing keeps them). Projects glow,
  each in its own shade of its category's color. Sources are minerals (a diamond by
  default). Clicking a name opens its node, like clicking the node.

### Fixed

- After a deploy, browsers kept the previous build's styles and scripts for months (every
  build's files have the same date), so pages could look broken and the graph settings
  do nothing. Static files now carry a hash of their content and are checked each time,
  and the first page from a new build tells the browser to drop what it cached before
  (`Clear-Site-Data`), so nobody needs to force a reload.
- The site's name and the titles kept the old palette's colors after a change on the
  Appearance page: a cache in front of the site kept `/theme.css`. Its address now
  changes with the theme. Project names in the list take the palette's title color
  instead of the link color, which was a light blue in every palette.

## [0.1.0] - 2026-11-10

The first release: a folder of Markdown notes shown as a forest of ideas, read-only and
self-hosted. The project was called Mycelium while it was built; it is released as Micelio
(Spanish for mycelium).

### Added

**Reading the vault**

- Vault reader: frontmatter, titles and Obsidian-style wikilinks (aliases, headings, paths);
  hidden folders and Syncthing conflict copies are skipped.
- In-memory index with backlinks, project membership, bridges, ghost links and orphans,
  refreshed from file modification times.
- `micelio check` lists problems in a vault; `micelio serve` runs the site.
- `micelio.toml` loading and validation: site, vault folders, categories with mushroom
  species, graph, landing, typography, sign-in and data folder.

**Pages**

- The landing: the vault drawn as a forest over a painted background. Projects are
  mushrooms (eight species, grown by status, sized by notes), notes are spore clouds in
  the mycelium, links are hyphae with sparks, sources are crystals and the latest journal
  notes are golden spores; positions from a vendored, seeded d3-force.
- The graph of everything at `/explore`, with search and filters, plus a graph on every
  project and note page, all drawn as mycelium by the same engine (`static/js/draw.js`);
  `graph.max_nodes` keeps big vaults readable.
- Reading pages: projects by category, each project with its notes and conversations,
  notes with backlinks and the projects they belong to, the journal and a health page.
- Markdown rendered like Obsidian (wikilinks, ghost links, callouts, task lists, tables,
  footnotes) and sanitized with nh3.
- `/api/graph` and `/api/landing` with the same data as the pages; `/healthz` for
  containers and monitoring.

**Look**

- One dark look on every page: the painted background, text on ink glass, pill buttons.
- The Appearance page (`/appearance`): four palettes (Psychedelic, Tokyo Night, Catppuccin
  Mocha, Rosé Pine) that recolor the background, the mushrooms and the categories; an
  uploaded background; the soil line; the title, tagline and site name; fonts, title
  effect and sizes; and a prompt builder for painting a background with any image
  generator. Saved in the data folder, never in the vault. Seven fonts ship with
  Micelio (SIL OFL).

**Languages**

- English and Spanish interfaces, including the names of the default categories; own
  categories take `label = "Art"` or `label = { en = "Art", es = "Arte" }`; dates per
  language and in the configured time zone. Adding a language takes one file.

**Sign-in and sharing**

- Sign-in for one person: argon2 password and TOTP code, server-side sessions in SQLite,
  lockout after repeated failures, `auth.mode = "none"` for gateways, and `micelio user`
  commands to create the secrets. On `127.0.0.1` with no secrets, sign-in is off.
- Public notes: anonymous visitors see the landing, `/explore`, `/projects`, the journal
  and the APIs built from `public: true` notes only. Private notes do not exist for them:
  no titles, links, nodes, ghosts or counts, and their URLs answer 404.
- Security headers (CSP without inline code, no framing) on every response.

**Installing**

- A Docker image, `ghcr.io/0xpietri/micelio`, for `linux/amd64` and `linux/arm64`: a
  non-root user, a read-only root filesystem, the vault mounted read-only, one data volume
  and a health check. `compose.example.yml` runs it on the sample vault in one command.
- The Python package `micelio` on PyPI: `uvx micelio serve --vault ~/Notes`.
- `micelio serve` takes its defaults from `MICELIO_HOST`, `MICELIO_PORT` and
  `MICELIO_FORWARDED_ALLOW_IPS`.
- Self-hosting guides for Micelio plus a notes MCP server, on your own computer or on a
  server.
- A sample vault in `examples/vault`, CI on Linux, macOS and Windows, and releases from a
  tag (image, package and GitHub release).

[Unreleased]: https://github.com/0xpietri/micelio/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/0xpietri/micelio/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/0xpietri/micelio/releases/tag/v0.1.0
