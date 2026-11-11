// Micelio graphs: draws /api/graph as mycelium, like the landing (§7, §7c). Projects are
// mushrooms, notes spore clouds, links hyphae, sources crystals, journal notes golden
// spores. SVG over a seeded d3-force layout (vendored, global `d3`), so the same vault
// always draws the same map. Plain ES module, no build step.

import {
  DEFS, MINERALS, SVG_NS, cloud, el, f1, fold, fragment, hyphaPath, lighter, loadStrings, mix, painter,
  paletteFromCss, rampFilter, reduced, seededRandom, shade, tr,
} from "./draw.js";
import { labelText, lengthFor, load, save } from "./graph-settings.js";
import { graphSection } from "./graph-panel.js";
import { lookKey, openLookPanel } from "./node-look.js";

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
    /** A project's own color: its category's, shifted a little per project, so two
     * projects of one category are told apart (the owner may choose it, ``node.look``). */
    projectColor(node) {
      if (node.look && node.look.color) return node.look.color;
      return shade(node.id, this.color(node.category), pal);
    },
    projectSpecies(node) { return (node.look && node.look.species) || this.species(node.category); },
    mineral(node) {
      const kind = (node.look && node.look.mineral) || "diamond";
      return { kind, color: (node.look && node.look.color) || MINERALS[kind] || MINERALS.diamond };
    },
    defs: (ramp) => DEFS + (ramp ? rampFilter(ramp) : ""),
  };
}

/* ---------- one mark per node; a mushroom's base sits on the node's point ---------- */

function mark(node, L, k = 1) {
  const { pal, paint } = L;
  const degree = node.degree || 0;
  if (node.type === "project") {
    const size = (node.look && node.look.size) || 1;
    const s = (0.36 + 0.06 * Math.sqrt(degree)) * k * size;
    const color = L.projectColor(node);
    // The glow the notes used to have now belongs to the projects.
    const aura = `<ellipse cx="0" cy="${f1(-52 * s)}" rx="${f1(44 * s)}" ry="${f1(58 * s)}" fill="${color}" opacity=".38" filter="url(#softglow)"/>`;
    const glow = `<ellipse cx="0" cy="2" rx="${f1(46 * s)}" ry="${f1(12 * s)}" fill="${color}" opacity=".6" filter="url(#softglow)"/>`;
    const body = paint.mushroom(L.projectSpecies(node), color, node.status);
    return { r: 30 * s, top: 105 * s, markup: `${aura}${glow}<g transform="scale(${s.toFixed(3)})"><g class="grow"><g class="sway">${body}</g></g></g>` };
  }
  if (node.type === "source") {
    const { kind, color } = L.mineral(node);
    const s = 0.42 * k;
    return { r: 10 * k, top: 10 * k, markup: `<g class="cloud"><g transform="scale(${s.toFixed(2)})">${paint.mineral(kind, color)}</g><circle r="${f1(12 * k)}" fill="transparent"/></g>` };
  }
  if (node.ghost) {
    return { r: 6 * k, top: 6 * k, markup: `<circle r="${f1(5 * k)}" fill="none" stroke="${pal.thread}" stroke-opacity=".55" stroke-dasharray="2 3"/><circle r="${f1(9 * k)}" fill="transparent"/>` };
  }
  if (node.type === "journal") {
    const r = 4.5 * k;
    return { r, top: r, markup: `<g class="cloud"><circle r="${f1(r)}" fill="${pal.spore}" stroke="${pal.ink}" stroke-width="1.4"/><circle r="${f1(r + 7)}" fill="transparent"/></g>` };
  }
  // A note: a plain dot in its category's color, so the links stay readable.
  const r = (3.6 + Math.sqrt(degree) * 1.25) * k;
  const ring = node.bridge
    ? `<circle r="${f1(r + 4)}" fill="none" stroke="${pal.sun}" stroke-opacity=".9" stroke-width="1.3" stroke-dasharray="2 3"/>`
    : "";
  return { r, top: r, markup: `<g class="cloud">${ring}<circle r="${f1(r)}" fill="${L.color(node.category)}" stroke="${pal.ink}" stroke-width="1.4"/><circle r="${f1(r + 7)}" fill="transparent"/></g>` };
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

/** Seeded force layout in plain 2D. A focused graph keeps its focus in the middle.
 * ``spacing`` (percent) stretches the links, the push between nodes and their room. */
function layoutFree(data, spacing = 100) {
  const s = spacing / 100;
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
    .force("link", d3.forceLink(links).id((d) => d.id).distance((l) => (touchesProject(l) ? 95 : 70) * s).strength(0.35))
    .force("charge", d3.forceManyBody().strength((d) => (d.type === "project" ? -520 : -190) * s))
    .force("collide", d3.forceCollide((d) => (d.type === "project" ? 44 : 24) * Math.sqrt(s)))
    .force("x", d3.forceX(0).strength(0.04 / s))
    .force("y", d3.forceY(0).strength(0.05 / s));
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

/** Drag to pan, wheel and buttons to zoom. ``opt.maxOut`` is how far it zooms out past the
 * home view (1: not at all), ``opt.clamp`` keeps the view inside home, ``opt.ctrlWheel``
 * leaves the plain wheel to scroll the page (graphs inside a reading page), and
 * ``opt.onZoom`` hears the zoom the viewer chose, as a ratio to the home view. */
function panZoom(svg, onChange, opt = {}) {
  const maxOut = opt.maxOut ?? 4;
  let vb = { x: 0, y: 0, w: 1, h: 1 };
  let home = vb;
  const rect = () => svg.getBoundingClientRect();
  const ratio = () => home.w / vb.w;
  const keepInside = () => {
    if (!opt.clamp) return;
    vb.x = Math.min(home.x + home.w - vb.w, Math.max(home.x, vb.x));
    vb.y = Math.min(home.y + home.h - vb.h, Math.max(home.y, vb.y));
  };
  const apply = () => {
    keepInside();
    svg.setAttribute("viewBox", `${f1(vb.x)} ${f1(vb.y)} ${f1(vb.w)} ${f1(vb.h)}`);
    onChange(rect().width / vb.w, ratio());
  };
  const zoomAt = (cx, cy, f, chosen = true) => {
    const r = rect();
    const nw = Math.min(home.w * maxOut, Math.max(home.w / 8, vb.w * f));
    const k = nw / vb.w;
    const px = vb.x + ((cx - r.left) / r.width) * vb.w;
    const py = vb.y + ((cy - r.top) / r.height) * vb.h;
    vb = { x: px - (px - vb.x) * k, y: py - (py - vb.y) * k, w: vb.w * k, h: vb.h * k };
    apply();
    if (chosen && opt.onZoom) opt.onZoom(ratio());
  };
  const center = (f, chosen) => {
    const r = rect();
    zoomAt(r.left + r.width / 2, r.top + r.height / 2, f, chosen);
  };
  svg.addEventListener("wheel", (e) => {
    if (opt.ctrlWheel && !e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    zoomAt(e.clientX, e.clientY, e.deltaY > 0 ? 1.12 : 1 / 1.12);
  }, { passive: false });
  // One pointer drags; two (fingers on a phone or tablet) pinch to zoom and move together.
  const touches = new Map();
  let drag = null;
  let pinch = null;
  const startPinch = () => {
    const [a, b] = [...touches.values()];
    pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2, vb: { ...vb } };
    drag = null;
    svg.classList.add("dragging");
    svg.dataset.dragged = "1";
  };
  svg.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    touches.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (touches.size === 2) {
      for (const id of touches.keys()) { try { svg.setPointerCapture(id); } catch { /* gone */ } }
      startPinch();
      return;
    }
    if (touches.size === 1) drag = { x: e.clientX, y: e.clientY, vb: { ...vb }, moved: false, id: e.pointerId };
  });
  svg.addEventListener("pointermove", (e) => {
    if (!touches.has(e.pointerId)) return;
    touches.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && touches.size >= 2) {
      const [a, b] = [...touches.values()];
      const r = rect();
      const d = Math.hypot(a.x - b.x, a.y - b.y) || 1;
      const nw = Math.min(home.w * maxOut, Math.max(home.w / 8, (pinch.vb.w * pinch.d) / d));
      const k = nw / pinch.vb.w;
      // The point under the fingers' first midpoint stays under their midpoint now.
      const px = pinch.vb.x + ((pinch.mx - r.left) / r.width) * pinch.vb.w;
      const py = pinch.vb.y + ((pinch.my - r.top) / r.height) * pinch.vb.h;
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      const w = pinch.vb.w * k;
      const h = pinch.vb.h * k;
      vb = { x: px - ((mx - r.left) / r.width) * w, y: py - ((my - r.top) / r.height) * h, w, h };
      apply();
      return;
    }
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
  const end = (e) => {
    touches.delete(e.pointerId);
    if (pinch) {
      if (touches.size < 2) {
        pinch = null;
        if (opt.onZoom) opt.onZoom(ratio());
        // The finger left on the glass carries on as a drag, from where it is now.
        const [rest] = [...touches.entries()];
        drag = rest ? { x: rest[1].x, y: rest[1].y, vb: { ...vb }, moved: true, id: rest[0] } : null;
        if (!rest) {
          svg.classList.remove("dragging");
          setTimeout(() => delete svg.dataset.dragged, 0);
        }
      }
      return;
    }
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
    /** Fit ``box``, then zoom to ``zoom`` (the viewer's saved ratio) around its middle. */
    show(box, zoom = 1) {
      home = fitTo(svg, box);
      vb = { ...home };
      apply();
      if (zoom !== 1) center(1 / zoom, false);
    },
    zoom: (f) => center(f, true),
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

/** A shortened name shows whole, on top of the others, while its node is pointed at or
 * focused (and a name hidden when zoomed far out shows too). */
function openLabels(svg) {
  let open = null;
  const close = () => {
    if (!open) return;
    open.textContent = open.dataset.short;
    open.classList.remove("open");
    open = null;
  };
  const reveal = (a) => {
    const text = a && svg.querySelector(`text.lbl[data-id="${CSS.escape(a.dataset.id)}"]`);
    if (text === open) return;
    close();
    if (!text) return;
    text.dataset.short = text.textContent;
    text.textContent = text.dataset.full;
    text.classList.add("open");
    text.parentNode.appendChild(text);
    open = text;
  };
  // A name is a way in too: pointing at it shows it whole, clicking it opens its node.
  const nodeOf = (target) => {
    const name = target.closest && target.closest("text.lbl");
    if (name && !name.classList.contains("crowded")) return svg.querySelector(`a.node[data-id="${CSS.escape(name.dataset.id)}"]`);
    return target.closest ? target.closest("a.node") : null;
  };
  svg.addEventListener("click", (e) => {
    const name = e.target.closest && e.target.closest("text.lbl");
    const a = name && nodeOf(e.target);
    if (!a) return;
    e.preventDefault();
    a.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, ctrlKey: e.ctrlKey, metaKey: e.metaKey, shiftKey: e.shiftKey }));
  });
  svg.addEventListener("mouseover", (e) => reveal(nodeOf(e.target)));
  svg.addEventListener("mouseleave", close);
  svg.addEventListener("focusin", (e) => reveal(e.target.closest("a.node")));
  svg.addEventListener("focusout", close);
  return { close };
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

function label(node, x, y, cls, settings) {
  const text = el("text", { class: `lbl ${cls}`, x: f1(x), y: f1(y), "text-anchor": "middle", "dominant-baseline": "hanging" });
  text.setAttribute("data-id", node.id);
  text.setAttribute("data-full", node.title);
  const scale = node.type === "project" ? 1.6 : lengthFor(node.degree);
  text.textContent = labelText(node.title, settings, scale);
  // Which name wins when two would overlap (declutter): projects, the focus, then links.
  text.setAttribute("data-rank", String((node.type === "project" ? 1e6 : 0) + (node.focus ? 5e5 : 0) + (node.degree || 0)));
  return text;
}

/** Names that would sit on top of each other: the better connected node keeps its name,
 * the other one hides it until its node is pointed at (openLabels shows it). Run again
 * after every zoom, since the names keep their size on screen. */
function declutter(root) {
  const texts = [...root.querySelectorAll("text.lbl")].sort((a, b) => Number(b.dataset.rank) - Number(a.dataset.rank));
  const kept = [];
  for (const t of texts) {
    t.classList.remove("crowded");
    let box;
    try { box = t.getBBox(); } catch { continue; }
    if (!box.width) continue;
    const pad = box.height * 0.25;
    const hit = kept.some((k) => box.x < k.x + k.width + pad && k.x < box.x + box.width + pad && box.y < k.y + k.height && k.y < box.y + box.height);
    if (hit) t.classList.add("crowded");
    else kept.push(box);
  }
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

/** What a thread joins decides how it looks, so a crowded graph still reads: a project's
 * own notes hang on solid threads in its color, journal entries on gold dots, sources
 * on dashes in the crystal color, and note-to-note links are thin and faint. */
function thread(a, b, L) {
  const kind = a.ghost || b.ghost ? "ghost"
    : a.type === "project" || b.type === "project" ? "member"
      : a.type === "journal" || b.type === "journal" ? "journal"
        : a.type === "source" || b.type === "source" ? "source" : "link";
  const p = a.type === "project" ? a : b;
  const bridge = a.bridge || b.bridge;
  const look = {
    member: { color: kind === "member" ? L.projectColor(p) : "", width: 1.8, dash: "", opacity: 0.8 },
    journal: { color: L.pal.spore, width: 1.6, dash: "0.1 5", opacity: 0.85 },
    source: { color: L.pal.crystals ? L.pal.crystals[0] : L.pal.thread, width: 1.3, dash: "7 5", opacity: 0.75 },
    link: { color: L.pal.thread, width: bridge ? 1.6 : 1, dash: "", opacity: bridge ? 0.5 : 0.32 },
    ghost: { color: L.pal.thread, width: 1, dash: "3 6", opacity: 0.4 },
  }[kind];
  const dash = look.dash ? ` stroke-dasharray="${look.dash}"` : "";
  return { kind, attrs: `stroke="${look.color}" stroke-width="${look.width}" stroke-opacity="${look.opacity}"${dash}` };
}

/** The free graph (Explore and the note's neighborhood). */
function drawFree(layer, laid, L, strings, opts) {
  const visible = opts.visible || (() => true);
  const dimmed = opts.dimmed || (() => false);
  const hyphae = el("g");
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
    const t = thread(a, b, L);
    const cls = ["hypha", `k-${t.kind}`, l.faded ? "faded" : "", dimmed(a) && dimmed(b) ? "dim" : ""].join(" ").trim();
    markup += `<path class="${cls}" d="${d}" ${t.attrs}/>`;
    if (!ghost) {
      pulses.push({ d, color: a.type === "project" ? L.projectColor(a) : b.type === "project" ? L.projectColor(b) : L.pal.spore });
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
    const y = n.type === "project" ? n.y + 8 : n.y + m.r * 1.35 + 2;
    const text = label(n, n.x, y, n.type === "project" ? "project" : n.ghost ? "ghost minor" : "minor", opts.settings);
    if (dimmed(n)) text.classList.add("dim");
    labels.appendChild(text);
  }
  const plane = el("g", { class: "pulses" });
  layer.replaceChildren(hyphae, twigs, plane, marks, labels);
  declutter(labels);
  pulsing(plane, pulses, opts.state, opts.pulseEvery || 700);
}

/** The project's own little forest: its mushroom on the soil line, its notes below, the
 * other projects its bridge notes reach standing faded at the sides. */
function drawForest(svg, data, L, strings, state, settings, zoom = 1) {
  const bg = backdropInfo();
  const soil = bg.soil;
  const r = svg.getBoundingClientRect();
  const width = Math.max(320, r.width);
  // The sky keeps its size; the underground grows down with the notes, the spacing and
  // the zoom (+ / − spread the notes apart; names keep their size).
  const w = Math.max(460, Math.min(1536, width * 1.2));
  const u = w / width; // viewBox units per screen pixel
  const skyPx = Math.max(340, Math.min(560, window.innerHeight * 0.55));
  const top = Math.max(0, soil - skyPx * u);
  const a = width / Math.max(1, window.innerHeight);
  const k = Math.max(0.75, Math.min(1.6, w / 900));
  const s = settings.spacing / 100;
  const left = (1536 - w) / 2;
  const edge = Math.max(50, w * 0.14); // room for a name beside the scene's edge
  const cx = left + w * (a > 1.3 ? 0.62 : 0.5);

  const focus = data.nodes.find((n) => n.focus);
  const others = data.nodes.filter((n) => n.type === "project" && !n.focus);
  const below = data.nodes.filter((n) => n.type !== "project");
  const nodes = [];
  if (focus) nodes.push({ ...focus, fx: cx, fy: soil + 6 });
  others.forEach((o, i) => nodes.push({ ...o, fx: cx + (i % 2 ? 1 : -1) * w * (0.28 + 0.06 * Math.floor(i / 2)), fy: soil + 6 }));
  const rand = seededRandom(focus ? focus.id : "forest");
  below.forEach((n) => nodes.push({ ...n, x: cx + (rand() - 0.5) * 300, y: soil + 120 + rand() * 200 }));
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const links = data.edges.filter((e) => byId[e.source] && byId[e.target]).map((e) => ({ ...e }));
  const d3 = window.d3;
  // More notes, more depth: the ground they settle in deepens with their number.
  const depth = (150 + 22 * Math.sqrt(below.length) * 6) * k * s;
  const sim = d3.forceSimulation(nodes).randomSource(seededRandom(`${focus ? focus.id : ""}f`)).stop()
    .force("link", d3.forceLink(links).id((d) => d.id).distance(140 * k * Math.sqrt(s)).strength(0.25))
    .force("charge", d3.forceManyBody().strength(-260 * s))
    .force("collide", d3.forceCollide(42 * k * Math.sqrt(s)))
    .force("y", d3.forceY(soil + depth * 0.55).strength(0.05));
  for (let i = 0; i < 300; i++) {
    sim.tick();
    for (const n of nodes) {
      if (n.fx != null) continue;
      n.y = Math.max(soil + 80, n.y);
      n.x = Math.max(left + edge, Math.min(left + w - edge, n.x));
    }
  }
  // Zoom spreads the underground around the focus's foot: fully downward, and sideways
  // only as far as the scene is wide.
  const free = nodes.filter((n) => n.fx == null);
  const reach = (side) => Math.max(1, ...free.map((n) => side * (n.x - cx)));
  const zx = Math.min(zoom, (cx - left - edge) / reach(-1), (left + w - edge - cx) / reach(1));
  for (const n of free) {
    n.x = cx + (n.x - cx) * Math.max(zoom < 1 ? zoom : 1, zx);
    n.y = soil + (n.y - soil) * zoom;
  }
  const deepest = Math.max(soil + 300 * u, ...free.map((n) => n.y + 70));
  const vb = { x: left, y: top, w, h: deepest - top };
  svg.setAttribute("viewBox", `${f1(vb.x)} ${f1(vb.y)} ${f1(vb.w)} ${f1(vb.h)}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMin meet");
  // Names keep a readable size on screen whatever the scene's width (a little larger here).
  const host = svg.closest(".graph");
  if (host) host.style.setProperty("--view-scale", (1 / (u * 1.15)).toFixed(3));
  const scene = svg.closest(".hero-scene");
  if (scene) {
    scene.style.setProperty("--scene-h", `${Math.round(width * vb.h / vb.w)}px`);
    scene.classList.add("sized");
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
    const look = thread(s, t, L);
    markup += `<path class="hypha k-${look.kind}${l.faded ? " faded" : ""}" d="${d}" ${look.attrs}/>`;
    if (!ghost) {
      pulses.push({ d, color: s.type === "project" ? L.projectColor(s) : L.pal.spore });
    }
  }
  const marks = el("g");
  const labels = el("g");
  for (const n of nodes) {
    const link = nodeLink(n, strings, true);
    if (n.type === "project") {
      const s = (n.focus ? 1 : 0.62) * k * ((n.look && n.look.size) || 1);
      const color = L.projectColor(n);
      const body = L.paint.mushroom(L.projectSpecies(n), color, n.status);
      const aura = `<ellipse cx="0" cy="-55" rx="48" ry="62" fill="${color}" opacity=".35" filter="url(#softglow)"/>`;
      link.appendChild(fragment(`<g transform="translate(${f1(n.x)},${soil + 4}) scale(${s.toFixed(2)})">${aura}<g class="grow"><g class="sway">${body}</g></g></g>`));
      if (!n.focus) labels.appendChild(label(n, n.x, soil + 18, "project-small", settings));
    } else {
      const m = mark(n, L, k);
      link.appendChild(fragment(`<g transform="translate(${f1(n.x)},${f1(n.y)})">${m.markup}</g>`));
      labels.appendChild(label(n, n.x, n.y + m.r * 1.4 + 2, n.ghost ? "ghost minor" : "minor", settings));
    }
    marks.appendChild(link);
  }
  const image = el("g");
  const painting = (attrs) => el("image", {
    href: bg.url, x: 0, y: 0, width: 1536, height: 1024, preserveAspectRatio: "xMidYMid slice",
    filter: bg.ramp ? "url(#bgmap)" : null, ...attrs,
  });
  image.appendChild(painting({}));
  // Deeper than the painting: its underground again, band after band.
  const band = 1024 - soil - 40;
  for (let y = 1024; band > 40 && y < vb.y + vb.h; y += band) {
    const tile = el("svg", { x: 0, y: f1(y), width: 1536, height: f1(band), viewBox: `0 ${soil + 40} 1536 ${band}`, preserveAspectRatio: "none" });
    tile.appendChild(painting({}));
    image.appendChild(tile);
  }
  if (vb.y + vb.h > 1024) image.appendChild(el("rect", { class: "ground-shade", x: 0, y: 1024, width: 1536, height: f1(vb.y + vb.h - 1024) }));
  const plane = el("g", { class: "pulses" });
  const hyphae = el("g");
  hyphae.appendChild(fragment(markup));
  const twigLayer = el("g");
  twigLayer.appendChild(fragment(twigMarkup));
  svg.replaceChildren(el("defs", {}, L.defs(bg.ramp)), image, hyphae, twigLayer, plane, marks, labels);
  declutter(labels);
  pulsing(plane, pulses, state, 1000);
  return vb;
}

/* ---------- zoom buttons ---------- */

function html(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) node.setAttribute(k, String(v));
  if (text) node.textContent = text;
  return node;
}

/** + / − / Fit and ⚙ in the graph's top right corner. The ⚙ opens the viewer's settings
 * (spacing, names; static/js/graph-panel.js), which tell every graph when they change. */
function zoomButtons(host, strings, { hint, onZoom, onFit }) {
  const bar = html("div", { class: "graph-tools" });
  if (hint) {
    // Shown while pointed at or focused (CSS), and read out as the button's name.
    const help = html("span", { class: "graph-help" });
    help.append(html("button", { type: "button", class: "graph-help-icon", "aria-label": hint }, "i"), html("span", { class: "graph-help-text glass", role: "tooltip" }, hint));
    bar.appendChild(help);
  }
  const button = (attrs, text, fn) => {
    const b = html("button", { type: "button", ...attrs }, text);
    b.addEventListener("click", fn);
    bar.appendChild(b);
    return b;
  };
  button({ "data-zoom": "in", "aria-label": tr(strings, "graph.zoom_in"), title: tr(strings, "graph.zoom_in") }, "+", () => onZoom(1 / 1.3));
  button({ "data-zoom": "out", "aria-label": tr(strings, "graph.zoom_out"), title: tr(strings, "graph.zoom_out") }, "−", () => onZoom(1.3));
  button({ "data-zoom": "fit" }, tr(strings, "graph.fit"), onFit);
  const panel = html("div", { class: "graph-panel glass", hidden: "" });
  graphSection(panel, strings);
  const open = (yes) => {
    panel.hidden = !yes;
    gear.setAttribute("aria-expanded", String(yes));
    // On a phone only the ⚙ shows until it is opened (CSS).
    bar.classList.toggle("open", yes);
  };
  const gear = button({ class: "graph-gear", "aria-expanded": "false", "aria-label": tr(strings, "graph.settings"), title: tr(strings, "graph.settings") }, "⚙", () => open(panel.hidden));
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") { open(false); gear.focus(); } });
  document.addEventListener("pointerdown", (e) => { if (!panel.hidden && !bar.contains(e.target)) open(false); });
  bar.appendChild(panel);
  host.appendChild(bar);
}

/** The most connected nodes, at most ``max``: projects first, ghosts last. */
function trim(data, max) {
  if (!max || data.nodes.length <= max) return { data, hidden: 0 };
  const rank = (n) => (n.type === "project" ? 2 : n.ghost ? 0 : 1);
  const kept = [...data.nodes].sort((a, b) => rank(b) - rank(a) || b.degree - a.degree || a.id.localeCompare(b.id)).slice(0, max);
  const ids = new Set(kept.map((n) => n.id));
  const hidden = data.nodes.filter((n) => !ids.has(n.id) && !n.ghost).length;
  return { data: { ...data, nodes: kept, edges: data.edges.filter((e) => ids.has(e.source) && ids.has(e.target)) }, hidden };
}

/** The underground of the painting behind a note's neighborhood, fixed while it pans. */
function groundBehind(host, L, bg) {
  if (!bg.url) return;
  const top = bg.soil + 30;
  host.prepend(el("svg", {
    class: "graph-ground", "aria-hidden": "true", focusable: "false",
    viewBox: `0 ${top} 1536 ${1024 - top}`, preserveAspectRatio: "xMidYMid slice",
  },
  el("defs", {}, bg.ramp ? rampFilter(bg.ramp) : ""),
  el("image", { href: bg.url, x: 0, y: 0, width: 1536, height: 1024, preserveAspectRatio: "xMidYMid slice", filter: bg.ramp ? "url(#bgmap)" : null }),
  el("rect", { class: "ground-shade", x: 0, y: top, width: 1536, height: 1024 - top })));
}

/** Draw the graph named by ``el.dataset.graph`` into ``el``. ``data-mode`` is ``free``
 * (the whole vault on /explore, the default), ``box`` (a note's neighborhood over the
 * underground) or ``forest`` (a project's scene on the soil line). Every mode pans and
 * zooms and has the viewer's settings panel; inside a reading page the plain wheel keeps
 * scrolling the page. Resolves to a small controller. */
export async function mountGraph(host) {
  const status = host.querySelector(".graph-status");
  const strings = await loadStrings();
  if (!window.d3) return null;
  let data;
  try {
    // A visitor's own palette (look.js) colors the categories too.
    const url = new URL(host.dataset.graph, location.href);
    if (document.documentElement.dataset.palette) url.searchParams.set("palette", document.documentElement.dataset.palette);
    const response = await fetch(url, { headers: { Accept: "application/json" } });
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
  const settings = load();
  const svg = el("svg", { class: "graph-svg pannable", role: "group", "aria-label": host.getAttribute("aria-label") || "" });
  host.removeAttribute("role");
  host.prepend(svg);
  host.classList.add(`graph-${mode}`);
  const labelZoom = () => host.style.setProperty("--label-zoom", String(settings.labels / 100));
  labelZoom();
  const nodesById = Object.fromEntries(data.nodes.map((n) => [n.id, n]));
  tooltips(host, svg, nodesById, strings);
  const labels = openLabels(svg);

  // How to use the graph sits behind a discreet ⓘ in the corner; the status line only
  // says how many nodes were left out, if any.
  const hint = tr(strings, mode === "free" ? "graph.hint" : "graph.hint_box");
  if (status) {
    status.textContent = trimmed.hidden ? (trimmed.hidden === 1 ? tr(strings, "landing.more_one") : tr(strings, "landing.more", { count: trimmed.hidden })) : "";
  }

  const rememberZoom = (ratio) => {
    settings.zoom[mode] = ratio;
    save(settings);
  };
  const embedded = mode !== "free";
  let home = null;
  let narrow = false;
  let tidy = null;
  const view = mode === "forest" ? null : panZoom(svg, (scale, ratio) => {
    if (mode === "forest") {
      // A narrow scene: the notes' names would overlap; the tooltip and the list say them.
      svg.classList.toggle("far", narrow && ratio < 1.5);
      requestAnimationFrame(soilLine);
      return;
    }
    // Zoomed out, the names keep a readable size on screen and the crowded ones hide.
    host.style.setProperty("--view-scale", String(Math.max(0.3, Math.min(1, scale))));
    clearTimeout(tidy);
    tidy = setTimeout(() => declutter(svg), 120);
  }, { onZoom: rememberZoom, ctrlWheel: embedded, maxOut: mode === "forest" ? 1 : mode === "box" ? 2 : 4, clamp: mode === "forest" });

  // Where the soil line is on screen, for what stands on it (the project's growth card).
  const scene = host.closest(".hero-scene");
  function soilLine() {
    const ctm = scene && svg.getScreenCTM();
    if (!ctm) return;
    const y = ctm.d * backdropInfo().soil + ctm.f - scene.getBoundingClientRect().top;
    scene.style.setProperty("--soil-y", `${Math.round(y)}px`);
    scene.classList.add("has-soil");
  }

  let depthZoom = Math.max(0.6, Math.min(3, Number(settings.zoom.forest) || 1));
  let visible = () => true;
  let dimmed = () => false;
  let laid = null;
  let redraw;
  let fitBox;

  if (mode === "forest") {
    redraw = () => {
      labels.close();
      home = drawForest(svg, data, L, strings, state, settings, depthZoom);
      requestAnimationFrame(soilLine);
      narrow = home.w < 700;
    };
    fitBox = () => home;
  } else {
    if (mode === "box") groundBehind(host, L, backdropInfo());
    svg.appendChild(el("defs", {}, L.defs(null)));
    const layer = el("g", { class: "layer" });
    svg.appendChild(layer);
    laid = layoutFree(data, settings.spacing);
    redraw = () => {
      labels.close();
      drawFree(layer, laid, L, strings, { visible, dimmed, state, settings, focusAll: mode === "box", pulseEvery: mode === "box" ? 1100 : 700 });
    };
    fitBox = () => bounds(laid.nodes.filter((n) => visible(n)), mode === "box" ? 70 : 60);
  }
  const all = () => (laid ? laid.nodes.filter((n) => visible(n)) : []);
  const place = () => { if (view) view.show(fitBox(), settings.zoom[mode]); };
  redraw();
  place();

  zoomButtons(host, strings, {
    hint,
    // In a project's scene + / − spread the underground only; the sky stays.
    onZoom: (f) => {
      if (view) return view.zoom(f);
      depthZoom = Math.max(0.6, Math.min(3, depthZoom / f));
      rememberZoom(depthZoom);
      redraw();
    },
    onFit: () => {
      rememberZoom(1);
      if (view) return place();
      depthZoom = 1;
      redraw();
    },
  });
  // On its own page the owner dresses the project or source: clicking its mushroom or
  // mineral opens the look editor instead of reloading the page.
  if (lookKey()) {
    svg.addEventListener("click", (e) => {
      const a = e.target.closest && e.target.closest("a.node");
      const node = a && nodesById[a.dataset.id];
      if (!node || !node.focus || (node.type !== "project" && node.type !== "source")) return;
      if (e.ctrlKey || e.metaKey || e.shiftKey) return;
      e.preventDefault();
      e.stopPropagation();
      const now = node.type === "project"
        ? { species: L.projectSpecies(node), color: L.projectColor(node), size: (node.look && node.look.size) || 1 }
        : (() => { const m = L.mineral(node); return { mineral: m.kind, color: m.color }; })();
      openLookPanel(host, node, now, strings, (lookNow) => {
        node.look = lookNow;
        if (laid) for (const n of laid.nodes) if (n.id === node.id) n.look = lookNow;
        redraw();
      });
    });
  }
  // A ⚙ panel saved new settings: take them and draw again as needed.
  window.addEventListener("micelio:graph-settings", (e) => {
    const key = e.detail && e.detail.key;
    const fresh = load();
    for (const k of ["spacing", "labels", "shorten", "length"]) settings[k] = fresh[k];
    if (key === "labels") { labelZoom(); return redraw(); }
    if (key === "spacing" && laid) laid = layoutFree(data, settings.spacing);
    redraw();
    if (key === "spacing" || key === "reset") place();
    labelZoom();
  });

  let timer = null;
  window.addEventListener("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(() => { if (mode === "forest") redraw(); place(); }, 150);
  });
  return {
    data,
    strings,
    svg,
    get nodes() { return laid ? laid.nodes : []; },
    settings,
    /** Show only nodes for which ``fn`` is true; fit them. */
    filter(fn) { visible = fn; redraw(); place(); },
    /** Dim everything except nodes for which ``fn`` is true (or nothing, with null). */
    highlight(fn) { dimmed = fn ? (n) => !fn(n) : () => false; redraw(); },
    fit(nodes) { if (view) view.show(nodes && nodes.length ? bounds(nodes, 140) : bounds(all(), 60)); },
    zoom: (f) => view && view.zoom(f),
  };
}

/** Every ``[data-graph]`` on the page that is not handled by a page of its own. */
export function mountAll(root = document) {
  return Promise.all(
    [...root.querySelectorAll("[data-graph]:not([data-graph-manual])")].map((host) => mountGraph(host)),
  );
}
