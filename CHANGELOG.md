# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Reading pages: projects by category, each project with its notes and conversations,
  notes with backlinks and the projects they belong to, the journal and a health page.
- Markdown rendered like Obsidian (wikilinks, ghost links, callouts, task lists, tables,
  footnotes) and sanitized with nh3.
- Spanish interface; dates per language and in the configured time zone; light and dark
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
