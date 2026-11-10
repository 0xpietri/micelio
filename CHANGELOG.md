# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- The landing: the vault drawn as a forest over a painted background, projects as
  mushrooms (eight species, grown by status, sized by notes), notes as spore clouds in
  the mycelium, links as hyphae, sources as crystals and the latest journal notes as
  spores; positions from a vendored, seeded d3-force; `/api/landing` with the same data.
- The Appearance page (`/appearance`): four palettes (Psychedelic, Tokyo Night,
  Catppuccin Mocha, Rosé Pine) that also recolor the background and the category colors
  everywhere, an uploaded background image, the soil line, the title and tagline, and a
  prompt builder for making a background with any image generator. Saved in the data
  folder, never in the vault.
- `site.headline`, per-language `site.tagline` and a `[landing]` section in the config;
  a category's `color` is now optional and comes from the palette.
- The graph: `/api/graph` for the whole vault, a project or a note's neighborhood;
  `/explore` with search and filters; graphs on project and note pages, drawn with a
  vendored Cytoscape.js; browser strings served as `/static/locales/<lang>.json`.
- Reading pages: projects by category, each project with its notes and conversations,
  notes with backlinks and the projects they belong to, the journal and a health page.
- Markdown rendered like Obsidian (wikilinks, ghost links, callouts, task lists, tables,
  footnotes) and sanitized with nh3.
- Spanish interface, including the names of the default categories; own categories take
  `label = "Art"` or `label = { en = "Art", es = "Arte" }`; dates per language and in the configured time zone; light and dark
  themes that follow the system.
- Sign-in for one person: argon2 password and TOTP code, server-side sessions in SQLite,
  lockout after repeated failures, `auth.mode = "none"` for gateways, and
  `mycelium user` commands to create the secrets.
- Security headers (CSP without inline code, no framing) on every response.
- Interface strings in `locales/en.toml`.

- Project skeleton: packaging with `uv`, lint, types, tests and CI on Linux, macOS and Windows.
- `mycelium.toml` loading and validation, with categories, colors and mushroom species.
- Vault reader: frontmatter, titles and Obsidian-style wikilinks (aliases, headings, paths).
- In-memory index with backlinks, project membership, bridges, ghost links and orphans,
  refreshed from file modification times.
- `mycelium check` lists problems in a vault; `mycelium serve` runs the site.
- `/healthz` for containers and monitoring.
- A sample vault in `examples/vault`.
- Self-hosting guides for Mycelium plus a notes MCP server, on your own computer or a server.
