# Micelio: specification v0.1

Status: draft, 2026-11-09, for marcos's review.
Repository: `0xpietri/micelio` (public, MIT). Reference deployment: `micelio.pietri.dev`.

## 1. Purpose

Micelio is a small, self-hosted website that shows a folder of Markdown notes as a network of ideas: a list of projects by category, a graph per project and one graph of everything on the home page.

The notes are written mostly by AI assistants through an MCP server (for example Claude or ChatGPT in a voice call) and by people in Obsidian. Micelio never writes them. It is the window, not the pen.

It is meant to be useful to anyone with an Obsidian-style vault, and to read as a portfolio piece: clean code, tests, docs and a five-minute install.

## 2. Principles

1. **The files are the truth.** Everything Micelio shows is derived from the Markdown files at request time. Delete its data folder and nothing is lost.
2. **Read only.** No editor, no Git operations, nothing written to the vault, which is mounted read-only. The one exception to "no uploads" is the landing's background image (§7b), stored in Micelio's own data folder, never in the vault.
3. **Model-agnostic.** Nothing depends on a particular LLM or MCP server. Any tool that writes the documented frontmatter works.
4. **Configuration, not code.** Categories, colors, folder names, titles and texts live in `micelio.toml`. Nothing personal is hard-coded.
5. **No build step.** Server-rendered pages (FastAPI + Jinja), plain CSS and JavaScript modules, vendored libraries. No inline `<script>` or `<style>`, so a strict CSP works.
6. **Small.** One container, one process, SQLite for its own state, under 100 MB of RAM for a vault of a few thousand notes.

## 3. The vault model

### 3.1 Folders (defaults, configurable)

| Folder | Holds |
| --- | --- |
| `projects/` | One index note per project |
| `notes/` | Atomic notes, one idea each |
| `journal/` | One note per conversation |
| `sources/` | Papers, articles, transcripts |

`vault_root` in the config points at the notebook folder, which may be a subfolder of a larger vault (marcos's: `ideas/` inside his Obsidian vault). Files outside it are ignored, and so are hidden paths, `.trash/` and Syncthing conflict copies (`*.sync-conflict-*`).

### 3.2 Frontmatter

```yaml
---
type: project        # project | note | question | gap | journal | source
created_by: claude-opus-5-5   # optional: who wrote it (§3.4)
edited_by: marcos             # optional: the last to edit it
category: science    # projects only; values come from the config
status: draft        # draft | active | paused | closed
tags: [astronomy, gravity]
created: 2026-11-09
updated: 2026-11-09
public: false
---
```

- A note without `type` is inferred from its folder.
- An unknown `category` or `status` value is shown as "unknown" and listed on a `/health` page, never a crash.
- `public` defaults to `false`.

### 3.3 Links and membership

- Wikilinks are resolved the way Obsidian does: `[[name]]`, `[[name|label]]`, `[[name#heading]]`, `![[embed]]`, by file name first, then by `aliases` in frontmatter, case-insensitive; ambiguity goes to the shortest path.
- A note **belongs to a project** when the project's index note links to it. Membership is never stored in the note itself.
- A link to a missing note is drawn as a "ghost" node (dashed) and listed on `/health`.

### 3.4 Project guides, questions and gaps (added 2026-11-11)

- **Guide.** Every project and every note of a project shows the project's guide at the left: its notes as a numbered outline, with the current note marked and previous / next at the foot of the note. A dropdown chooses the order: **structured** (the default) or **by date** (`created`). Checkboxes choose which kinds it lists (concepts, questions, gaps), and previous / next skip what is not shown. Both choices are kept in the browser's `localStorage` (`micelio.guide.v1`), like the graph settings. On a phone the guide folds above the page.
- **Conversations** that touch the project (journal notes linking it or its notes) sit at the top of the guide, folded, newest first. A journal note of the project shows the guide too.
- **The structured order is written in the vault**, by the model through the notes MCP, never by Micelio: a `## Guide` section in the project's index (headings from `[guide] headings`, `Guide` and `Guía` by default, compared without case or accents) holding a nested list. A list item with a link is a note; an item without one is a section, and the items indented under an item hang from it; `###` and `####` headings are sections too. **Nobody writes numbers**: Micelio numbers the outline from its shape (1, 1.1, 1.1.1, 2 …), so inserting a line renumbers everything after it, and Obsidian renumbers an ordered list the same way. Empty sections are left out. The section is shown in the guide, not again in the rendered body, and reads as a plain nested list in Obsidian. A project without it is guided in the order its index first links each note; notes the index links outside the guide come last, under "Not in the guide yet". Links between notes in different sections are ordinary links in the notes and show in the graphs.
- A note in more than one project shows the first project's guide by name; `?guide=<project>` picks another, and the guide's links keep it.
- **`type: question`**: a side question asked along the way, on topic but not part of the project's skeleton (for example, "the contest that chose SHA-3"). Drawn as a drifting spore: lighter, ringed, with a small spore beside it.
- **`type: gap`** (a **primordium**): something still missing to understand the project, written by the model where it belongs in the guide, with two lines on what is missing and why it matters. Drawn as a primordium, the knot a mushroom grows from: dashed and see-through in the project's color. When it is learned the model turns it into a `note` and it "comes out". A link in the guide to a note that does not exist yet also shows as a gap, to the owner only (visitors see no ghosts, §9). Gaps do not count for the project's growth (§7c).
- Both live in `notes/` and follow the same rules as notes; they only change how they are drawn and listed.
- **Who wrote a note**: `created_by` (never changes) and `edited_by` (the last to touch it), each a model id such as `claude-opus-5-5` (shown "Claude Opus 5.5") or a person's name. The model sets them when it writes; the owner changes `edited_by` by hand when editing. A note's head shows its dates and these names in a small card at the right of the title (under it when there is no room).
- **Tags** show as small pills and link to `/explore?tag=<tag>`, which lights and frames every note carrying the tag.

## 4. Configuration (`micelio.toml`)

```toml
[site]
title = "Micelio"
owner = "Marcos Pietri"    # shown on the landing: "Marcos Pietri's micelio"
headline = "The micelio of Marcos"   # optional: replaces that title; or { en = "...", es = "..." }
tagline = "A living notebook of ideas"
language = "en"            # UI language (see §5a); note content is shown as written
timezone = "America/Argentina/Buenos_Aires"

[vault]
root = "/vault/ideas"
projects = "projects"
notes = "notes"
journal = "journal"
sources = "sources"

# The default keys are named in the interface language (locales, `category.<key>`).
# Own categories add `label = "Art"` or `label = { en = "Art", es = "Arte" }`.
# `color` is optional: without it the category takes its color from the palette (§7b).
[[categories]]
key = "science"
species = "fly-agaric"     # mushroom drawn on the landing (§7a)

[[categories]]
key = "philosophy"
species = "shaggy-inkcap"

[[categories]]
key = "study"
species = "morel"

[[categories]]
key = "free"
species = "chanterelle"

# Defaults for the Appearance page (§7b); what is saved there wins.
[landing]
palette = "psychedelic"    # psychedelic | tokyo-night | catppuccin | rose-pine
soil = 52                  # soil line, % of the background's height

# Fonts and sizes on every page (§7b); what is saved on the Appearance page wins.
[typography]
title_font = "shrikhand"   # shrikhand | righteous | bagel-fat-one | fraunces
text_font = "system"       # system | atkinson-hyperlegible | literata | space-grotesk
title_size = 100           # % (70-140)
text_size = 16             # px (14-20)
graph_labels = 100         # % (80-150)
title_effect = "poster"    # poster | plain

[graph]
hide_by_default = ["journal", "source"]
max_nodes = 400            # over this, /explore draws only the most connected notes

[auth]
mode = "local"             # local | none (when an external gateway handles it)
```

Secrets (password hash, TOTP secret, session key) come only from environment variables. The repo ships `micelio.example.toml` and `.env.example` with placeholders.

## 5. Sign-in

- One user. argon2 password hash and a TOTP code (30-second steps, one step of drift, a used code is refused).
- Signed session cookie, `HttpOnly`, `Secure`, `SameSite=Strict`, 12 h, stored server-side in SQLite so sign-out revokes it.
- 5 failures per IP in 15 minutes lock that IP for the window.
- `auth.mode = "none"` turns sign-in off for people who put Cloudflare Access or another gateway in front. The README says so plainly.
- `micelio user set-password`, `micelio user totp` (with a QR code in the terminal) and `micelio user session-key` print the three secrets as `.env` lines; `micelio user sign-out-all` ends every session.
- Listening on loopback only with none of the secrets set, sign-in is off (the personal-computer case of §10). On any other address `auth.mode = "local"` refuses to start until all three are set. Setting some but not all is always an error.
- Password and code are asked together and a failure never says which was wrong. A form token (HMAC with the session key) guards sign-in and sign-out.

## 5a. Interface languages

- English is the default and the reference. Every UI string has a key; templates call `t("projects.empty")`, never a literal.
- Translations live in one flat file per language: `micelio/locales/en.toml`, `es.toml`, … No compile step (unlike gettext `.po`/`.mo`).
- Strings the browser needs (graph tooltips, filters) are served from `/static/locales/<lang>.json`, generated from the same file at start.
- A missing key falls back to English; a test fails if a locale has keys English lacks or misses any key, so a partial translation is visible in CI.
- Adding a language = copy `en.toml`, translate, open a PR. `CONTRIBUTING.md` explains it in five lines.
- v0.1 ships `en` and `es`. Dates and numbers are formatted per language (Babel).

Since 2026-11-11 anyone can switch the interface language with the flag in the header (`/language/<code>`, kept in a `micelio_lang` cookie for a year); `site.language` is the default.

## 6. Pages and API

| Route | Shows |
| --- | --- |
| `/` | The landing: the owner's ideas drawn as a living forest floor (§7a) |
| `/explore` | The graph of everything, full screen; side panel with search, filters (category, status, type) and the 5 latest journal notes; `?tag=<tag>` lights the notes with that tag |
| `/projects` | Projects grouped by category: title, status, number of notes, last conversation |
| `/projects/<slug>` | Thesis, open questions, the project's graph, its notes, its guide (§3.4) |
| `/notes/<slug>` | The rendered note, backlinks, the projects it belongs to, its 1-hop neighborhood graph, its project's guide (§3.4; `?guide=<project>` picks one) |
| `/journal` | Conversations, newest first |
| `/health` | Unknown frontmatter values, broken links, orphans (signed-in only) |
| `/login`, `/logout` | Sign-in |
| `/api/graph?scope=all\|project:<slug>\|note:<slug>` | Nodes and edges as JSON |
| `/healthz` | Liveness for the container and monitoring |
| `/appearance` | Palette, background, title and the background prompt guide (§7b, signed-in only) |
| `/api/landing` | What the landing draws, as JSON (§7a) |
| `/changes` | Every change, newest first, from the packaged `CHANGELOG.md` (§7c, visitors too) |

Markdown is rendered with markdown-it-py and sanitized with nh3. Wikilinks become links to `/notes/<slug>`. Callouts (`> [!warning]`) and task lists render like Obsidian. Two callouts have a look of their own and no heading unless one is given: `> [!said]` (the owner's own words, a speech bubble pointing at a small mushroom) and `> [!takeaway]` (a small sign that closes a concept). Times are shown in the configured time zone. Links to projects go to `/projects/<slug>` (and `/notes/<project>` redirects there); links to missing notes render as dashed ghost text; `![[file.png]]` and other non-note embeds render as their name (attachments are not served in v0.1). Category colors, the palette and the type settings come from a generated `/theme.css`, so pages need no inline styles. There is one dark look built from the palette (§7c); the light theme of step 3 was dropped on 2026-11-10.

## 7. The graph

- **Drawing**: since 2026-11-10 the graphs are drawn as mycelium with the landing's own engine (§7c): SVG over the vendored `d3-force`, served from `/static`. 2D. (Steps 4–6 used Cytoscape.js; it was removed.)
- **`/api/graph` is renderer-agnostic**: plain nodes and edges with `type`, `category`, `status`, `degree`, `public`. A 3D view (3d-force-graph) can be added later as one more page without touching the API.
- **Color**: a project takes its category color. An atomic note takes the color of the project that links it; linked from projects of different categories, it is a **bridge**: neutral fill, double border.
- **Shape** (§7c): project = its category's mushroom, grown by status; note = a spore cloud glowing in its category's color, with a dashed ring when it is a bridge; question = a drifting spore; gap = a dashed primordium (§3.4); journal = golden spores; source = a crystal; missing note = a faint dashed ring. Links are glowing hyphae. Size grows with links.
- **Project graph**: the index, its notes, the links among them, and the bridges to other projects faded.
- **Defaults**: journal and source nodes hidden on the global graph, with a toggle.
- **Click** opens the note. Hover shows its title and status.
- **Layout**: seeded, so the same vault always draws the same map. Every graph pans and zooms (drag, wheel, buttons; inside a reading page the wheel zooms only with Ctrl or ⌘, so the page still scrolls); over `graph.max_nodes` only the most connected notes are drawn and the page says how many more there are.
- **Viewer settings** (added 2026-11-10): a ⚙ panel on every graph sets the space between nodes (50–250 %), the size of the names (60–200 %, on top of the Appearance size of §7b), and whether long names are shortened and to how many letters (12–60, 28 by default; a name shows whole while its node is pointed at or focused). The panel, the zoom chosen on each kind of graph and a reset are kept in the browser's `localStorage`, never on the server: they are one viewer's settings, visitors keep theirs too, and nothing new is written to the data folder.
- Accessible: every graph page also lists its nodes as text links; every mark is a real link with a name, and the keyboard reaches the projects (on small graphs, every node).

## 7a. The landing: above and below the ground

The home page is the project's signature: a generative illustration drawn from the vault's real data, not a stock image. The soil line splits the screen.

**Look (mockup approved 2026-11-10).** Illustrated, psychedelic palette (neon green, magenta, cyan, electric blue, orange, gold) with dark outlines. A dusk sky, two layers of distant mountains, grass with small flowers on the soil line. No tree. Underground: a dark stained-glass mosaic, white branching hyphae and notes as fuzzy clouds of spores. The colors follow the chosen palette (§7b).

**Above ground: what has surfaced.**
- Each **project** is a mushroom. v0.1 ships eight species with distinct silhouettes (fly agaric, shaggy inkcap, morel, chanterelle, liberty caps, coral fungus, parasol, glowing bonnets); each category picks one species in `micelio.toml`. Size = its number of notes.
- **Two layers** (decided 2026-11-09): a painted background image (sky, sun, mountains, grass, underground mosaic; no mushrooms or micelio) generated once and shipped as a static asset, and the live layer drawn in code from the vault on top of it.
- Its status is its growth: `draft` = a small button, `active` = a full open cap, `paused` = faded, `closed` = dried and bent.
- Hover shows the title; click opens the project.

**Below ground: where ideas connect.**
- **Atomic notes** are knots in the mycelium, under the mushroom of their project.
- **Links** are hyphae: thin, softly glowing threads. A **bridge** note sends a thicker hypha across to another mushroom's network.
- **Sources** are mineral crystals the hyphae reach for (nutrients). Crystals, not stones, so they never mix with stones painted in a background.
- **Journal notes** are spores on the surface: the latest 5 drift near the mushrooms they touched.

**Movement.** On load the hyphae grow out from each mushroom; then a faint pulse travels along random links. Everything stops under `prefers-reduced-motion`.

**Text.** Top left, always on one line (it shrinks to fit): the headline, by default `site.owner`'s name, e.g. "Marcos Pietri's micelio". The text is editable: `site.headline` in the config or the Appearance page. Under it the tagline and two buttons: *Explore the graph* (`/explore`) and *Projects* (`/projects`).

**Technique.** SVG drawn by our own module (`static/js/landing.js`) over the background image; SVG rather than Canvas so every mushroom and note is a real link the keyboard can reach. Positions from a vendored `d3-force` (underground nodes kept below the soil line, each project's notes pulled under its mushroom). Mushroom shapes are parameterized SVG paths, drawn procedurally, no image files. The data comes from `/api/landing`. Seeded by the vault's content, so the same vault always draws the same forest. Over about 300 notes, only the most connected are drawn underground and a counter says how many more there are.

**Visitors.** Anonymous visitors see the same landing built from public notes only (§9). With nothing public it shows the soil, one sprout and the sign-in button.

**Accessibility.** A visually hidden list under the canvas names every mushroom and note with links; keyboard focus moves through the mushrooms.

## 7b. Appearance

A signed-in page, `/appearance`, decided by marcos on 2026-11-10. What it saves lives in the data folder (`data/site.sqlite3` and `data/backgrounds/`), never in the vault; deleting the data folder brings back the defaults of `micelio.toml`.

- **Palette**: four templates of analogous colors. *Psychedelic* (the original neon), *Tokyo Night*, *Catppuccin Mocha* and *Rosé Pine* (the last three follow those MIT-licensed themes). A palette sets the mushrooms (by category order; an explicit `color` in the config wins), the hyphae, the spores, the crystals and the landing's buttons, and the category colors on every page and graph.
- **Background**: the included painting (*Psychedelic dusk*, 1536 x 1024 WebP) or an image the owner uploads. PNG, JPEG or WebP, at most 8 MB, at least 1200 x 800; the type is checked from the file's bytes, never its name. One uploaded image is kept; a new upload replaces it. Wider or taller images are cropped to fill the screen.
- **Recolor**: on by default for the included painting, off for an upload. It maps the image's brightness onto the palette's ramp with an SVG filter in the browser; the file itself is never changed.
- **Soil line**: where the ground starts, 30–70 % of the image's height (52 % for the included painting).
- **Title and tagline**: optional text that replaces `site.headline` and `site.tagline`. Until the page is first saved the tagline shows the default; once saved, an empty tagline shows nothing (2026-11-11).
- **Prompt guide**: a form that builds a prompt for any image generator (ChatGPT, Gemini, Midjourney, Stable Diffusion). The format rules are fixed and shown as such: 1536 x 1024 (3:2), the horizon at the soil line, a calm top-left corner for the title, a dark low-contrast underground, nothing tall on the horizon, no mushrooms, trees, threads or text. The owner writes the creative parts: style, sky, horizon, underground, colors (prefilled from the palette) and mood. A button copies the result. The prompt is in the interface language.
- **Names and lettering** (added 2026-11-10): the site's name (empty: `site.title`), the title font (Shrikhand, Righteous, Bagel Fat One, Fraunces Black), the title effect (*poster*: dark outline and colored shadow, or *plain*), the text font (the system's, Atkinson Hyperlegible, Literata, Space Grotesk), and three sizes: titles 70–140 %, text 14–20 px, names on the graphs 80–150 %. Every font ships with Micelio (SIL OFL, Latin subsets); nothing loads from another site. The page previews a change before it is saved and shows the matching `[typography]` lines of `micelio.toml`, whose values are the defaults.
- **Saves itself** (2026-11-11): every choice is saved as soon as it changes (text after a pause in typing) and the page repaints the theme and background in place; there is no Save button unless JavaScript is off. A chosen image uploads at once. The prompt guide is folded. A click on the painting around the panel goes back to the page the owner came from.
- Saving needs the sign-in form token (HMAC, like sign-out). With `auth.mode = "none"` the page is as open as the rest of the site, so the gateway in front must protect it.

## 7c. The look on every page

Decided by marcos on 2026-11-10: the landing's painting is part of the whole interface, and every graph is drawn as micelio.

- **Background**: the painting (or the uploaded image, recolored when chosen) stays fixed behind every page. Reading pages show the horizon at the top and scroll into the underground; `/explore` shows only the underground. The landing keeps its own scene.
- **Header** (2026-11-11): two lines. First the site's name (larger on wide screens) and, at the right, Appearance (the owner's page; for visitors a menu with their own look), the language flag and an icon to sign out or in. Below, the sections. The graph settings are a ⚙ in each graph's top right corner, next to + / − / Fit.
- **A visitor's own look** (2026-11-11): palette, fonts, title effect and sizes, kept in the visitor's browser (`localStorage`); the palette's name goes to `/theme.css`, `/api/graph` and `/api/landing` as `?palette=`, which only recolor that answer. The site stays the owner's for everyone else.
- **Footer** (2026-11-11): every page but the landing ends with the last version, the build's commit (`MICELIO_REVISION`, set by the image) and "What's new", which unfolds the changes since that version (else the version's own). `/changes` lists every version's changes. Each change adds its line to `CHANGELOG.md` under Unreleased.
- **Glass**: text sits on ink-colored glass panels with the palette's dark outline; navigation is pill buttons; titles use the title font and effect of §7b.
- **One dark look**: no light theme; the palette sets every color.
- **Project page**: a scene at the top, the project's mushroom on the soil line, its notes as spore clouds below, the other projects its bridge notes reach standing faded at the sides; the title over the sky.
- **Note page**: the neighborhood drawn as mycelium over the underground of the painting.
- **Projects**: one card per project with its mushroom on a strip of the painting, grouped by category. **Journal**: a timeline of golden spores.
- **Engine**: one shared module (`static/js/draw.js`) draws the mushrooms, clouds, hyphae and crystals for the landing (`landing.js`), the graphs (`graph.js`) and the small mushrooms in lists (`specimens.js`). Vault text never enters markup; titles and links are set as attributes.

## 8. Reading the vault

- On start, walk `vault.root`, parse every note and keep an in-memory index (notes, links, backlinks, membership).
- On each request, re-check modification times (cheap `stat`, throttled to once every 2 s) and re-parse only changed files. A note written during a voice call shows up on reload.
- Paths are resolved under the vault root only; symlinks leaving it are refused.

## 9. Public notes

- `public: true` makes a note readable without signing in, at the same URL.
- A public project shows only its public notes, and its graph only public nodes.
- Links from a public note to a private one render as plain text, never as a link or a node, so a private title never leaks.
- An anonymous visitor sees only public notes everywhere: the landing (§7a), `/explore`, `/projects`, `/journal`, `/api/graph`, `/api/landing`. Private notes do not exist for them, not even as counts: a private note's URL answers 404, and `/healthz` leaves out the number of notes.
- Links to missing notes also render as plain text for visitors, with no ghost node, so a missing note and a private one look the same.
- A note is public when its own frontmatter says `public: true`; being linked from a public project does not make it public.
- **Shared projects.** The signed-in owner has a Share switch on each project's page (checked: shared, unchecked: private). Sharing a project makes it and the notes it links to readable by visitors, as if each said `public: true`; their other links to private notes still render as plain text. The choice is kept in the data folder (`site.sqlite3`), never written to the vault, and turning it off hides them again at once. A project already public in its frontmatter shows as shared and is changed in the vault.

## 10. Packaging

- Docker image built from a multi-stage Dockerfile: Python 3.12 slim, `uv` with a lockfile, non-root user, read-only root filesystem, the vault mounted read-only, one data volume for SQLite.
- Published to `ghcr.io/0xpietri/micelio` for `linux/amd64` on merges to `main` and on tags; `linux/arm64` only on release tags.
- `compose.example.yml` runs it against the bundled sample vault in one command.
- **New versions** (2026-11-11): the "New version" workflow (`version.yml`, started by `miceliodeploy edge` or by hand) numbers the version (the next patch after the last tag), moves `CHANGELOG.md`'s Unreleased changes under it, commits to `main`, tags `v<version>` and starts the image and package builds on that tag. Nobody tags by hand. Static files are served with `Cache-Control: no-cache` and a content ETag, since every build's files carry the same date.
- **Two ways to install, both first-class:**
  - *Server*: the Docker image (Linux, or Docker Desktop on macOS and Windows). Release images are `amd64` + `arm64`, so Apple Silicon and a Raspberry Pi work.
  - *Personal computer, no Docker*: a Python package on PyPI. `uvx micelio serve --vault ~/Obsidian` (or `pipx`) opens it on `http://localhost:8765`. Bound to localhost, sign-in is off by default there; it turns on when bound to another address.
- **Supported systems**: Linux, macOS and Windows. CI runs the tests on all three (cheap on a public repo). Paths go through `pathlib`; file names with accents, spaces and Windows reserved names are covered by tests on the sample vault.

## 11. Quality

- `ruff` (lint and format), `mypy --strict`, `pytest` with coverage reported; target 90 %.
- Tests run on the sample vault. Every behaviour change comes with tests.
- CI on pull requests: lint, types, tests, under 2 minutes; superseded runs are cancelled; the image builds only on `main` and tags.
- Semantic versioning, `CHANGELOG.md` (Keep a Changelog), GitHub releases.
- `README.md` (GIF of the graph, what it is in two lines, quick start, configuration, architecture diagram, security notes), `LICENSE` (MIT), `SECURITY.md`, `CONTRIBUTING.md`, issue and PR templates, Dependabot for pip, Actions and Docker.
- Each step ends with a short report in `docs/reports/`.

## 12. Sample vault

`examples/vault/`: about 30 notes in English across the four categories, with a few bridges, one ghost link, two journal notes, one source and some public notes. It drives the tests, the screenshots and the demo.

## 12a. Roadmap after v0.1

1. **Static export (v0.2).** `micelio export --public out/` writes a static site of the public notes only (landing, explore, projects, notes). It can be uploaded to GitHub Pages, Cloudflare Pages or Netlify for free, or zipped and sent. This is how someone without a server shares ideas. The landing and graph are already plain JS over `/api/graph`, so the export writes that JSON as a file.
2. **Obsidian plugin (v0.3).** The easiest path for non-technical people: install "Micelio" from Obsidian's community plugins, one click, on Windows, macOS, Linux and mobile. It shows the landing and the graph inside Obsidian and has an "Export public site" command. It reuses the same front-end modules (forest renderer, graph styles); only the data loading differs.
3. Self-hosting guides for technical users, in `docs/guides/`: Micelio plus a notes MCP server on their own computer (Linux, macOS, Windows, with a tunnel) or on a VPS. Each person runs their own stack.
4. Not planned: native installers (`.exe`, `.dmg`). They need paid code signing to avoid security warnings, and the plugin reaches the same people better.

## 13. Out of scope for v0.1

- Writing notes, Git operations, the MCP server itself, embeddings or semantic search.
- More than one user.
- Hosting other people's notes: there is no shared service; everyone self-hosts (decided 2026-11-09).
- The 3D view (§7 keeps the door open).

## 14. Steps

Each step ends with tests, a report and a stop for marcos's review.

1. **Skeleton.** Repo hygiene files, CI, config loading and validation, the sample vault, the vault parser and the in-memory index, `/healthz`.
2. **Sign-in.** Local auth with TOTP, sessions, lockout, CLI for secrets, `auth.mode = "none"`.
3. **Pages and languages.** `/projects`, `/projects/<slug>`, `/notes/<slug>`, `/journal`, `/health`; Markdown rendering and sanitizing; light and dark themes; `en` and `es` (§5a).
4. **Graph.** `/api/graph`, `/explore`, the project and note graphs, filters, search.
5. **The landing.** The forest floor of §7a and the Appearance page of §7b. Starts with a static mockup for marcos's approval before the real code (approved 2026-11-10).
6. **Public notes.** §9, with tests that no private title appears in any anonymous response.
7. **The look on every page.** §7c and the names and lettering of §7b: the painted background and glass on every page, the graphs drawn as mycelium (Cytoscape.js removed), one dark look, fonts and sizes on the Appearance page and in `[typography]`. Started with a static mockup approved by marcos (2026-11-10).
8. **Release v0.1.0.** Docker image, compose example, README with GIF and diagram, CHANGELOG, tag.

The deployment on factory (Caddy site, the notes MCP, the vault's Git timer, backups, monitoring) is tracked outside this repository.

## 15. Decisions

- 2026-11-09 (marcos): UI in English, easy to add languages (§5a); anonymous visitors see public notes only (§9); the owner's name in the config and an artistic landing with mushrooms above ground and mycelium below (§7a).
- 2026-11-10 (marcos): landing mockup approved. The title stays on one line and its text is editable; no tree. Four palettes (Psychedelic, Tokyo Night, Catppuccin Mocha, Rosé Pine) recolor the mushrooms and the background; the owner can upload a background, guided by a prompt builder; all chosen on a signed-in Appearance page that saves to the data folder (§7b). This relaxes principle 2 for that one image.
- 2026-11-10 (marcos): the landing's painting becomes part of the whole interface and every graph is drawn as mycelium (§7c), as a new step before the release. The light theme is dropped and Cytoscape.js is replaced by the landing's engine. The owner also chooses the site's name, the fonts and the sizes, on the Appearance page or in `micelio.toml` (§7b).
- 2026-11-09 (marcos): no hosted service for other people's notes. Technical users self-host, guided by `docs/guides/` (own computer with a tunnel, or a VPS); non-technical users get the Obsidian plugin (v0.3).
- 2026-11-10 (marcos): a settings panel on the graphs for spacing, name size, shortened names shown whole on hover, and zoom, remembered per browser (§7).
- 2026-11-10 (marcos): before the first release the project is renamed from Mycelium to **Micelio** everywhere: code, command, environment variables, `micelio.toml`, the image `ghcr.io/0xpietri/micelio`, the PyPI package `micelio` (`mycelium` was taken there), the repository and the site `micelio.pietri.dev`.
- 2026-11-11 (marcos): `miceliodeploy` installs what `main` has without a new version; `miceliodeploy edge` makes a new version from the changes gathered since the last one and installs it. The site lists each version's changes in a footer and at `/changes`.
- 2026-11-11 (marcos): a Share switch on each project's page shares the project and its notes with visitors (§9), kept in the data folder so the vault stays read-only.
- 2026-11-11 (marcos): a guide at the left of each project and its notes (§3.4), structured by default or by date; two new kinds of note, `question` (side questions) and `gap` (primordia, what is still missing), with their own look. The model writes the order and the gaps in the vault; Micelio only reads them.
- 2026-11-11 (marcos): the guide becomes a numbered outline (sections from nested lists, numbers computed, never written), the order a dropdown, previous / next follow the kinds shown, conversations at the top of the guide; `created_by` / `edited_by` on notes (decided: both, rather than only the last); dates in a card beside the title; tags as pills linked to the graph.
