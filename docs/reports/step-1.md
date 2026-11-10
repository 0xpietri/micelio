# Step 1 report: skeleton

Date: 2026-11-09

## Done

- Packaging with `uv` (lockfile), `hatchling`, console script `micelio`.
- `ruff` (lint + format), `mypy --strict`, `pytest` with coverage (99 %).
- CI: lint and types on Linux; tests on Linux, macOS and Windows (Python 3.12) plus Linux on
  3.13; superseded runs cancelled. Dependabot for `uv` and Actions. No image build yet (step 7).
- `micelio.toml` loading and validation (`config.py`): unknown keys rejected, category keys,
  hex colors and mushroom species checked, duplicate categories rejected, relative vault root
  resolved against the config file, `MICELIO_CONFIG` / `MICELIO_VAULT` / `--vault`.
- Vault parser: frontmatter (broken blocks reported, never raised; YAML dates kept as strings),
  title from frontmatter → first H1 → file name, wikilinks with headings, labels and embeds,
  ignoring code blocks and inline code.
- Index: type from frontmatter or folder, slug collisions, Obsidian-style resolution (name,
  alias, path, path suffix, shortest path wins; case-insensitive, NFC/NFD-insensitive), edges,
  backlinks, ghosts, project membership, bridges, orphans. Skips hidden folders, Syncthing
  conflict copies, non-Markdown files, files over 2 MB and symlinks that leave the vault.
  Refresh is throttled to 2 s and re-parses only files whose mtime or size changed.
- `micelio check` and `micelio serve`; `/healthz` returns status, version and the note
  count only. API docs routes are disabled.
- Sample vault: 27 notes (5 projects, 18 notes, 2 journal, 2 sources) with 3 bridges, one ghost
  link, an alias, an accented file name, an orphan and a closed orphan project.
- Repo files: README, LICENSE (MIT), CHANGELOG, CONTRIBUTING, SECURITY, AGENTS.md (CLAUDE.md
  imports it), issue and PR templates, `micelio.example.toml`, `.env.example`.

## Spec changes

- §4 example: categories now carry `species` and the landing palette colors, matching §7a and
  the code.

## Open points

- The sample vault has 27 notes and two sources; §12 says "about 30" and "one source". Close
  enough; more notes can be added when the graph needs them.
- Ghost links count as issues, so `micelio check` exits 1 on the sample vault by design.
