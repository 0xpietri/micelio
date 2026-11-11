# Said bubbles written from the site

Asked by marcos on 2026-11-11: add handwritten notes to a note, shown as said bubbles with
the profile picture, and edit the ones already there. On a computer a floating "add note"
button that puts the note between the paragraphs at its height, then drag it anywhere; on
the phone, hold a blank space, a popup to write, the note lands in that gap and can be
moved between paragraphs. A voice-note button comes later and the design leaves room for it.

## The decision

This is the first time Micelio writes the vault (principle 2). Proposed in the thread and
chosen by marcos: Micelio writes directly, with a conflict check, rather than through the
notes MCP (same result, fewer moving parts: Micelio already runs as the vault's owner).

## What changed

- `src/micelio/editing.py`: `SaidEditor` inserts, edits, moves and deletes top-level
  `> [!said]` callouts. It refuses unless the file's SHA-256 is the one the page showed
  (409 `changed`), only accepts places between top-level blocks (re-parsed with
  markdown-it), only touches said callouts, sets `edited_by` and `updated` in the
  frontmatter by text (comments and order elsewhere kept), writes through a
  `.syncthing.*.tmp` file and one rename (permissions and CRLF kept), and copies the
  replaced version to `data/edits/` (last 50).
- `render.py`: with `anchors=True` (owner's renderer, editing on) each top-level block
  carries `data-l="start-end"`; the leading title and the guide section are blanked instead
  of cut (`drop_section(keep_lines=True)`), so the numbers are the file's body lines.
- `pages.py`: `GET/POST /api/notes/<slug>/said` (owner only, per-session form key), the
  `said_editing` template helper (hash, key, URL; a file newer than the index gets the hash
  `stale`, so a write asks for a reload instead of landing on wrong lines), and a forced
  index refresh on note and project pages for the owner when editing is on.
- `static/js/said-edit.js` + CSS: floating button and drop line (desktop), hold-to-add popup
  and hint (phone), composer, per-bubble tools (drag handle, Edit, Move with arrows, Delete
  in two clicks), body reloaded in place after each save. Strings in `locales/*.toml`
  `[said]`. Empty `.said-extra` slots in the button bar, popup and composer for the voice
  note.
- `[editing] enabled / author` in the config (off by default); spec §2, §4, §6, §8a, §10,
  decision log; CHANGELOG; a said bubble in the sample vault.

## Tests

`tests/test_said_edit.py` (21): every operation on the text, frontmatter, refused places
and non-said blocks, conflict refusal writes nothing, CRLF/permissions/no temp files left,
history pruning, paths outside the vault, line numbers through hidden parts, the routes
(owner insert then stale hash refused, wrong key, visitors get nothing, editing off).
Checked by hand in Chromium (desktop: button, composer, drag, edit; Pixel 7: hold, popup,
⋯ menu, move with arrows).

## To deploy

The vault mount must allow writes and `[editing] enabled = true` (factory-panel PR).

## Not done

- Voice notes (slot only).
- Callouts nested inside lists or other callouts are not editable from the site.
- A write by another program in the milliseconds between the hash check and the rename
  is not caught (the other writers share no lock with Micelio).
