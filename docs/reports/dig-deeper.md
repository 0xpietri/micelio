# Dig deeper: the project's underground, closed until asked

Asked by marcos on 2026-11-15: on each project the underground should start hidden, open
with a clearly visible "Dig deeper" button and an animation that loads the connections;
the graph looked overloaded with mycelium and connections and should be simpler; the
guide should drop the word "Guide", show the project's name as a link and fold from the
arrow beside it.

## What was built

- **Closed underground.** The project's scene now ends a little under the soil line, with
  only the sky, the mushroom and its neighbours on the ground. A bright "Dig deeper"
  button (`graph.dig`) sits under the mushroom. Pressing it grows the scene down, scrolls
  to the soil and uncovers the underground from the mushroom's foot: a soft circle of light
  (an SVG mask) widens over two seconds, with a glowing ring that runs only below the soil.
  A bar at the bottom offers "Back to the surface" and "Every connection". The zoom tools
  and ⚙ show only while it is open. Whether a page was dug stays for the tab
  (`sessionStorage`, `graph-settings.js` `dug` / `setDug`), so Back returns to it open.
  Reduced motion: no animation, no smooth scroll.
- **One thread per note.** `/api/graph` now marks each edge with `spine`. In a project's
  scope (`graph.mark_spine`) the spine is a tree: the project feeds its most linked notes
  (about the square root of their number, at least 3) and every other note hangs from its
  most linked neighbour already on the tree; each other project keeps one thread, to its
  most linked bridge note; ghost threads are left out. The forest lays out and draws only
  the spine. A note's other links are drawn hidden and light up while the note is pointed
  at or focused. "Every connection" (graph setting `every`, kept in the browser) draws
  them all, ghosts included. Other scopes mark every edge as spine.
- **Guide header.** The project's name heads the guide as a link to the project; the
  arrow beside it rotates and folds or opens the guide. "Guide" stays only as hidden text
  for screen readers.

On a test project of 36 densely linked notes and 3 journal entries, the page went from
208 drawn edges to 39 threads.

## Follow-up: which note links which

marcos asked (same night) for an animation showing which note links to which. Pointing at
or focusing a note in the underground lights all its threads, dims the rest, and runs
sparks along each thread from the linking note to the linked one. Mutual links run both
ways, from the API's `both` field. The sparks reuse the Neighborhood's `.flow` style
from the note-page PR (#28). Touch screens have no pointer to hover: a tap still
opens the note.

## Tests

`tests/test_graph.py`: the spine is a tree reaching every note, keeps one thread to the
other project, never a ghost, feeds 3 to 6 notes from the project; other scopes keep
every edge; the JSON shape. `tests/test_graph_settings.py`: the `every` setting and the
per-tab dug state, blocked storage included. `tests/test_guide.py`: the guide's header.
