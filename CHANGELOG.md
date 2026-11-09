# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Project skeleton: packaging with `uv`, lint, types, tests and CI on Linux, macOS and Windows.
- `mycelium.toml` loading and validation, with categories, colors and mushroom species.
- Vault reader: frontmatter, titles and Obsidian-style wikilinks (aliases, headings, paths).
- In-memory index with backlinks, project membership, bridges, ghost links and orphans,
  refreshed from file modification times.
- `mycelium check` lists problems in a vault; `mycelium serve` runs the site.
- `/healthz` for containers and monitoring.
- A sample vault in `examples/vault`.
- Self-hosting guides for Mycelium plus a notes MCP server, on your own computer or a server.
