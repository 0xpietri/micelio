// Mycelium landing (§7a): mushrooms above the soil, mycelium below, drawn as SVG over
// the background image. Plain ES module, no build step. Positions come from the vendored
// d3-force (global `d3`), seeded by the vault so the same vault draws the same forest.

import {
  DEFS, SVG_NS, cloud, el, f1, fragment, hyphaPath, lighter, loadStrings, painter, rampFilter,
  reduced, seededRandom, tr,
} from "./draw.js";

function viewWindow(svg, soil) {
  const r = svg.getBoundingClientRect();
  const a = r.width / Math.max(1, r.height);
  if (a >= 1.5) {
    const h = 1536 / a;
    return { x: 0, y: Math.min(Math.max(soil - h * 0.52, 0), 1024 - h), w: 1536, h };
  }
  const w = 1024 * a;
  return { x: (1536 - w) / 2, y: 0, w, h: 1024 };
}

function layout(data, V, soil, k) {
  const narrow = V.w < 900;
  const left = V.x + (narrow ? 50 : 140);
  const right = V.x + V.w - 60;
  const count = data.projects.length;
  const step = (right - left) / Math.max(1, count - 1);
  const crowd = Math.min(1, step / 110);

  const projects = data.projects.map((p, i) => {
    const rand = seededRandom(p.id);
    const x = count === 1 ? (left + right) / 2 : left + step * i + (rand() - 0.5) * step * 0.3;
    const size = k * crowd * Math.min(1.6, 0.78 + 0.17 * Math.sqrt(p.notes));
    return { ...p, x, size };
  });
  const byId = Object.fromEntries(projects.map((p) => [p.id, p]));

  const nodes = [
    ...projects.map((p) => ({ id: p.id, kind: "project", fx: p.x, fy: soil + 8 })),
    ...data.notes.map((n) => {
      const homes = n.projects.map((id) => byId[id].x);
      const hx = homes.length ? homes.reduce((a, b) => a + b, 0) / homes.length : V.x + V.w * 0.55;
      const r = seededRandom("n" + n.id);
      return {
        id: n.id, kind: "note", note: n, hx,
        hy: soil + 150 + (n.projects.length > 1 ? 150 : 0) + r() * 120,
        x: hx + (r() - 0.5) * 60, y: soil + 180 + r() * 160,
      };
    }),
    ...data.sources.map((s) => {
      const r = seededRandom(s.id);
      return { id: s.id, kind: "source", source: s, hx: null, hy: V.y + V.h - 90, x: V.x + V.w * r(), y: V.y + V.h - 120 };
    }),
  ];
  const known = new Set(nodes.map((n) => n.id));
  const links = [
    ...data.notes.flatMap((n) => n.projects.map((p) => ({ source: p, target: n.id, kind: "member", bridge: n.projects.length > 1 }))),
    ...data.links.map(([a, b]) => ({ source: a, target: b, kind: "link" })),
    ...data.sources.flatMap((s) => s.links.filter((t) => known.has(t)).map((t) => ({ source: t, target: s.id, kind: "source" }))),
  ];

  const d3 = window.d3;
  const seed = data.projects.map((p) => p.id).join("|") + data.notes.length;
  const sim = d3.forceSimulation(nodes).randomSource(seededRandom(seed)).stop()
    .force("link", d3.forceLink(links).id((d) => d.id).distance((l) => (l.kind === "member" ? 150 * k : 90 * k)).strength(0.25))
    .force("charge", d3.forceManyBody().strength(-60))
    .force("collide", d3.forceCollide((d) => (d.kind === "project" ? 10 : 22 * k)))
    .force("x", d3.forceX((d) => d.hx ?? d.x).strength((d) => (d.kind === "note" ? 0.12 : 0.02)))
    .force("y", d3.forceY((d) => d.hy ?? d.y).strength(0.08));
  const minY = soil + 60;
  const maxY = V.y + V.h - 50;
  const ticks = Math.min(300, 60 + Math.round(30000 / Math.max(1, nodes.length)));
  for (let i = 0; i < ticks; i++) {
    sim.tick();
    for (const d of nodes) {
      if (d.kind === "project") continue;
      d.y = Math.max(minY, Math.min(maxY, d.y));
      d.x = Math.max(V.x + 30, Math.min(V.x + V.w - 30, d.x));
    }
  }
  return { projects, byId, nodes, links };
}

function draw(svg, data, strings, state) {
  const pal = data.palette;
  const paint = painter(pal);
  const soil = Math.round((1024 * data.background.soil) / 100);
  const V = viewWindow(svg, soil);
  svg.setAttribute("viewBox", `${f1(V.x)} ${f1(V.y)} ${f1(V.w)} ${f1(V.h)}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid slice");
  const k = Math.min(1.7, Math.max(0.75, V.w / 900));
  const motion = !reduced();
  const t = (key, values) => tr(strings, key, values);

  const { projects, byId, nodes, links } = layout(data, V, soil, k);
  const delay = (s) => `data-delay="${motion ? s.toFixed(2) : 0}"`;

  let hyphae = "";
  const pulses = [];
  links.forEach((l, i) => {
    const a = l.source;
    const b = l.target;
    const from = a.kind === "project" ? { x: a.x, y: soil + 6 } : a;
    const { d, twigs } = hyphaPath(from, b, a.id + b.id, soil);
    const width = l.bridge ? 3.2 : l.kind === "source" ? 1.4 : 1.8;
    const start = 0.2 + (l.kind === "member" ? 0 : 1.2) + i * 0.02;
    hyphae += `<path class="hypha" pathLength="1" d="${d}" stroke-width="${width}" ${delay(start)}/>`;
    for (const twig of twigs) hyphae += `<path class="hypha twig" pathLength="1" d="${twig}" stroke-width="1" ${delay(start + 1.2)}/>`;
    pulses.push({ d, color: l.kind === "member" ? byId[a.id].color : pal.thread });
  });

  const degree = {};
  for (const l of links) {
    degree[l.source.id] = (degree[l.source.id] || 0) + 1;
    degree[l.target.id] = (degree[l.target.id] || 0) + 1;
  }

  const link = (cls, item, sub, start, focusable) => el("a", {
    class: cls,
    href: item.href,
    tabindex: focusable ? null : "-1",
    "data-title": item.title,
    "data-sub": sub,
    "data-delay": start === null ? null : motion ? start.toFixed(2) : 0,
  });

  const knots = el("g");
  nodes.filter((d) => d.kind === "note").forEach((d, i) => {
    const r = (9 + Math.sqrt(degree[d.id] || 0) * 4) * Math.max(0.9, k * 0.85);
    const bridge = d.note.projects.length > 1;
    const home = d.note.projects.length ? byId[d.note.projects[0]].title : "";
    const sub = t("type.note") + (bridge ? " · " + t("landing.bridge") : home ? " · " + home : "");
    const a = link("knot", d.note, sub, 1.6 + i * 0.03, false);
    a.appendChild(fragment(`<g transform="translate(${f1(d.x)},${f1(d.y)})"><g class="cloud">
      <circle r="${f1(r * 1.5)}" fill="${pal.thread}" opacity=".16" filter="url(#softglow)"/>
      ${bridge ? `<circle r="${f1(r + 5)}" fill="none" stroke="${pal.thread}" stroke-opacity=".5" stroke-width="1" stroke-dasharray="2 4"/>` : ""}
      ${cloud(r, d.id, pal.thread)}
      <circle r="${f1(r * 1.6)}" fill="transparent"/></g></g>`));
    knots.appendChild(a);
  });

  const crystals = el("g");
  nodes.filter((d) => d.kind === "source").forEach((d, i) => {
    const a = link("crystal", d.source, t("type.source"), 2.2, false);
    a.appendChild(fragment(`<g transform="translate(${f1(d.x)},${f1(d.y)}) scale(${k.toFixed(2)})">${paint.crystal(pal.crystals[i % 2])}</g>`));
    crystals.appendChild(a);
  });

  const shrooms = el("g");
  projects.forEach((p, i) => {
    const count = p.notes === 1 ? t("landing.notes_one") : t("landing.notes", { count: p.notes });
    const status = t("status." + p.status);
    const a = link("mushroom", p, `${t("type.project")} · ${status} · ${count}`, null, true);
    a.setAttribute("aria-label", `${t("type.project")}: ${p.title}, ${status}`);
    a.appendChild(fragment(`<g transform="translate(${f1(p.x)},${soil + 4}) scale(${p.size.toFixed(2)})"><g class="grow"><g class="sway" data-sway="${(i * 1.3).toFixed(1)}">
      ${paint.mushroom(p.species, p.color, p.status)}</g></g></g>`));
    shrooms.appendChild(a);
  });
  if (!projects.length) {
    const x = V.x + V.w / 2;
    shrooms.appendChild(fragment(`<g transform="translate(${f1(x)},${soil + 4}) scale(${k.toFixed(2)})" aria-hidden="true">${paint.button(pal.cats[0])}</g>`));
  }

  const spores = el("g");
  data.journal.forEach((j, i) => {
    const p = byId[j.links[0]];
    if (!p) return;
    const r = seededRandom(j.id);
    const x = p.x + (r() < 0.5 ? -1 : 1) * (45 + r() * 25) * p.size;
    const y = soil - (125 + r() * 30) * p.size;
    const a = link("spore", j, t("type.journal"), 2.6, false);
    a.appendChild(fragment(`<g transform="translate(${f1(x)},${f1(y)})"><g class="drift" data-sway="${i * 2}">
      <circle r="24" fill="${pal.spore}" opacity=".5" filter="url(#softglow)"/>${cloud(15, j.id, lighter(pal.spore, 0.5))}
      <circle r="24" fill="transparent"/></g></g>`));
    spores.appendChild(a);
  });

  const recolor = data.background.recolor && pal.ramp;
  const image = el("image", {
    href: data.background.url,
    x: 0, y: 0, width: 1536, height: 1024,
    preserveAspectRatio: "xMidYMid slice",
    filter: recolor ? "url(#bgmap)" : null,
  });
  const label = svg.querySelector("title");
  svg.replaceChildren(
    label,
    el("defs", {}, DEFS + (recolor ? rampFilter(pal.ramp) : "")),
    image,
    el("g", { filter: "url(#glow)" }, hyphae),
    el("g", { class: "pulses" }),
    crystals, knots, shrooms, spores,
  );

  // Inline style attributes are blocked by the CSP; the CSSOM is not.
  for (const el of svg.querySelectorAll("[data-delay]")) el.style.animationDelay = `${el.dataset.delay}s`;
  for (const el of svg.querySelectorAll("[data-sway]")) el.style.animationDelay = `-${el.dataset.sway}s`;

  clearInterval(state.pulseTimer);
  if (motion && pulses.length) {
    const layer = svg.querySelector(".pulses");
    const ghost = document.createElementNS(SVG_NS, "path");
    state.pulseTimer = setInterval(() => {
      if (document.hidden) return;
      const pulse = pulses[Math.floor(Math.random() * pulses.length)];
      ghost.setAttribute("d", pulse.d);
      const total = ghost.getTotalLength();
      const dot = document.createElementNS(SVG_NS, "circle");
      dot.setAttribute("r", "3.5");
      dot.setAttribute("fill", pulse.color);
      dot.setAttribute("filter", "url(#glow)");
      layer.appendChild(dot);
      const t0 = performance.now();
      const run = (now) => {
        const f = Math.min(1, (now - t0) / 1600);
        const pt = ghost.getPointAtLength(total * f);
        dot.setAttribute("cx", pt.x);
        dot.setAttribute("cy", pt.y);
        dot.setAttribute("opacity", Math.sin(Math.PI * f));
        if (f < 1) requestAnimationFrame(run);
        else dot.remove();
      };
      requestAnimationFrame(run);
    }, 900);
  }
}

/* ---------- title on one line, shrunk to fit ---------- */

function fitHeadline() {
  const h = document.getElementById("headline");
  if (!h) return;
  const hero = h.parentElement;
  h.style.fontSize = "";
  const cs = getComputedStyle(hero);
  const avail = (hero.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)) * (window.innerWidth > 900 ? 0.62 : 1);
  const max = parseFloat(getComputedStyle(h).fontSize);
  if (h.scrollWidth > avail) h.style.fontSize = `${Math.max(12, (max * avail) / h.scrollWidth).toFixed(1)}px`;
}

/* ---------- tooltips ---------- */

function tooltips(scene, svg) {
  const tip = document.getElementById("tip");
  const show = (el, evt) => {
    tip.replaceChildren();
    const strong = document.createElement("strong");
    strong.textContent = el.dataset.title;
    const span = document.createElement("span");
    span.textContent = el.dataset.sub;
    tip.append(strong, span);
    tip.hidden = false;
    const box = scene.getBoundingClientRect();
    let x;
    let y;
    if (evt && evt.clientX) {
      x = evt.clientX - box.left + 14;
      y = evt.clientY - box.top + 14;
    } else {
      const r = el.getBoundingClientRect();
      x = r.left - box.left + r.width / 2;
      y = r.top - box.top - 10;
    }
    tip.style.left = `${Math.max(8, Math.min(x, box.width - tip.offsetWidth - 12))}px`;
    tip.style.top = `${Math.max(8, Math.min(y, box.height - tip.offsetHeight - 12))}px`;
  };
  svg.addEventListener("mousemove", (e) => {
    const a = e.target.closest("a[data-title]");
    if (a) show(a, e);
    else tip.hidden = true;
  });
  svg.addEventListener("mouseleave", () => { tip.hidden = true; });
  svg.addEventListener("focusin", (e) => {
    const a = e.target.closest("a[data-title]");
    if (a) show(a);
  });
  svg.addEventListener("focusout", () => { tip.hidden = true; });
}

/* ---------- start ---------- */

async function start() {
  const scene = document.getElementById("scene");
  const svg = document.getElementById("forest");
  if (!scene || !svg || !window.d3) return;
  let data;
  try {
    const response = await fetch("/api/landing", { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    data = await response.json();
  } catch {
    return;
  }
  const strings = await loadStrings();
  const state = { pulseTimer: null };
  const redraw = () => draw(svg, data, strings, state);
  fitHeadline();
  redraw();
  tooltips(scene, svg);
  if (document.fonts) document.fonts.ready.then(fitHeadline);
  let timer = null;
  window.addEventListener("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(() => { fitHeadline(); redraw(); }, 150);
  });
}

start();
