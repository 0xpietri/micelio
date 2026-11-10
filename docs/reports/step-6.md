# Step 6 report: public notes

Date: 2026-11-10

## Done

- **Anonymous visitors can read** `/`, `/api/landing`, `/explore`, `/api/graph`,
  `/projects`, `/projects/<slug>`, `/notes/<slug>` and `/journal` (GET and HEAD only), all
  built from notes with `public: true`. The uploaded landing background is open too, since
  the landing shows it. Everything else still needs a session: `/health` and `/appearance`
  redirect to sign-in, any POST answers 401, and both pages also answer 404 by themselves if
  a visitor ever reached them.
- **`PublicView`** (`vault/public.py`): the same questions as the vault index (notes, links,
  backlinks, projects and their members, bridges), answered over the public notes only. It
  is rebuilt when the index changes. Pages, the graph builder and the landing builder take
  either the whole index or this view, chosen per request, so no page can show a private
  note by forgetting a filter: the view does not have them.
- **What that means for a visitor** (§9):
  - A public project shows only its public notes, with counts of public notes only.
  - Degrees (node size) and bridges count public links and public projects only.
  - A link from a public note to a private one renders as plain text, never as a link or a
    node. A link resolves the same way as for the owner, so when a private note wins a name
    the visitor gets text, not a different public note of the same name.
  - Links to missing notes are also plain text and there are no ghost nodes, so a missing
    note and a private one look the same.
  - A private note's URL, as a page or as a graph scope, answers 404, the same as a note
    that never existed. The 404 page offers sign-in ("If this notebook is yours…") on every
    404, so it says nothing about the note.
  - `/healthz` leaves out the number of notes unless signed in.
- **With nothing public** the landing shows the soil, one sprout, "Nothing here is public
  yet." and a sign-in button (§7a).
- **Navigation**: visitors see Explore, Projects and Journal and a "Sign in" link that
  comes back to the same page; Health, Appearance and Sign out are only for the owner.
- **Languages**: the two new strings and the sign-in links in `en` and `es`; a test checks
  the Spanish visitor pages show no English.
- **Spec**: §9 now states the 404, the `/healthz` count, the ghost rule and that only a
  note's own `public: true` makes it public.

Tests: 284 (21 new in `tests/test_public.py`), coverage 98 %. The main test crawls every
page and JSON reachable without signing in (following every link) over a vault whose
private titles, paths, slugs, tags and aliases all carry a marker, and checks no response
contains it. A second crawl over the sample vault checks no private title, path or URL
appears. Checked in Chromium as a visitor in English and Spanish: no CSP violations or
script errors.

## Decisions taken while building

- No ghosts for visitors (above). Showing them would tell which unresolved links point at
  nothing and so, by elimination, which point at a private note.
- A public note may name a private one in its own text (`[[Private idea]]`). That text is
  the author's and is shown as written; the private note's real title, path and contents
  are never shown. Use `[[Private idea|other words]]` to say it differently.
- `auth.mode = "none"` and the personal-computer case (sign-in off) show everything, as
  before: there is no visitor to hide from.

## Open points

- With very few public projects the landing places the mushrooms near the screen edges, so
  one can be partly cut off at some widths (layout from step 5).
