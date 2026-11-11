# What's new in the footer

Asked by marcos on 2026-11-11: when he deploys with `miceliodeploy edge`, the app should
list the changes of the new version at the bottom.

## What was built

- `micelio.changes` reads `CHANGELOG.md`, splits it by `## [version]`, renders each section
  with markdown-it and cleans it with nh3. The newest section with content is "what this
  build brought": main's Unreleased changes when there are some, else the newest release.
- A footer on every page but the landing: `Micelio 0.1.1 · abc1234 · What's new`. A click
  unfolds the newest changes and a link to `/changes`, which lists them all. Visitors see
  it too: the changelog holds nothing from the vault.
- The changelog ships inside the wheel (hatch `force-include`) and the image; the image
  sets `MICELIO_REVISION` from the commit it was built from. The smoke test checks that
  `/changes` shows that commit.
- AGENTS.md now asks every user-visible change to add its line under Unreleased.

## Tests

`tests/test_changes.py`: parsing and sanitizing, which section is the latest, the build
value, the packaging, the footer on the pages (not the landing), visitors reading `/changes`.

## Follow-up the same night

marcos saw the header broken and the graph settings doing nothing after deploying. Cause:
every file in the wheel and the image has the same 2020 date, so browsers cached the old
`micelio.css` and `graph.js` by heuristic and used them with the new pages. `/static` is
now served by `FreshStaticFiles`: `Cache-Control: no-cache` and an ETag from the content.

He also asked for the ⚙ only on graphs, in the graph's top right corner
(`static/js/graph-panel.js`), "Appearance" back as text in the header, and a larger name.
