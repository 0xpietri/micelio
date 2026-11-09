// Mycelium graphs: draws /api/graph with the vendored Cytoscape.js.
// Plain ES module, no build step. Strings come from /static/locales/<lang>.json.

import cytoscape from "../vendor/cytoscape/cytoscape.esm.min.js";

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let stringsPromise = null;

/** The browser strings of the page's language (English fallback is merged on the server). */
export function loadStrings() {
  if (!stringsPromise) {
    const lang = document.documentElement.lang || "en";
    stringsPromise = fetch(`/static/locales/${encodeURIComponent(lang)}.json`)
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({}));
  }
  return stringsPromise;
}

/** Look up a string and fill its {placeholders}. */
export function tr(strings, key, values = {}) {
  const text = strings[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (all, name) => (name in values ? String(values[name]) : all));
}

/** Lowercase without accents, so "cafe" finds "Café". */
export function fold(text) {
  return text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

function themeColors() {
  const css = getComputedStyle(document.documentElement);
  const get = (name) => css.getPropertyValue(name).trim();
  return {
    bg: get("--bg"),
    text: get("--text"),
    muted: get("--muted"),
    line: get("--graph-edge") || get("--line"),
    ghost: get("--ghost"),
    neutral: get("--graph-neutral") || get("--surface-2"),
    accent: get("--accent"),
  };
}

function nodeSize(node) {
  const grow = Math.sqrt(node.degree || 0);
  if (node.type === "project") return 30 + 6 * grow;
  if (node.type === "ghost") return 12;
  return 12 + 3.5 * grow;
}

function elementsFrom(data, colors) {
  const palette = Object.fromEntries(data.categories.map((c) => [c.key, c.color]));
  const nodes = data.nodes.map((n) => ({
    group: "nodes",
    data: {
      ...n,
      size: nodeSize(n),
      color: n.category ? palette[n.category] : colors.neutral,
    },
  }));
  const edges = data.edges.map((e) => ({ group: "edges", data: { ...e } }));
  return [...nodes, ...edges];
}

function styleFor(colors) {
  return [
    {
      selector: "node",
      style: {
        "background-color": "data(color)",
        width: "data(size)",
        height: "data(size)",
        shape: "ellipse",
        // A ring in the text color keeps every fill visible on both themes (WCAG 1.4.11).
        "border-width": 1.5,
        "border-color": colors.text,
        label: "data(title)",
        color: colors.text,
        "font-size": 10,
        "text-valign": "bottom",
        "text-margin-y": 4,
        "text-wrap": "ellipsis",
        "text-max-width": 140,
        "text-outline-color": colors.bg,
        "text-outline-width": 2,
        "min-zoomed-font-size": 9,
      },
    },
    {
      selector: 'node[type = "project"]',
      style: { "font-size": 13, "font-weight": 700, "border-width": 2.5, "min-zoomed-font-size": 6 },
    },
    { selector: 'node[type = "journal"]', style: { shape: "rectangle" } },
    { selector: 'node[type = "source"]', style: { shape: "triangle" } },
    {
      selector: "node[?bridge]",
      style: { "border-style": "double", "border-width": 6, "background-color": colors.neutral },
    },
    {
      selector: "node[?ghost]",
      style: {
        "background-opacity": 0,
        "border-style": "dashed",
        "border-color": colors.ghost,
        color: colors.ghost,
      },
    },
    { selector: "node[?focus]", style: { "border-color": colors.accent, "border-width": 4 } },
    {
      selector: "edge",
      style: { width: 1.2, "line-color": colors.line, "curve-style": "straight", opacity: 0.9 },
    },
    { selector: 'edge[target ^= "ghost:"]', style: { "line-style": "dashed" } },
    { selector: "node[?faded], edge[?faded]", style: { opacity: 0.35 } },
    { selector: ".dim", style: { opacity: 0.12 } },
    { selector: "node.match", style: { "border-color": colors.accent, "border-width": 4, "z-index": 10 } },
    { selector: "node.hover", style: { "border-color": colors.accent } },
    { selector: ".hidden", style: { display: "none" } },
  ];
}

/** Rings around the focus for a project or note graph: the focus, its notes, the rest. */
function ring(node) {
  const d = node.data();
  if (d.focus) return 3;
  return d.faded || d.ghost ? 1 : 2;
}

/** Lay out what is visible. Gentle animation unless the visitor asked for less motion. */
export function relayout(cy, { first = false } = {}) {
  const visible = cy.elements().not(".hidden");
  if (!visible.length) return;
  const animate = !first && !reducedMotion() && cy.nodes().length < 400;
  const focused = cy.nodes("[?focus]").length > 0;
  const options = focused
    ? {
        name: "concentric",
        concentric: ring,
        levelWidth: () => 1,
        minNodeSpacing: 40,
        startAngle: (3 / 2) * Math.PI,
      }
    : {
        name: "cose",
        nodeRepulsion: () => 20000,
        nodeOverlap: 20,
        idealEdgeLength: () => 90,
        randomize: first,
      };
  visible.layout({ ...options, animate, animationDuration: 500, fit: true, padding: 30 }).run();
}

function showTip(tip, node, strings) {
  const d = node.data();
  const parts = [d.title];
  if (d.ghost) parts.push(tr(strings, "graph.ghost"));
  else {
    parts.push(tr(strings, `type.${d.type}`));
    if (d.status) parts.push(tr(strings, `status.${d.status}`));
    if (d.bridge) parts.push(tr(strings, "graph.bridge"));
  }
  tip.textContent = parts.join(" · ");
  const pos = node.renderedPosition();
  const offset = node.renderedOuterHeight() / 2 + 6;
  tip.style.transform = `translate(${Math.round(pos.x)}px, ${Math.round(pos.y - offset)}px) translate(-50%, -100%)`;
  tip.hidden = false;
}

/** Draw the graph named by ``el.dataset.graph`` into ``el``. Resolves to the Cytoscape core. */
export async function mountGraph(el) {
  const status = el.querySelector(".graph-status");
  const strings = await loadStrings();
  let data;
  try {
    const response = await fetch(el.dataset.graph, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(String(response.status));
    data = await response.json();
  } catch {
    if (status) status.textContent = tr(strings, "graph.failed");
    return null;
  }
  if (!data.nodes.length) {
    if (status) status.textContent = tr(strings, "graph.empty");
    return null;
  }

  const canvas = document.createElement("div");
  canvas.className = "graph-canvas";
  const tip = document.createElement("div");
  tip.className = "graph-tip";
  tip.hidden = true;
  tip.setAttribute("aria-hidden", "true");
  el.append(canvas, tip);
  if (status) status.textContent = tr(strings, "graph.hint");

  const colors = themeColors();
  const cy = cytoscape({
    container: canvas,
    elements: elementsFrom(data, colors),
    style: styleFor(colors),
    minZoom: 0.2,
    maxZoom: 3,
    boxSelectionEnabled: false,
    autoungrabify: false,
  });
  cy.scratch("mycelium", { data, strings });

  const hidden = new Set(data.hidden_types || []);
  cy.nodes().forEach((n) => {
    if (hidden.has(n.data("type"))) n.addClass("hidden");
  });
  relayout(cy, { first: true });

  cy.on("mouseover", "node", (event) => {
    const node = event.target;
    node.addClass("hover");
    if (node.data("href")) canvas.classList.add("pointer");
    showTip(tip, node, strings);
  });
  cy.on("mouseout", "node", (event) => {
    event.target.removeClass("hover");
    canvas.classList.remove("pointer");
    tip.hidden = true;
  });
  cy.on("pan zoom drag", () => {
    tip.hidden = true;
  });
  cy.on("tap", "node", (event) => {
    const href = event.target.data("href");
    if (href) window.location.assign(href);
  });

  // Follow a change of system theme without a reload.
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    const next = themeColors();
    cy.nodes().forEach((n) => {
      if (!n.data("category")) n.data("color", next.neutral);
    });
    cy.style(styleFor(next));
  });
  return cy;
}

/** Every ``[data-graph]`` on the page that is not handled by a page of its own. */
export function mountAll(root = document) {
  return Promise.all(
    [...root.querySelectorAll("[data-graph]:not([data-graph-manual])")].map((el) => mountGraph(el)),
  );
}
