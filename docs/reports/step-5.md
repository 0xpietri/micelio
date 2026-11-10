# Step 5 report: the landing and the Appearance page

Date: 2026-11-10

## How it was decided

The step started with a static mockup, as §14 asks. marcos approved it with changes, all
written into the spec (§7a, the new §7b, §15):

- The title stays on **one line** (it shrinks to fit) and its **text is editable**.
- **No tree.**
- **Four palettes** that recolor the mushrooms and the background, chosen from analogous
  themes: Psychedelic (the original), Tokyo Night, Catppuccin Mocha and Rosé Pine.
- The owner can **upload their own background**, guided by a **prompt builder** that fixes
  the format and leaves the creative parts open.
- All of it on a signed-in **Appearance page** that saves to the data folder. This is the
  first time Mycelium writes anything; it never touches the vault, and principle 2 now
  names this one exception.

## Done

- **`/`**: the landing of §7a. The painted background (`static/img/psychedelic-dusk.webp`,
  1536 x 1024) with a live SVG layer drawn by `static/js/landing.js`:
  - Projects are mushrooms on the soil line, one of eight species per category, drawn
    procedurally. Status is growth: `draft` a closed button, `active` a full cap, `paused`
    faded, `closed` dried and bent. Size grows with the project's notes.
  - Notes are clouds of spores below, pulled under their projects; bridge notes sit
    between their projects with a dashed ring and a thicker thread.
  - Links are glowing hyphae with small side twigs; sources are crystals; the 5 latest
    journal notes float as golden spores near the projects they touched.
  - Threads grow on load and a pulse runs along random links; all motion stops under
    `prefers-reduced-motion`.
  - Hover or focus shows the title; click opens the page. Tab moves through the mushrooms;
    a visually hidden list names every project, note, source and journal note as links.
  - Over `landing.max_notes` (300) notes, only the most connected are drawn and the legend
    says how many more there are. An empty vault shows the soil, one button and a hint.
- **Layout**: a seeded `d3-force` (vendored 3.0.0 with dispatch, quadtree and timer), so the
  same vault always draws the same forest. The view adapts to the screen: wide screens
  crop the sky, phones crop the sides, mushrooms spread over the visible width.
- **`/api/landing`**: what the landing draws, as JSON (projects with species, color and
  status; notes with their projects; links among drawn notes; sources; journal; the
  palette; the background). The page fetches it, so the static export of v0.2 can write it
  as a file.
- **`/appearance`** (§7b), signed in:
  - Palette: four cards with swatches.
  - Background: the included painting or an uploaded image (PNG, JPEG or WebP, up to 8 MB,
    at least 1200 x 800). The type and size come from the file's own header bytes, never
    its name. One upload is kept, written atomically to `data/backgrounds/`.
  - Recolor: maps the image's brightness onto the palette's ramp with an SVG filter in the
    browser. On by default for the included painting, off for an upload.
  - Soil line (30–70 %), title and tagline.
  - Prompt builder: the fixed rules are shown as fixed (size, soil line, calm corner for the
    title, dark underground, nothing on the horizon, no mushrooms or text); the owner edits
    style, sky, horizon, underground, colors (prefilled from the palette) and mood, and
    copies the prompt. It is in the interface language.
  - Every form needs a token tied to the session (HMAC, like sign-out). With sign-in off
    the key is random per start.
- **Colors everywhere**: the palette also sets the category colors on `/theme.css`, the
  graphs and the project lists. A category's `color` in the config is now optional and,
  when set, wins over the palette.
- **Config**: `site.headline` and `site.tagline` (one text or one per language; without a
  tagline the translated default is used, so the Spanish site never shows English), and
  `[landing]` with `palette`, `soil` and `max_notes`.
- **Font**: Shrikhand (SIL OFL), Latin subset, vendored for the title.
- **Languages**: every new string in `en` and `es`; tests check that the Spanish landing and
  Appearance page show no English interface text.
- **CSP**: still no inline code or styles. Animation delays are set through the CSSOM,
  palette colors come from `/theme.css`, and SVG built in the browser takes vault text only
  through `setAttribute`, never through markup.

Tests: 263 (36 new), coverage 98 %. Checked in Chromium at 1440 x 900 and 390 x 844, in
English and Spanish, with the four palettes and an uploaded background: no console errors
and no CSP violations.

## Decisions taken while building

- SVG instead of the Canvas 2D the spec first named: every mushroom is a real link the
  keyboard reaches, with no hit testing to write. The spec now says so.
- Sources are crystals, not stones, because the painted background already has stones.
- The included background's prompt (below) is kept here so it can be painted again.
- The Appearance page writes to `data/site.sqlite3` only when something is saved; a site
  nobody customizes never creates the file.

## Open points

- Anonymous visitors: `/`, `/api/landing` and the uploaded background still need sign-in,
  like every page. Step 6 shows the landing built from public notes only.
- The title font covers Latin scripts; other scripts fall back to Cooper Black or Georgia.
- The `cose` layout of `/explore` is still unseeded (step 4); the landing is seeded.

## The included background's prompt

Painted with ChatGPT from this prompt; the Appearance page builds prompts in the same shape.

> Wide landscape illustration, 1536 x 1024 (3:2), for the background of a website. It is
> ONLY a backdrop: other artwork (mushrooms, white mycelium threads, glowing spore clouds
> and text) will be placed on top of it later in code, so leave room for them. Style:
> 1960s–70s psychedelic concert-poster art meets modern flat vector illustration, bold
> black outlines, flat fills with smooth gradients, a saturated neon palette (#FF2FA0,
> #FF8A1F, #FFD23F, #C6FF3A, #39FF6A, #22D3EE, #3B5BFF, #9B5CFF, outlines #12051F). A
> slightly wavy horizon at 48 % of the height; a liquid, swirling sky with an op-art sun of
> concentric rings at the upper right; a calmer top-left corner for the title; two layers of
> distant mountains and a thin strip of grassy hills with tiny flowers on the horizon; below,
> a dark, low-contrast stained-glass mosaic of jewel-tone cells with a few small stones. No
> mushrooms, trees, roots, threads, people, animals, text, logos or frame.
