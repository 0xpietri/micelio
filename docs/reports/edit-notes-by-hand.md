# Edit notes by hand from the site (2026-11-15)

marcos asked to edit whole notes from the site and delete parts such as "What you should
know" or his said bubbles. He chose (decision card) **by blocks + the whole note**, with
the frontmatter left as it is and an Undo.

## What changed

- `editing.py`: `SaidEditor` is now `NoteEditor`. New ops: `block` (new Markdown for any
  top-level block; empty deletes it), `drop`, `section` (a heading and everything under it,
  up to the next heading as high), `body` (the whole body; frontmatter kept, only
  `edited_by` / `updated` set; a note without frontmatter never gets one) and `undo`.
  Block lines come from the renderer's own parser rules (footnotes, task lists, HTML).
- History is per note now: `data/edits/<note>/<stamp>.md` plus `.after` (the hash of the
  file that change wrote), the last 20 of each note. Undo restores the latest and walks
  back, but only while the note is still the file the site wrote: if the MCP, Obsidian or
  Syncthing wrote it since, it is refused (`not-last`) and the button is hidden.
- `GET /api/notes/<slug>/source[?start=N]`: the body or one block as written, owner only.
- Page (`said-edit.js`): tools over the block under the pointer (Edit, Delete, Delete
  section on headings; deleting asks twice and marks what goes). Under the text: "Edit
  note" (the whole body as Markdown, draft kept in localStorage until saved), "Undo", and
  on a phone "Edit parts" (then tap a block).
- Spec §2 and §8a, CHANGELOG, en/es strings.

## Tests

`tests/test_note_edit.py` (blocks, sections, body, frontmatter, undo, undo refused after
another writer) and new website tests in `tests/test_said_edit.py` (source route, body
save + undo, section delete, visitors and editing-off get 404). 445 passed; ruff, format
and mypy clean. Tried in Chromium on desktop and a Pixel 7 profile.

## Not done

- factory-panel needs no change (vault already writable, `[editing]` already on).
- The vault guide still asks Claude to end notes with a takeaway; if marcos deletes one
  and wants it to stay gone, the guide should say so.
