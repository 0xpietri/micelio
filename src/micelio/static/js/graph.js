// Micelio graphs: draws /api/graph as mycelium, like the landing (§7, §7c). Projects are
// mushrooms, notes spore clouds, links hyphae, sources crystals, journal notes golden
// spores. SVG over a seeded d3-force layout (vendored, global `d3`), so the same vault
// always draws the same map. Plain ES module, no build step.

import {
  DEFS, SVG_NS, cloud, el, f1, fold, fragment, hyphaPath, lighter, loadStrings, mix, painter,
  paletteFromCss, rampFilter, reduced, seededRandom, tr,
} from "./draw.js";

export { fold, loadStrings, tr };

const UNCATEGORIZED_SPECIES = "glowing-bonnets";
const DRAW_ORDER = { ghost: 0, source: 1, note: 2, journal: 3, project: 4 };

/* ---------- what the page knows: palette, background, categories ---------- */

function backdropInfo() {
  const b = document.getElementById("backdrop");
  const image = b && b.querySelector("image");
  return {
    url: image ? image.getAttribute("href") : null,
    soil: Math.round((1024 * Number(b ? b.dataset.soil : 52)) / 100),
    ramp: b && b.dataset.ramp ? b.dataset.ramp.split(" ") : null,
  };
}

function look(data) {
  const pal = paletteFromCss();
  const cats = Object.fromEntries(data.categories.map((c) => [c.key, c]));
  const neutral = mix(pal.thread, pal.ink, 0.45);
  return {
    pal,
    paint: painter(pal),
    color: (key) => (key && cats[key] ? cats[key].color : neutral),
    species: (key) => (key && cats[key] ? cats[key].species : UNCATEGORIZED_SPECIES),
    defs: (ramp) => DEFS + (ramp ? rampFilter(ramp) : ""),
  };
}

/* ---------- one mark per node; a mushroom's base sits on the node's point ---------- */

function mark(node, L, k = 1) {
  const { pal, paint } = L;
  const degree = node.degree || 0;
  if (node.type === "project") {
    const s = (0.36 + 0.06 * Math.sqrt(degree)) * k;
    const glow = `<ellipse cx="0" cy="2" rx="${f1(46 * s)}" ry="${f1(12 * s)}" fill="${L.color(node.category)}" opacity=".55" filter="url(#softglow)"/>`;
    const body = paint.mushroom(L.species(node.category), L.color(node.category), node.status);
    return { r: 30 * s, top: 105 * s, markup: `${glow}<g transform="scale(${s.toFixed(3)})"><g class="grow"><g class="sway">${body}</g></g></g>` };
  }
  if (node.type === "source") {
    return { r: 14 * k, top: 18 * k, markup: `<g class="cloud" transform="scale(${(0.55 * k).toFixed(2)})">${paint.crystal(pal.crystals[0])}</g>` };
  }
  if (node.ghost) {
    return { r: 8 * k, top: 10 * k, markup: `<circle r="${7 * k}" fill="none" stroke="${pal.thread}" stroke-opacity=".55" stroke-dasharray="2 3"/><circle r="${9 * k}" fill="transparent"/>` };
  }
  if (node.type === "journal") {
    const r = 10 * k;
    return { r, top: r, markup: `<g class="cloud"><circle r="${f1(r * 1.6)}" fill="${pal.spore}" opacity=".45" filter="url(#softglow)"/>${cloud(r, node.id, lighter(pal.spore, 0.45))}<circle r="${f1(r * 1.6)}" fill="transparent"/></g>` };
  }
  const r = (6 + Math.sqrt(degree) * 3.2) * k;
  const ring = node.bridge
    ? `<circle r="${f1(r + 5)}" fill="none" stroke="${pal.sun}" stroke-opacity=".8" stroke-width="1.2" stroke-dasharray="2 4"/>`
    : "";
  return { r, top: r, markup: `<g class="cloud"><circle r="${f1(r * 1.55)}" fill="${L.color(node.category)}" opacity=".42" filter="url(#softglow)"/>${ring}${cloud(r, node.id, pal.thread)}<circle r="${f1(r * 1.6)}" fill="transparent"/></g>` };
}

/** A small picture of one kind of node, for legends. */
export function legendIcon(type, data, extra = {}) {
  const L = look(data);
  const node = { id: `legend-${type}`, type, degree: 4, category: data.categories[0]?.key, status: "active", ghost: type === "ghost", ...extra };
  const m = mark(node, L, type === "project" ? 0.75 : 0.8);
  const y = type === "project" ? 12 : 0;
  return el("svg", { viewBox: "-20 -20 40 40", "aria-hidden": "true", focusable: "false", class: "legend-icon" },
    el("defs", {}, DEFS), `<g transform="translate(0,${y})">${m.markup}</g>`);
}

function describe(node, strings) {
  if (node.ghost) return tr(strings, "graph.ghost");
  const parts = [tr(strings, `type.${node.type}`)];
  if (node.status) parts.push(tr(strings, `status.${node.status}`));
  if (node.bridge) parts.push(tr(strings, "graph.bridge"));
  return parts.join(" · ");
}

/* ---------- layout ---------- */

/** Seeded force layout in plain 2D. A focused graph keeps its focus in the middle. */
function layoutFree(data) {
  const nodes = data.nodes.map((n) => ({ ...n }));
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const links = data.edges.filter((e) => byId[e.source] && byId[e.target]).map((e) => ({ ...e }));
  const rand = seededRandom(nodes.map((n) => n.id).join("|"));
  for (const n of nodes) {
    n.x = (rand() - 0.5) * 400;
    n.y = (rand() - 0.5) * 400;
    if (n.focus) { n.fx = 0; n.fy = 0; }
  }
  const touchesProject = (l) => l.source.type === "project" || l.target.type === "project";
  const d3 = window.d3;
  const sim = d3.forceSimulation(nodes).randomSource(rand).stop()
    .force("link", d3.forceLink(links).id((d) => d.id).distance((l) => (touchesProject(l) ? 95 : 70)).strength(0.35))
    .force("charge", d3.forceManyBody().strength((d) => (d.type === "project" ? -520 : -190)))
    .force("collide", d3.forceCollide((d) => (d.type === "project" ? 44 : 24)))
    .force("x", d3.forceX(0).strength(0.04))
    .force("y", d3.forceY(0).strength(0.05));
  const ticks = Math.min(320, 80 + Math.round(40000 / Math.max(1, nodes.length)));
  for (let i = 0; i < ticks; i++) sim.tick();
  return { nodes, links };
}

function bounds(nodes, pad = 60) {
  if (!nodes.length) return { x: -100, y: -100, w: 200, h: 200 };
  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  const x0 = Math.min(...xs) - pad;
  const y0 = Math.min(...ys) - pad - 40;
  return { x: x0, y: y0, w: Math.max(...xs) + pad - x0, h: Math.max(...ys) + pad - y0 };
}

/** ``box`` grown to the element's aspect ratio, centered. */
function fitTo(svg, box) {
  const r = svg.getBoundingClientRect();
  const a = r.width / Math.max(1, r.height);
  const vb = { ...box };
  if (vb.w / vb.h < a) {
    const w = vb.h * a;
    vb.x -= (w - vb.w) / 2;
    vb.w = w;
  } else {
    const h = vb.w / a;
    vb.y -= (h - vb.h) / 2;
    vb.h = h;
  }
  return vb;
}

/* ---------- pan and zoom ---------- */

function panZoom(svg, onChange) {
  let vb = { x: 0, y: 0, w: 1, h: 1 };
  let home = vb;
  const rect = () => svg.getBoundingClientRect();
  const apply = () => {
    svg.setAttribute("viewBox", `${f1(vb.x)} ${f1(vb.y)} ${f1(vb.w)} ${f1(vb.h)}`);
    onChange(rect().width / vb.w);
  };
  const zoomAt = (cx, cy, f) => {
    const r = rect();
    const nw = Math.min(home.w * 4, Math.max(home.w / 8, vb.w * f));
    const k = nw / vb.w;
    const px = vb.x + ((cx - r.left) / r.width) * vb.w;
    const py = vb.y + ((cy - r.top) / r.height) * vb.h;
    vb = { x: px - (px - vb.x) * k, y: py - (py - vb.y) * k, w: vb.w * k, h: vb.h * k };
    apply();
  };
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    zoomAt(e.clientX, e.clientY, e.deltaY > 0 ? 1.12 : 1 / 1.12);
  }, { passive: false });
  let drag = null;
  svg.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    drag = { x: e.clientX, y: e.clientY, vb: { ...vb }, moved: false, id: e.pointerId };
  });
  svg.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx, dy) > 4) {
      drag.moved = true;
      svg.classList.add("dragging");
      svg.setPointerCapture(drag.id);
    }
    if (!drag.moved) return;
    const r = rect();
    vb = { ...vb, x: drag.vb.x - (dx / r.width) * vb.w, y: drag.vb.y - (dy / r.height) * vb.h };
    apply();
  });
  const end = () => {
    if (drag && drag.moved) svg.dataset.dragged = "1";
    drag = null;
    svg.classList.remove("dragging");
    setTimeout(() => delete svg.dataset.dragged, 0);
  };
  svg.addEventListener("pointerup", end);
  svg.addEventListener("pointercancel", end);
  // A drag that ends on a node is not a click on it.
  svg.addEventListener("click", (e) => {
    if (svg.dataset.dragged) { e.preventDefault(); e.stopPropagation(); }
  }, true);
  return {
    show(box) { home = fitTo(svg, box); vb = { ...home }; apply(); },
    zoom(f) { const r = rect(); zoomAt(r.left + r.width / 2, r.top + r.height / 2, f); },
  };
}

/* ---------- tooltips ---------- */

function tooltips(host, svg, nodesById, strings) {
  const tip = document.createElement("div");
  tip.className = "graph-tip";
  tip.hidden = true;
  tip.setAttribute("aria-hidden", "true");
  host.appendChild(tip);
  const show = (a, evt) => {
    const node = nodesById[a.dataset.id];
    if (!node) return;
    const strong = document.createElement("strong");
    strong.textContent = node.title;
    const span = document.createElement("span");
    span.textContent = describe(node, strings);
    tip.replaceChildren(strong, span);
    tip.hidden = false;
    const box = host.getBoundingClientRect();
    let x;
    let y;
    if (evt) {
      x = evt.clientX - box.left + 14;
      y = evt.clientY - box.top + 14;
    } else {
      const r = a.getBoundingClientRect();
      x = r.left - box.left + r.width / 2;
      y = r.bottom - box.top + 8;
    }
    tip.style.left = `${Math.max(8, Math.min(x, box.width - tip.offsetWidth - 8))}px`;
    tip.style.top = `${Math.max(8, Math.min(y, box.height - tip.offsetHeight - 8))}px`;
  };
  svg.addEventListener("mousemove", (e) => {
    const a = e.target.closest("a.node");
    if (a && !svg.classList.contains("dragging")) show(a, e);
    else tip.hidden = true;
  });
  svg.addEventListener("mouseleave", () => { tip.hidden = true; });
  svg.addEventListener("focusin", (e) => {
    const a = e.target.closest("a.node");
    if (a) show(a);
  });
  svg.addEventListener("focusout", () => { tip.hidden = true; });
}

/* ---------- drawing ---------- */

function nodeLink(node, strings, focusable) {
  const a = el("a", {
    class: "node",
    "data-id": node.id,
    tabindex: focusable ? null : "-1",
    "aria-label": node.ghost ? `${tr(strings, "graph.ghost")}: ${node.title}` : `${tr(strings, `type.${node.type}`)}: ${node.title}`,
  });
  if (node.href) a.setAttribute("href", node.href);
  if (node.faded) a.classList.add("faded");
  return a;
}

function label(node, x, y, cls) {
  const text = el("text", { class: `lbl ${cls}`, x: f1(x), y: f1(y), "text-anchor": "middle" });
  text.textContent = node.title.length > 34 && node.type !== "project" ? `${node.title.slice(0, 32)}…` : node.title;
  return text;
}

function pulsing(layer, pulses, state, every) {
  clearInterval(state.timer);
  if (reduced() || !pulses.length) return;
  const ghost = document.createElementNS(SVG_NS, "path");
  state.timer = setInterval(() => {
    if (document.hidden || !layer.isConnected) return;
    const pulse = pulses[Math.floor(Math.random() * pulses.length)];
    ghost.setAttribute("d", pulse.d);
    const total = ghost.getTotalLength();
    const dot = el("circle", { r: 3.2, fill: pulse.color, filter: "url(#glow)" });
    layer.appendChild(dot);
    const t0 = performance.now();
    const run = (now) => {
      const f = Math.min(1, (now - t0) / 1500);
      const pt = ghost.getPointAtLength(total * f);
      dot.setAttribute("cx", pt.x);
      dot.setAttribute("cy", pt.y);
      dot.setAttribute("opacity", Math.sin(Math.PI * f));
      if (f < 1) requestAnimationFrame(run);
      else dot.remove();
    };
    requestAnimationFrame(run);
  }, every);
}

/** The free graph (Explore and the note's neighborhood). */
function drawFree(layer, laid, L, strings, opts) {
  const visible = opts.visible || (() => true);
  const dimmed = opts.dimmed || (() => false);
  const hyphae = el("g", { filter: "url(#glow)" });
  const twigs = el("g");
  const pulses = [];
  let markup = "";
  let twigMarkup = "";
  for (const l of laid.links) {
    const a = l.source;
    const b = l.target;
    if (!visible(a) || !visible(b)) continue;
    const { d, twigs: tw } = hyphaPath(a, b, a.id + b.id, -Infinity);
    const ghost = a.ghost || b.ghost;
    const project = a.type === "project" || b.type === "project";
    const width = ghost ? 1 : a.bridge || b.bridge ? 2.4 : project ? 1.9 : 1.3;
    const cls = ["hypha", ghost ? "ghost" : "", l.faded ? "faded" : "", dimmed(a) && dimmed(b) ? "dim" : ""].join(" ").trim();
    markup += `<path class="${cls}" d="${d}" stroke-width="${width}" stroke-opacity="${project ? 0.8 : 0.6}"/>`;
    if (!ghost) {
      for (const t of tw) twigMarkup += `<path class="twig${dimmed(a) && dimmed(b) ? " dim" : ""}" d="${t}" stroke-width=".8"/>`;
      pulses.push({ d, color: a.type === "project" ? L.color(a.category) : b.type === "project" ? L.color(b.category) : L.pal.spore });
    }
  }
  hyphae.appendChild(fragment(markup));
  twigs.appendChild(fragment(twigMarkup));
  const marks = el("g");
  const labels = el("g");
  const shown = laid.nodes.filter(visible).sort((a, b) => DRAW_ORDER[a.ghost ? "ghost" : a.type] - DRAW_ORDER[b.ghost ? "ghost" : b.type]);
  for (const n of shown) {
    const m = mark(n, L);
    const focusable = opts.focusAll || n.type === "project";
    const a = nodeLink(n, strings, focusable);
    if (dimmed(n)) a.classList.add("dim");
    const ring = n.focus ? `<circle class="focus-ring" cy="${n.type === "project" ? f1(-m.top / 2) : 0}" r="${f1((n.type === "project" ? m.top * 0.62 : m.r * 1.7) + 6)}"/>` : "";
    a.appendChild(fragment(`<g transform="translate(${f1(n.x)},${f1(n.y)})">${ring}${m.markup}</g>`));
    marks.appendChild(a);
    const y = n.type === "project" ? n.y + 18 : n.y + m.r * 1.35 + 11;
    const text = label(n, n.x, y, n.type === "project" ? "project" : n.ghost ? "ghost minor" : "minor");
    if (dimmed(n)) text.classList.add("dim");
    labels.appendChild(text);
  }
  const plane = el("g", { class: "pulses" });
  layer.replaceChildren(hyphae, twigs, plane, marks, labels);
  pulsing(plane, pulses, opts.state, opts.pulseEvery || 700);
}

/** The project's own little forest: its mushroom on the soil line, its notes below, the
 * other projects its bridge notes reach standing faded at the sides. */
function drawForest(svg, data, L, strings, state) {
  const bg = backdropInfo();
  const soil = bg.soil;
  const r = svg.getBoundingClientRect();
  const a = r.width / Math.max(1, r.height);
  const h = a < 1 ? 640 : Math.min(1024, 1536 / a);
  const w = h * a;
  const vb = { x: (1536 - w) / 2, y: Math.min(1024 - h, Math.max(0, soil - h * 0.36)), w, h };
  svg.setAttribute("viewBox", `${f1(vb.x)} ${f1(vb.y)} ${f1(vb.w)} ${f1(vb.h)}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid slice");
  const k = Math.max(0.75, Math.min(1.6, vb.w / 900));
  const cx = vb.x + vb.w * (a > 1.3 ? 0.62 : 0.5);

  const focus = data.nodes.find((n) => n.focus);
  const others = data.nodes.filter((n) => n.type === "project" && !n.focus);
  const below = data.nodes.filter((n) => n.type !== "project");
  const nodes = [];
  if (focus) nodes.push({ ...focus, fx: cx, fy: soil + 6 });
  others.forEach((o, i) => nodes.push({ ...o, fx: cx + (i % 2 ? 1 : -1) * vb.w * (0.28 + 0.06 * Math.floor(i / 2)), fy: soil + 6 }));
  const rand = seededRandom(focus ? focus.id : "forest");
  below.forEach((n) => nodes.push({ ...n, x: cx + (rand() - 0.5) * 300, y: soil + 120 + rand() * 120 }));
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const links = data.edges.filter((e) => byId[e.source] && byId[e.target]).map((e) => ({ ...e }));
  const d3 = window.d3;
  const sim = d3.forceSimulation(nodes).randomSource(seededRandom(`${focus ? focus.id : ""}f`)).stop()
    .force("link", d3.forceLink(links).id((d) => d.id).distance(130 * k).strength(0.3))
    .force("charge", d3.forceManyBody().strength(-160))
    .force("collide", d3.forceCollide(30 * k))
    .force("y", d3.forceY(soil + (a < 1 ? 230 : 170) * k).strength(0.06));
  for (let i = 0; i < 260; i++) {
    sim.tick();
    for (const n of nodes) {
      if (n.fx != null) continue;
      n.y = Math.max(soil + 70, Math.min(vb.y + vb.h - 40, n.y));
      n.x = Math.max(vb.x + 40, Math.min(vb.x + vb.w - 40, n.x));
    }
  }

  let markup = "";
  let twigMarkup = "";
  const pulses = [];
  for (const l of links) {
    const s = l.source;
    const t = l.target;
    const from = s.type === "project" ? { x: s.x, y: soil + 6 } : s;
    const to = t.type === "project" ? { x: t.x, y: soil + 6 } : t;
    const { d, twigs } = hyphaPath(from, to, s.id + t.id, soil + 8);
    const ghost = s.ghost || t.ghost;
    markup += `<path class="hypha${ghost ? " ghost" : ""}${l.faded ? " faded" : ""}" d="${d}" stroke-width="${s.bridge || t.bridge ? 3 : 1.8}"/>`;
    if (!ghost) {
      for (const x of twigs) twigMarkup += `<path class="twig" d="${x}" stroke-width="1"/>`;
      pulses.push({ d, color: s.type === "project" ? L.color(s.category) : L.pal.spore });
    }
  }
  const marks = el("g");
  const labels = el("g");
  for (const n of nodes) {
    const link = nodeLink(n, strings, true);
    if (n.type === "project") {
      const s = (n.focus ? 1 : 0.62) * k;
      const body = L.paint.mushroom(L.species(n.category), L.color(n.category), n.status);
      link.appendChild(fragment(`<g transform="translate(${f1(n.x)},${soil + 4}) scale(${s.toFixed(2)})"><g class="grow"><g class="sway">${body}</g></g></g>`));
      if (!n.focus) labels.appendChild(label(n, n.x, soil + 30, "project-small"));
    } else {
      const m = mark(n, L, k);
      link.appendChild(fragment(`<g transform="translate(${f1(n.x)},${f1(n.y)})">${m.markup}</g>`));
      labels.appendChild(label(n, n.x, n.y + m.r * 1.4 + 12, n.ghost ? "ghost minor" : "minor"));
    }
    marks.appendChild(link);
  }
  const image = el("image", {
    href: bg.url, x: 0, y: 0, width: 1536, height: 1024, preserveAspectRatio: "xMidYMid slice",
    filter: bg.ramp ? "url(#bgmap)" : null,
  });
  const plane = el("g", { class: "pulses" });
  const hyphae = el("g", { filter: "url(#glow)" });
  hyphae.appendChild(fragment(markup));
  const twigLayer = el("g");
  twigLayer.appendChild(fragment(twigMarkup));
  svg.replaceChildren(el("defs", {}, L.defs(bg.ramp)), image, hyphae, twigLayer, plane, marks, labels);
  // On a narrow screen the notes' names would overlap: the tooltip and the list below say them.
  svg.classList.toggle("far", vb.w < 700);
  pulsing(plane, pulses, state, 1000);
}

/* ---------- mounting ---------- */

/** The most connected nodes, at most ``max``: projects first, ghosts last. */
function trim(data, max) {
  if (!max || data.nodes.length <= max) return { data, hidden: 0 };
  const rank = (n) => (n.type === "project" ? 2 : n.ghost ? 0 : 1);
  const kept = [...data.nodes].sort((a, b) => rank(b) - rank(a) || b.degree - a.degree || a.id.localeCompare(b.id)).slice(0, max);
  const ids = new Set(kept.map((n) => n.id));
  const hidden = data.nodes.filter((n) => !ids.has(n.id) && !n.ghost).length;
  return { data: { ...data, nodes: kept, edges: data.edges.filter((e) => ids.has(e.source) && ids.has(e.target)) }, hidden };
}

/** Draw the graph named by ``el.dataset.graph`` into ``el``. ``data-mode`` is ``free``
 * (pan and zoom, the default), ``box`` (a fixed picture over the underground) or
 * ``forest`` (a project's scene on the soil line). Resolves to a small controller. */
export async function mountGraph(host) {
  const status = host.querySelector(".graph-status");
  const strings = await loadStrings();
  if (!window.d3) return null;
  let data;
  try {
    const response = await fetch(host.dataset.graph, { headers: { Accept: "application/json" } });
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
  const mode = host.dataset.mode || "free";
  const trimmed = trim(data, Number(host.dataset.max || 0));
  data = trimmed.data;
  const L = look(data);
  const state = { timer: null };
  const svg = el("svg", { class: "graph-svg", role: "group", "aria-label": host.getAttribute("aria-label") || "" });
  host.removeAttribute("role");
  host.prepend(svg);
  const nodesById = Object.fromEntries(data.nodes.map((n) => [n.id, n]));
  tooltips(host, svg, nodesById, strings);

  if (mode === "forest") {
    if (status) status.textContent = tr(strings, "graph.hint_box");
    const draw = () => drawForest(svg, data, L, strings, state);
    draw();
    let timer = null;
    window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(draw, 150); });
    return { data, strings, svg };
  }

  const laid = layoutFree(data);
  const bg = backdropInfo();
  svg.appendChild(el("defs", {}, L.defs(mode === "box" ? bg.ramp : null)));
  const ground = el("g", { class: "ground-image" });
  svg.appendChild(ground);
  const layer = el("g", { class: "layer" });
  svg.appendChild(layer);

  let visible = () => true;
  let dimmed = () => false;
  const draw = () => drawFree(layer, laid, L, strings, { visible, dimmed, state, focusAll: mode === "box", pulseEvery: mode === "box" ? 1100 : 700 });
  draw();

  if (status) {
    let hint = tr(strings, mode === "box" ? "graph.hint_box" : "graph.hint");
    if (trimmed.hidden) hint = `${trimmed.hidden === 1 ? tr(strings, "landing.more_one") : tr(strings, "landing.more", { count: trimmed.hidden })} ${hint}`;
    status.textContent = hint;
  }

  if (mode === "box") {
    // A fixed picture: the underground of the painting stretched over the graph's box.
    const place = () => {
      const vb = fitTo(svg, bounds(laid.nodes, 70));
      svg.setAttribute("viewBox", `${f1(vb.x)} ${f1(vb.y)} ${f1(vb.w)} ${f1(vb.h)}`);
      if (!bg.url) return;
      ground.replaceChildren(el("svg", {
        x: f1(vb.x), y: f1(vb.y), width: f1(vb.w), height: f1(vb.h),
        viewBox: `0 ${bg.soil + 30} 1536 ${1024 - bg.soil - 30}`, preserveAspectRatio: "xMidYMid slice",
      }, el("image", { href: bg.url, x: 0, y: 0, width: 1536, height: 1024, preserveAspectRatio: "xMidYMid slice", filter: bg.ramp ? "url(#bgmap)" : null })),
      el("rect", { class: "ground-shade", x: f1(vb.x), y: f1(vb.y), width: f1(vb.w), height: f1(vb.h) }));
    };
    place();
    let timer = null;
    window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(place, 150); });
    return { data, strings, svg };
  }

  svg.classList.add("pannable");
  const view = panZoom(svg, (scale) => svg.classList.toggle("far", scale < 0.75));
  const all = () => laid.nodes.filter((n) => visible(n));
  view.show(bounds(all()));
  let timer = null;
  window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(() => view.show(bounds(all())), 150); });
  return {
    data,
    strings,
    svg,
    nodes: laid.nodes,
    /** Show only nodes for which ``fn`` is true; fit them. */
    filter(fn) { visible = fn; draw(); view.show(bounds(all())); },
    /** Dim everything except nodes for which ``fn`` is true (or nothing, with null). */
    highlight(fn) { dimmed = fn ? (n) => !fn(n) : () => false; draw(); },
    fit(nodes) { view.show(bounds(nodes && nodes.length ? nodes : all(), nodes && nodes.length ? 140 : 60)); },
    zoom: (f) => view.zoom(f),
  };
}

/** Every ``[data-graph]`` on the page that is not handled by a page of its own. */
export function mountAll(root = document) {
  return Promise.all(
    [...root.querySelectorAll("[data-graph]:not([data-graph-manual])")].map((host) => mountGraph(host)),
  );
}
