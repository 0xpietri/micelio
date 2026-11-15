# Scenes and illustrated mushrooms

Asked by marcos on 2026-11-15: replace the site's art with images made with fal.ai, pick a
scene as a template, and give each scene its own mushrooms to choose from (species and
size, no color).

## How the art was made

- Backgrounds: Nano Banana 2.1 (edit), from marcos's three reference images and the old
  painting's layout. He picked nine; each was edited again so the underground is dark and
  empty. About USD 2.30 in total.
- Mushrooms: one 4K sheet per style (15 species on a 5 x 3 grid on flat gray, the
  reference plus that style's backgrounds as the palette), background removed with Bria
  RMBG, then split by the transparent gaps. About USD 0.45.
- Stored as WebP: scenes 1920 x 1280 (1.2 MB for the nine) plus 360 x 240 thumbnails;
  mushrooms 512 px squares with the stem's foot at the bottom middle (1.4 MB for 45).

## What was built

- `micelio.scenes`: the ten scenes (nine new plus *Psychedelic dusk*) with their soil
  line, recolor default and mushroom style. `[landing] scene` sets the default
  (`blacklight-planet`).
- `Appearance` keeps `scene` and `mushrooms` (`None` follows the scene). Picking another
  painting resets the recolor box to that scene's default and brings its soil line. A
  choice saved before scenes existed starts on the default scene with its soil line,
  because the old box and slider were about the first painting.
- Every page carries `<meta name="micelio-mushrooms">`. `draw.js`'s painter draws a
  species as its picture for an illustrated style, or as the SVG for `drawn`. The seven
  new species borrow a close silhouette when drawn. Drafts are still the small button;
  paused and closed keep their filters.
- The Appearance page shows the scenes as a gallery, plus a "Mushrooms" select. The
  mushroom editor on a project's page shows the 15 pictures and the size. Its color
  picker is gone (sources keep theirs).
- Small fix found on the way: the hyphae on the project cards had no stroke on the
  projects page (graph.css isn't loaded there), so they showed as black wedges.

## Tests

`tests/test_scenes.py`:
- every scene and thumbnail ships as WebP;
- every style has every species, the same list as `draw.js` and `config.SPECIES`;
- names in both languages;
- scene defaults, the legacy migration, and an old upload keeping its soil line;
- autosave bringing a scene's values;
- the gallery on the page, the config key, and the new species in the editor.

Three older tests now expect the new default scene.

## Not done

- The landing's "draft" button and the drawn spores and crystals are still the SVG
  ones. Crystals (sources) are the next assets to replace.
- No per-category default species per style yet: the categories keep the species set in
  `micelio.toml` and the owner changes a project's from its page.

## Second round (marcos, 2026-11-15)

- The palette colors everything: every scene is recolored by default (Psychedelic has no
  ramp, so it keeps the painting's colors), and picking another palette turns the
  recolor back on. The illustrated mushrooms use the same filter as the painting. A
  project's stored color is dropped, so its mushroom, glow and threads follow the
  category's palette color; sources keep theirs.
- Smaller mushrooms: the pictures draw at 84 units instead of 112, and the size goes
  from 30 % to 120 % (was 60 % to 160 %). Larger saved sizes are clamped.
