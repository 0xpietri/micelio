# Share a project from its page

Asked by marcos on 2026-11-11: a small Share button on each project, checked when the
project is shared and private when not; a shared project can be read on the site by
anyone, without signing in.

## What changed

- `src/micelio/sharing.py`: `SharedProjects`, the slugs of shared projects in
  `data/site.sqlite3` (key `shared_projects`), next to the Appearance choices and the
  node looks.
- `PublicView` (§9) now also lets in each shared project and the notes it links to
  (`members`). It rebuilds when the vault or the shared set changes. Everything else in
  the public view is untouched: links to private notes stay text, no ghosts, private
  URLs 404.
- `POST /projects/<slug>/share`: signed-in only (visitors get 401 from the sign-in
  middleware, and 404 if it is off), a per-session form token, projects only. Plain
  HTML form, no JavaScript.
- The switch is a dark card on the soil line at the right of the project's scene,
  mirroring the growth card (same glass, same colors; on a phone both share one row in `.scene-cards`): a mushroom over its mycelium ("Spores in the air") when
  shared, only the mycelium under the soil ("Underground") when private. Its colors come
  from the theme (category color, the palette's spore and second button colors). Only the
  owner can click it and gets a hint on hover; visitors see the mushroom and its sign only. A project with
  `public: true` in its frontmatter shows the mushroom without a button (it is changed in
  the vault). The projects list shows a badge to the owner.
- Spec §9 and the decision log updated; CHANGELOG line under Unreleased.

## Why the data folder and not the frontmatter

Writing `public: true` into the notes would keep the vault as the only source of truth
and travel with the notes (Obsidian, a future static export), but it breaks principle 2:
the vault is mounted read-only and Micelio never writes it. A setting in the data folder
keeps the vault untouched and switches off instantly; the cost is that the choice lives
with this site, so `micelio export --public` (v0.2) must read it too.

## Tests

`tests/test_sharing.py`: the store; sharing opens the project and its notes (page, note,
graph) while a crawl of every anonymous page still finds no other private name;
unsharing hides them again; a frontmatter-public project shows as shared without a
button; anonymous, forged-token and non-project posts are refused.
