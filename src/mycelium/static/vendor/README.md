# Vendored libraries

Served from `/static/vendor`, never from a CDN, so the Content Security Policy can stay
`default-src 'self'`. Each library keeps its license next to it.

| Library | Version | File | Source |
| --- | --- | --- | --- |
| [Cytoscape.js](https://js.cytoscape.org/) (MIT) | 3.34.4 | `cytoscape/cytoscape.esm.min.js` | `dist/cytoscape.esm.min.mjs` from the npm tarball `cytoscape-3.34.4.tgz` |

The npm tarball was checked against the registry's integrity hash
`sha512-msY99tMY8iWTg+sIPGfSqDcPNOt4xcj+v/K/7qUFaCUxxlqnMkUYLBjRUzn9W5CU/R2hrmtJa5+UtovrEM2ctg==`.
The file is renamed from `.mjs` to `.js` so every server sends it as JavaScript.

To update: download the new tarball from `https://registry.npmjs.org/cytoscape/-/cytoscape-<version>.tgz`,
check its `dist.integrity`, copy the same file and `LICENSE`, and update this table and
`tests/test_graph_page.py`, which pins the version.
