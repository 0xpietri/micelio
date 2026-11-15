# Report: a simpler note page (Neighborhood only)

Asked by marcos on 2026-11-15, looking at `/notes/hash-esperado`.

## What changed

- **Only Neighborhood.** The note page drops "Part of" and "Linked from" and shows no
  list under the graph (a first version had one; marcos preferred the graph alone). Every
  node in the graph is a keyboard-reachable link.
- **Direction.** `/api/graph` edges carry `both` (the two notes link each other). On a
  note's Neighborhood, a `.flow` path over each thread animates sparks from the linking
  note to the linked one, and a second one runs back when `both`. Still under
  `prefers-reduced-motion`.
- **Marks.** Journal entries are a golden seed, draft notes (any non-project type with
  `status: draft`) a closed button mushroom over a ring of their category's color, in
  every graph. With an illustrated mushroom style (the scene's or the owner's choice) the
  seed, the button and the five source minerals use the pictures from the fal.ai asset kit
  (`static/img/nodes/<style>/`, `static/img/minerals/<style>/`, 160 px WebP, about 270 KB
  in total). With drawn mushrooms they are drawn in SVG. The kit's other minerals
  (obsidian, opal, malachite), note, question and gap pictures are not used yet.
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
  previous / next, with the dates card's look and the same height (58 px both), showing
  only "Add a note", on desktop and phone. It writes after the last block. The phone's held blank space still
  works between paragraphs.

## Tests

`tests/test_pages.py`: only the Neighborhood graph, no Links / Part of / Linked from, `links_headings = []`, Spanish `## Enlaces`. `tests/test_said_edit.py`: the card is
between the body and the Neighborhood for the owner and absent for visitors; the hidden
links section keeps line numbers. The anonymous crawl in `tests/test_public.py` covers the
new list. ruff, ruff format, mypy and pytest (432) pass.

`tests/test_graph.py`: `both` on edges, the node pictures for every style.

## Left open

- Pictures for plain notes, questions, gaps and the three extra minerals, once marcos
  picks from the asset kit.
