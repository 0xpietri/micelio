# Project guide, questions and gaps

Asked by marcos on 2026-11-11: an index at the left of a project and of its notes, to
follow the topic in an order, chronological or logical (set by the model), with the
things still missing to learn shown as another kind of note with a mushroom look, so each
topic has a skeleton with its holes. Then: a kind of note for side questions asked along
the way, other colour, and checkboxes in the index to choose which kinds it lists;
structured order by default.

## What changed

- `config.py`: note types `question` and `gap` (both live in `notes/`); `[guide] headings`
  (`Guide`, `Guía`).
- `vault/sections.py`: find or drop one `##` section by heading, outside code fences.
- `guide.py`: `GuideBuilder` builds a project's guide: structured order from its `## Guide`
  section (`###` stretches), else the order of the index's links; notes linked outside the
  guide come last; by-date order from `created`; previous / next. Missing notes in the
  guide are gaps for the owner; `PublicView` has no ghosts, so visitors never see them.
- `render.py`: the guide section is not rendered again in the project body.
- `templates/_guide.html`, `project.html`, `note.html`: the guide box (a `<details>`,
  open beside the page from 1100 px, folded above it on a phone), the pager, banners on
  question and gap pages. `static/js/guide.js` switches order and kinds, kept in
  `localStorage` `micelio.guide.v1`.
- `graph.js`: a question is a drifting spore, a gap a dashed primordium.
- Gaps do not count for the project's growth card.
- Sample vault: a Guide section in "Learning Bayesian statistics", one gap and one
  question note. Spec §3.4, §6, §7 and decisions; CHANGELOG.

## Tests

`tests/test_guide.py`: sections and fences; structured and by-date orders on the sample
vault; fallback without a Guide section; the new types raise no issue; missing notes are
gaps for the owner only and a private note never reaches a visitor's guide; the project
page shows the guide beside the body and not in it, with no inline script or style; the
note page has the pager and banners; `?guide=` picks the project. Counts in older tests
went from 27 to 29 notes.

## Second round (2026-11-11)

Asked by marcos after the first deploy: a guide that also reads well in Obsidian, numbered
1, 1.1 … and renumbered when a topic is inserted; the order in a dropdown; previous / next
following the ticked kinds; conversations at the top of the guide; who wrote each note
(model or marcos); dates in a card beside the title; tags styled apart and linked to a graph.

- `guide.py` builds an outline from the `## Guide` section: list items with a link are
  notes, items without one and `###`/`####` headings are sections, indentation nests.
  Numbers come from the shape (`GuideEntry.number`), empty sections are pruned.
  `vault/sections.section_outline` gives the raw lines.
- `_guide.html`: `<select>` for the order, sections and depths, conversations folded at the
  top; one pager that `guide.js` rewrites from the visible steps.
- `formatting.author_name` / `authors`: `created_by` / `edited_by` (model ids read as
  "Claude Opus 5.5"). Note head: title plus a dates card (`.note-card`), wraps below.
- Graph nodes carry `tags`; `/explore?tag=` lights and frames the tagged notes. Tags are
  pills linking there. Legend lines for questions and gaps.
- Tests in `tests/test_guide.py`: numbering by shape, conversations, dropdown and pager
  data, author names, tag links and graph tags.
