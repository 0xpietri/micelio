# Step 3 report: pages and languages

Date: 2026-11-09

## Done

- **Pages** (`pages.py`, `templates/`):
  - `/projects`: projects grouped by category in config order, then "No category"; each row
    shows status, number of notes and the date of the last conversation (newest journal note
    linking to the project or one of its notes). Sorted active, draft, paused, closed.
  - `/projects/<slug>`: the project note rendered, its notes with status, type, bridge mark and
    a one-line excerpt, and its conversations.
  - `/notes/<slug>`: the note, tags, dates, the projects it belongs to (with category dot),
    backlinks, bridge mark. Project URLs and note URLs redirect to each other (308).
  - `/journal`: newest first, with date and excerpt.
  - `/health`: counts per type, every issue with a readable label, orphans.
  - A 404 page; other HTTP errors keep FastAPI's responses.
- **Markdown** (`render.py`): markdown-it-py (CommonMark, tables, strikethrough, task lists,
  footnotes) plus two rules of our own: wikilinks (resolved through the index; ghost text when
  missing; attachments shown by name) and Obsidian callouts. The first `# Title` is dropped
  because the page shows the title. Everything goes through nh3 with an allow-list; links get
  `rel="noopener noreferrer nofollow"`. Rendered HTML is cached until the vault changes.
- **Dates** (`formatting.py`): Babel, per language, in `site.timezone`. A note's date is its
  `created`, else a date at the start of its file name, else its modification time.
  `site.language` and `site.timezone` are validated at start-up; Windows gets `tzdata`.
- **Languages**: `en` and `es` locale files with identical keys (enforced by a test).
  CONTRIBUTING explains how to add one. The default categories are named by the locale
  (`category.<key>`); a category's `label` in `mycelium.toml` is now optional and can be one
  name or a table per language.
- **Themes**: dark and light, following `prefers-color-scheme`. Category colors come from a
  generated `/theme.css`, so no page has inline styles (tested).
- **Index**: attachment embeds (`![[photo.png]]`) are no longer reported as broken links; a
  `generation` counter lets caches know when the vault changed.

Tests: 182, coverage 99 %. Every page checked in a browser in both themes.

## Spec changes

- §5: category `label` is optional and can be given per language.
- §6: project/note URL redirects, ghost and attachment rendering, `/theme.css`, themes.

## Open points

- The project and note graphs (§6) arrive with step 4, as planned.
- A missing note whose name ends like a file extension (`[[Version 1.5]]`) is treated as an
  attachment, so it is not listed as a broken link. Rare; documented in a test.
- Images inside the vault are not served yet; `![[x.png]]` shows the file name.
