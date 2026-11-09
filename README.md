# Mycelium

**Your Markdown notes as a living network of ideas.** Mycelium reads a folder of notes (an
Obsidian vault, or any folder of `.md` files) and shows it as projects, links and graphs on a
small self-hosted website. It is read-only: your notes stay plain files that you, your editor
or an AI assistant write.

> **Status: early development.** The first release (v0.1) is being built step by step; see
> the [roadmap](#roadmap). What works today: reading and checking a vault, and the health
> endpoint.

## Why

Notes written over months, by hand or by an assistant over [MCP](https://modelcontextprotocol.io),
pile up into a web of ideas that a file list cannot show. Mycelium makes that web visible:

- **Projects** grow above ground like mushrooms; the **notes** they link to spread below as
  mycelium, and notes shared by projects of different categories become visible **bridges**.
- **Graphs** for the whole vault, for each project and around each note.
- **Health**: broken links (shown as ghost nodes), unknown frontmatter values and orphans.
- **Sharing**: mark a note `public: true` and anonymous visitors can read it; everything else
  needs a sign-in.
- **Any assistant**: Mycelium does not care who wrote the notes. Claude, ChatGPT, a local
  model or you in Obsidian all work.

## Quick start

With [uv](https://docs.astral.sh/uv/) installed (Linux, macOS or Windows):

```sh
git clone https://github.com/0xpietri/mycelium
cd mycelium
uv sync
uv run mycelium check --vault examples/vault
uv run mycelium serve --vault examples/vault     # http://127.0.0.1:8765/healthz
```

Once v0.1 is on PyPI and GHCR this becomes `uvx mycelium serve --vault ~/Notes` on a personal
computer, or a Docker image on a server.

## How a vault is read

```
vault/
  projects/   one note per project, with a category; it links to its notes
  notes/      one idea per note
  journal/    dated entries
  sources/    books, papers, links
```

Each note may start with a frontmatter block:

```yaml
---
type: project            # project | note | journal | source (otherwise taken from the folder)
category: science        # projects only; one of the categories in mycelium.toml
status: active           # draft | active | paused | closed
tags: [gravity, astrology]
created: 2026-11-09
public: false            # true lets anonymous visitors read it
aliases: [Planets at birth]
---
```

Links use Obsidian's `[[wikilink]]` syntax, including `[[Note#Heading|label]]`, aliases and
paths. A note belongs to a project when the project links to it. Hidden folders (`.obsidian`,
`.trash`) and Syncthing conflict copies are ignored. Nothing in the frontmatter is required;
odd values are reported by `mycelium check`, never fatal.

## Configuration

Copy [`mycelium.example.toml`](mycelium.example.toml) to `mycelium.toml` and point
`--config` (or `MYCELIUM_CONFIG`) at it. It holds the site title, the owner's name, the vault
folders and the categories, each with a color and a mushroom species for the landing page.
Secrets never go in this file; see [`.env.example`](.env.example).

## Roadmap

| Step | What | State |
| --- | --- | --- |
| 1 | Skeleton: config, vault reader and index, `/healthz`, CI | done |
| 2 | Sign-in: password + TOTP, sessions, or `auth.mode = "none"` | next |
| 3 | Pages and languages: projects, notes, journal, health; English and Spanish | |
| 4 | Graphs: whole vault, per project, per note | |
| 5 | The landing: mushrooms above ground, mycelium below | |
| 6 | Public notes for anonymous visitors | |
| 7 | Release v0.1.0: Docker image (amd64 + arm64), PyPI package | |

Later: a static export to share public notes without a server (v0.2) and an Obsidian plugin
(v0.3). The full specification is in [`docs/spec`](docs/spec/MYCELIUM_SPEC_v0.1.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Marcos Pietri
