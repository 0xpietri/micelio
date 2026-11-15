# Report: a simpler note page (Neighborhood only)

Asked by marcos on 2026-11-15, looking at `/notes/hash-esperado`.

## What changed

- **Only Neighborhood.** The note page drops "Part of" and "Linked from". Under the
  Neighborhood graph, one list holds the same notes (`pages.neighbors`: outlinks, backlinks
  and projects): projects first, then notes, questions, gaps, sources and the journal.
  Each row has the mark it has in the graph, sized to the text and on the same line:
  the project's mushroom about as tall as the capital letters, dots for notes, the golden
  dot for journal entries, the crystal for sources. The type is in a tooltip and in
  hidden text for screen readers.
- **The note's own links section.** `## Links` / `## Enlaces` is left out of the rendered
  body for every note except projects (`[note] links_headings`, default
  `["Links", "Enlaces"]`; `[]` shows it again). With editing on, its lines are blanked,
  not cut, so said bubbles keep their line numbers; a bubble added at the end goes
  before that section in the file. The vault is not changed. Ghost links that only
  appeared in that section now show only in the graph.
- **Missing names in the graph.** "Defensa en capas" was in the graph data, but
  `declutter` hid its name because it overlapped another one. Now a name that would
  overlap tries one line lower, one line above and two lines lower before it hides.
  This applies to every graph.
- **"Add a note"** is no longer a floating button. It is a card where the note ends, above
  previous / next, with the dates card's look and the same height (58 px both), on
  desktop and phone. It writes after the last block. The phone's held blank space still
  works between paragraphs.

## Tests

`tests/test_pages.py`: Neighborhood list order and marks, no Links / Part of / Linked
from, `links_headings = []`, Spanish `## Enlaces`. `tests/test_said_edit.py`: the card is
between the body and the Neighborhood for the owner and absent for visitors; the hidden
links section keeps line numbers. The anonymous crawl in `tests/test_public.py` covers the
new list. ruff, ruff format, mypy and pytest (432) pass.

## Left open

- "Esa pelotita del nodo podríamos cambiarla para linkear por ejemplo un journal": not
  done yet. It still needs a decision on what that dot should do (see the PR).
