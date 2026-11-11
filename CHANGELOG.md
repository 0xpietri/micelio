# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/0xpietri/micelio/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/0xpietri/micelio/releases/tag/v0.1.0
