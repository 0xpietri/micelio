# Vendored libraries

Served from `/static/vendor`, never from a CDN, so the Content Security Policy can stay
`default-src 'self'`. Each library keeps its license next to it.

| Library | Version | File | Source |
| --- | --- | --- | --- |
| [d3-force](https://d3js.org/d3-force) (ISC) with d3-dispatch 3.0.1, d3-quadtree 3.0.1 and d3-timer 3.0.1 | 3.0.0 | `d3-force/d3-force.bundle.min.js` | the four `dist/*.min.js` files, concatenated in that order (dispatch, quadtree, timer, force) |
| [Shrikhand](https://fonts.google.com/specimen/Shrikhand) by Jonny Pinhorn (SIL OFL 1.1) | v17 | `fonts/shrikhand/shrikhand-latin.woff2` | the Latin subset served by Google Fonts |
| [Righteous](https://fonts.google.com/specimen/Righteous) by Astigmatic (SIL OFL 1.1) | @fontsource 5.1.0 | `fonts/righteous/righteous-latin-400.woff2` | `files/righteous-latin-400-normal.woff2` from `@fontsource/righteous` |
| [Bagel Fat One](https://fonts.google.com/specimen/Bagel+Fat+One) by JAMO (SIL OFL 1.1) | @fontsource 5.1.0 | `fonts/bagel-fat-one/bagel-fat-one-latin-400.woff2` | `files/bagel-fat-one-latin-400-normal.woff2` from `@fontsource/bagel-fat-one` |
| [Fraunces](https://fonts.google.com/specimen/Fraunces) by Undercase Type (SIL OFL 1.1) | @fontsource 5.1.0 | `fonts/fraunces/fraunces-latin-900.woff2` | `files/fraunces-latin-900-normal.woff2` from `@fontsource/fraunces` |
| [Atkinson Hyperlegible](https://fonts.google.com/specimen/Atkinson+Hyperlegible) by the Braille Institute (SIL OFL 1.1) | @fontsource 5.1.0 | `fonts/atkinson-hyperlegible/atkinson-hyperlegible-latin-{400,700}.woff2` | `files/atkinson-hyperlegible-latin-{400,700}-normal.woff2` from `@fontsource/atkinson-hyperlegible` |
| [Literata](https://fonts.google.com/specimen/Literata) by TypeTogether (SIL OFL 1.1) | @fontsource 5.1.0 | `fonts/literata/literata-latin-{400,700}.woff2` | `files/literata-latin-{400,700}-normal.woff2` from `@fontsource/literata` |
| [Space Grotesk](https://fonts.google.com/specimen/Space+Grotesk) by Florian Karsten (SIL OFL 1.1) | @fontsource 5.1.0 | `fonts/space-grotesk/space-grotesk-latin-{400,700}.woff2` | `files/space-grotesk-latin-{400,700}-normal.woff2` from `@fontsource/space-grotesk` |
| [Caveat](https://fonts.google.com/specimen/Caveat) by Impallari Type (SIL OFL 1.1) | @fontsource 5.1.0 | `fonts/caveat/caveat-latin-{500,700}.woff2` | `files/caveat-latin-{500,700}-normal.woff2` from `@fontsource/caveat` (tarball integrity `sha512-k7X12XF3BKtUlqV81Vcvc5k88dFJvg11txEOFyF39kspJ9rKfuWk3h4dTxovANahvGpdYaDuK1d1ywt2tBVi6g==`) |
| [Patrick Hand](https://fonts.google.com/specimen/Patrick+Hand) by Patrick Wagesreiter (SIL OFL 1.1) | @fontsource 5.1.0 | `fonts/patrick-hand/patrick-hand-latin-400.woff2` | `files/patrick-hand-latin-400-normal.woff2` from `@fontsource/patrick-hand` (tarball integrity `sha512-jzi0MnS4LnohFQ35Q0fmPQeNQAz+n7l5uEVxrKkDoNn/oKpu9uTu70126YAILMI+L4H3+I3THHn4L5H94SBYEQ==`) |
| [Gochi Hand](https://fonts.google.com/specimen/Gochi+Hand) by Huerta Tipográfica (SIL OFL 1.1) | @fontsource 5.1.0 | `fonts/gochi-hand/gochi-hand-latin-400.woff2` | `files/gochi-hand-latin-400-normal.woff2` from `@fontsource/gochi-hand` (tarball integrity `sha512-9pR00T4Ry+8nTUfTJ3YY59a7IRA+qyU71PH9mI26B4+motIUuVVTCxuwFnGryE2q0uuBNioswPtAEryQ5JXK/w==`) |

The d3 tarballs were checked against the registry's integrity hashes:

- `d3-force-3.0.0.tgz`: `sha512-zxV/SsA+U4yte8051P4ECydjD/S+qeYtnaIyAs9tgHCqfguma/aAQDjo85A9Z6EKhBirHRJHXIgJUlffT4wdLg==`
- `d3-dispatch-3.0.1.tgz`: `sha512-rzUyPU/S7rwUflMyLc1ETDeBj0NRuHKKAcvukozwhshr6g6c5d8zh4c2gQjY2bZ0dXeGLWc1PF174P2tVvKhfg==`
- `d3-quadtree-3.0.1.tgz`: `sha512-04xDrxQTDTCFwP5H6hRhsRcb9xxv2RzkcsygFzmkSIOJy3PeRJP7sNk3VRIbKXcog561P9oU0/rVH6vDROAgUw==`
- `d3-timer-3.0.1.tgz`: `sha512-ndfJ/JxxMd3nw31uyKoY2naivF+r29V+Lc0svZxe1JvvIRmi8hUsrMvdOwgS1o6uBHmiz91geQ0ylPP0aj1VUA==`

All four share the same ISC license text, kept once as `d3-force/LICENSE`. Each font keeps
its license as `OFL.txt` in its folder. `tests/test_landing.py` pins these versions.

The graphs used Cytoscape.js until the step that drew them as mycelium; it was removed
then, and the landing's d3-force draws every graph now.

The landing's included background, `../img/psychedelic-dusk.webp`, was painted for this
project with an image generator from the prompt in `docs/reports/step-5.md` and is
released under the project's MIT license.

The takeaway chalkboard's frame, `../img/log-frame.webp` (logs, leaves and fly agarics), was
made for this project with an image generator, cut out to a transparent PNG and scaled to
768 × 512; it is a 9-slice `border-image` (slices 100 125 130 125) and is released under
the project's MIT license.

