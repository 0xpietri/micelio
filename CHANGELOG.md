# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-10

The first release: a folder of Markdown notes shown as a forest of ideas, read-only and
self-hosted.

### Added

**Reading the vault**

- Vault reader: frontmatter, titles and Obsidian-style wikilinks (aliases, headings, paths);
  hidden folders and Syncthing conflict copies are skipped.
- In-memory index with backlinks, project membership, bridges, ghost links and orphans,
  refreshed from file modification times.
- `mycelium check` lists problems in a vault; `mycelium serve` runs the site.
- `mycelium.toml` loading and validation: site, vault folders, categories with mushroom
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
  Mycelium (SIL OFL).

**Languages**

- English and Spanish interfaces, including the names of the default categories; own
  categories take `label = "Art"` or `label = { en = "Art", es = "Arte" }`; dates per
  language and in the configured time zone. Adding a language takes one file.

**Sign-in and sharing**

- Sign-in for one person: argon2 password and TOTP code, server-side sessions in SQLite,
  lockout after repeated failures, `auth.mode = "none"` for gateways, and `mycelium user`
  commands to create the secrets. On `127.0.0.1` with no secrets, sign-in is off.
- Public notes: anonymous visitors see the landing, `/explore`, `/projects`, the journal
  and the APIs built from `public: true` notes only. Private notes do not exist for them:
  no titles, links, nodes, ghosts or counts, and their URLs answer 404.
- Security headers (CSP without inline code, no framing) on every response.

**Installing**

- A Docker image, `ghcr.io/0xpietri/mycelium`, for `linux/amd64` and `linux/arm64`: a
  non-root user, a read-only root filesystem, the vault mounted read-only, one data volume
  and a health check. `compose.example.yml` runs it on the sample vault in one command.
- The Python package `mycelium-notes` on PyPI: `uvx mycelium-notes serve --vault ~/Notes`.
  Once installed, the command is `mycelium`.
- `mycelium serve` takes its defaults from `MYCELIUM_HOST`, `MYCELIUM_PORT` and
  `MYCELIUM_FORWARDED_ALLOW_IPS`.
- Self-hosting guides for Mycelium plus a notes MCP server, on your own computer or on a
  server.
- A sample vault in `examples/vault`, CI on Linux, macOS and Windows, and releases from a
  tag (image, package and GitHub release).

[Unreleased]: https://github.com/0xpietri/mycelium/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/0xpietri/mycelium/releases/tag/v0.1.0
