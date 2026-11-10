# Vendored libraries

Served from `/static/vendor`, never from a CDN, so the Content Security Policy can stay
`default-src 'self'`. Each library keeps its license next to it.

| Library | Version | File | Source |
| --- | --- | --- | --- |
| [Cytoscape.js](https://js.cytoscape.org/) (MIT) | 3.34.4 | `cytoscape/cytoscape.esm.min.js` | `dist/cytoscape.esm.min.mjs` from the npm tarball `cytoscape-3.34.4.tgz` |
| [d3-force](https://d3js.org/d3-force) (ISC) with d3-dispatch 3.0.1, d3-quadtree 3.0.1 and d3-timer 3.0.1 | 3.0.0 | `d3-force/d3-force.bundle.min.js` | the four `dist/*.min.js` files, concatenated in that order (dispatch, quadtree, timer, force) |
| [Shrikhand](https://fonts.google.com/specimen/Shrikhand) by Jonny Pinhorn (SIL OFL 1.1) | v17 | `fonts/shrikhand/shrikhand-latin.woff2` | the Latin subset served by Google Fonts |

The npm tarball was checked against the registry's integrity hash
`sha512-msY99tMY8iWTg+sIPGfSqDcPNOt4xcj+v/K/7qUFaCUxxlqnMkUYLBjRUzn9W5CU/R2hrmtJa5+UtovrEM2ctg==`.
The file is renamed from `.mjs` to `.js` so every server sends it as JavaScript.

To update: download the new tarball from `https://registry.npmjs.org/cytoscape/-/cytoscape-<version>.tgz`,
check its `dist.integrity`, copy the same file and `LICENSE`, and update this table and
`tests/test_graph_page.py`, which pins the version.

The d3 tarballs were checked against the registry's integrity hashes:

- `d3-force-3.0.0.tgz`: `sha512-zxV/SsA+U4yte8051P4ECydjD/S+qeYtnaIyAs9tgHCqfguma/aAQDjo85A9Z6EKhBirHRJHXIgJUlffT4wdLg==`
- `d3-dispatch-3.0.1.tgz`: `sha512-rzUyPU/S7rwUflMyLc1ETDeBj0NRuHKKAcvukozwhshr6g6c5d8zh4c2gQjY2bZ0dXeGLWc1PF174P2tVvKhfg==`
- `d3-quadtree-3.0.1.tgz`: `sha512-04xDrxQTDTCFwP5H6hRhsRcb9xxv2RzkcsygFzmkSIOJy3PeRJP7sNk3VRIbKXcog561P9oU0/rVH6vDROAgUw==`
- `d3-timer-3.0.1.tgz`: `sha512-ndfJ/JxxMd3nw31uyKoY2naivF+r29V+Lc0svZxe1JvvIRmi8hUsrMvdOwgS1o6uBHmiz91geQ0ylPP0aj1VUA==`

All four share the same ISC license text, kept once as `d3-force/LICENSE`. The font's
license is `fonts/shrikhand/OFL.txt`. `tests/test_landing.py` pins these versions.

The landing's included background, `../img/psychedelic-dusk.webp`, was painted for this
project with an image generator from the prompt in `docs/reports/step-5.md` and is
released under the project's MIT license.

