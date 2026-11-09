# Self-hosting guides

Mycelium shows your notes. To **write** notes by talking to an assistant (Claude, ChatGPT or
any app that supports remote MCP connectors, including from a phone in voice mode), you also
run a notes MCP server next to it. These guides set up both, with
[maxkuminov/obsidian-mcp](https://github.com/maxkuminov/obsidian-mcp) as the MCP server.

| Guide | For | Always on? | Cost |
| --- | --- | --- | --- |
| [Your own computer](self-hosting-computer.md) | Trying it out, or a desktop that stays on | Only while the computer is on and awake | Free |
| [A server](self-hosting-server.md) | Daily use from a phone, notes reachable any time | Yes | A small VPS, about 4–6 € / month |

Both guides are for technical users: you should be comfortable with a terminal, Docker and
editing configuration files. Nobody hosts notes for you: each person runs their own stack and
owns their data.

## How the pieces fit

```
 phone / desktop app ──HTTPS──▶ notes MCP (writes .md) ──▶ vault folder ◀── Obsidian
 (Claude, ChatGPT…)              + PostgreSQL (search)           │
                                                                 └──▶ Mycelium (reads, shows)
```

- **The vault** is a plain folder of Markdown files. It is the only source of truth.
- **The MCP server** lets an assistant search, read and write notes. It needs PostgreSQL with
  `pgvector`, and an embedding model for search by meaning (keyword search works without it).
- **Mycelium** reads the same folder and shows projects, links and graphs. It never writes.
- **Obsidian** is optional: any editor works on the folder.

## Before you start

- The MCP server only runs on **Linux** (kernel 5.6 or newer) and needs a Linux filesystem
  for the vault, because it relies on kernel features to keep every write inside the vault.
  On macOS and Windows it runs inside Docker's Linux VM, and the vault is kept in sync with
  your Obsidian folder by Syncthing. The computer guide explains this.
- Put a `CLAUDE.md` at the root of the vault describing your folders and frontmatter. The MCP
  server hands it to every assistant through its `get_vault_guide` tool, so they all follow
  the same rules. Mycelium's expected layout is described in the main
  [README](../../README.md#how-a-vault-is-read).
- Mycelium's own Docker image and PyPI package ship with v0.1.0. Until then, run it from
  source as the main README shows.
