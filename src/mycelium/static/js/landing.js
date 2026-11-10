// Mycelium landing (§7a): mushrooms above the soil, mycelium below, drawn as SVG over
// the background image. Plain ES module, no build step. Positions come from the vendored
// d3-force (global `d3`), seeded by the vault so the same vault draws the same forest.

const SVG_NS = "http://www.w3.org/2000/svg";
const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------- small helpers ---------- */

function seededRandom(seed) {
  // mulberry32 over a string hash
  let a = 0;
  for (const ch of String(seed)) a = (Math.imul(a, 31) + ch.charCodeAt(0)) >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function mix(hex, other, k) {
  const parse = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const a = parse(hex);
  const b = parse(other);
  return "#" + a.map((v, i) => Math.round(v + (b[i] - v) * k).toString(16).padStart(2, "0")).join("");
}
const darker = (c, k) => mix(c, "#000000", k);
const lighter = (c, k) => mix(c, "#ffffff", k);

/** SVG elements from markup built here from numbers and palette colors only. Titles,
 * links and other vault text never enter markup: they are set with setAttribute. */
function fragment(markup) {
  const doc = new DOMParser().parseFromString(`<svg xmlns="${SVG_NS}">${markup}</svg>`, "image/svg+xml");
  const out = document.createDocumentFragment();
  for (const node of [...doc.documentElement.childNodes]) out.appendChild(document.importNode(node, true));
  return out;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) node.setAttribute(k, String(v));
  for (const child of children) if (child) node.appendChild(typeof child === "string" ? fragment(child) : child);
  return node;
}
const f1 = (n) => n.toFixed(1);

function tr(strings, key, values = {}) {
  const text = strings[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (all, name) => (name in values ? String(values[name]) : all));
}

async function loadStrings() {
  const lang = document.documentElement.lang || "en";
  try {
    const r = await fetch(`/static/locales/${encodeURIComponent(lang)}.json`);
    return r.ok ? await r.json() : {};
  } catch {
    return {};
  }
}

/* ---------- the eight species: base at (0,0), about 100 units tall ---------- */

function painter(pal) {
  const INK = pal.ink;
  const STEM = pal.stem;
  const P = (d, fill, sw = 3) =>
    `<path d="${d}" fill="${fill}" stroke="${INK}" stroke-width="${sw}" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`;
  const E = (x, y, rx, ry, fill, sw = 2) =>
    `<ellipse cx="${x}" cy="${y}" rx="${rx}" ry="${ry}" fill="${fill}" stroke="${INK}" stroke-width="${sw}" vector-effect="non-scaling-stroke"/>`;
  const HL = (d) => `<path d="${d}" fill="#fff" opacity=".28"/>`;
  const line = (d, color, w) =>
    `<path d="${d}" fill="none" stroke="${color}" stroke-width="${w}" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`;

  const species = {
    "fly-agaric"(c) {
      const dots = [[-24, -74, 6, 5], [-5, -88, 7, 5.5], [17, -80, 6, 5], [31, -64, 4, 3.5], [-35, -61, 4, 3.5], [4, -68, 5, 4], [-14, -60, 3.5, 3]];
      return P("M-9,0 C-11,-20 -8,-40 -7,-56 L7,-56 C8,-40 11,-20 9,0 Z", STEM)
        + P("M-15,0 C-16,-8 -10,-12 0,-12 C10,-12 16,-8 15,0 Z", STEM)
        + P("M-9,-41 C-15,-34 -12,-29 -8,-31 C-3,-28 3,-28 8,-31 C12,-29 15,-34 9,-41 Z", STEM)
        + P("M-42,-54 Q0,-44 42,-54 Q0,-61 -42,-54 Z", darker(STEM, 0.18))
        + P("M-44,-54 C-46,-82 -26,-102 0,-102 C26,-102 46,-82 44,-54 Q0,-47 -44,-54 Z", c)
        + HL("M-32,-80 C-26,-92 -12,-98 -2,-98 C-14,-93 -24,-86 -28,-74 Z")
        + dots.map(([x, y, rx, ry]) => E(x, y, rx, ry, STEM, 1.6)).join("");
    },
    "shaggy-inkcap"(c) {
      const scale = darker(c, 0.35);
      let s = "";
      for (let r = 0; r < 5; r++) {
        for (let i = 0; i < 4 - (r > 2 ? 1 : 0); i++) {
          const y = -50 - r * 12;
          const x = -11 + i * 7.5 + (r % 2) * 3.5 + (r > 2 ? 2 : 0);
          s += line(`M${x - 3},${y - 3} L${x},${y + 2} L${x + 3},${y - 3}`, scale, 1.8);
        }
      }
      return P("M-5,0 C-6,-20 -5,-35 -4,-48 L4,-48 C5,-35 6,-20 5,0 Z", STEM)
        + E(0, -1, 9, 3.5, STEM)
        + P("M-17,-38 C-20,-72 -14,-104 0,-112 C14,-104 20,-72 17,-38 C10,-34 -10,-34 -17,-38 Z", mix(c, STEM, 0.45))
        + P("M-7,-104 C-4,-112 4,-112 7,-104 C3,-106 -3,-106 -7,-104 Z", c)
        + s + HL("M-11,-60 C-12,-80 -8,-96 -3,-104 C-6,-92 -8,-78 -7,-62 Z")
        + P("M-17,-38 C-17,-29 -13,-29 -12,-35 C-11,-26 -7,-26 -6,-34 C-4,-28 0,-28 1,-34 C3,-26 7,-26 8,-34 C10,-29 14,-29 17,-38 C10,-34 -10,-34 -17,-38 Z", INK, 2);
    },
    morel(c) {
      const pit = darker(c, 0.5);
      let s = "";
      [[-46, 17], [-57, 16.5], [-68, 15], [-79, 12], [-90, 8]].forEach(([y, hw], r) => {
        const n = Math.max(2, Math.floor((hw * 2) / 8.5));
        for (let i = 0; i < n; i++) {
          const x = -hw + 5 + (i + (r % 2 ? 0.5 : 0)) * ((hw * 2 - 10) / Math.max(1, n - (r % 2 ? 0 : 1)));
          if (Math.abs(x) < hw - 3) s += `<ellipse cx="${f1(x)}" cy="${y}" rx="3.2" ry="4.4" fill="${pit}"/>`;
        }
      });
      return P("M-12,0 C-14,-14 -12,-30 -11,-42 L11,-42 C12,-30 14,-14 12,0 Z", STEM)
        + line("M-6,-8 C-4,-18 -7,-26 -5,-34 M5,-6 C7,-16 4,-24 6,-34", darker(STEM, 0.3), 1.5)
        + P("M-20,-38 C-26,-62 -14,-96 0,-104 C14,-96 26,-62 20,-38 C10,-34 -10,-34 -20,-38 Z", c)
        + s + HL("M-14,-56 C-15,-74 -9,-90 -2,-98 C-6,-86 -10,-72 -10,-56 Z");
    },
    chanterelle(c) {
      const ridge = darker(c, 0.35);
      const ridges = [-24, -14, -5, 5, 14, 24].map((x) => line(`M${x},-46 Q${f1(x * 0.45)},-28 ${f1(x * 0.15)},-8`, ridge, 1.5)).join("");
      return P("M-6,0 C-7,-16 -12,-30 -32,-48 C-24,-56 -14,-52 -8,-56 C-2,-50 4,-58 10,-54 C16,-58 26,-54 32,-48 C12,-30 7,-16 6,0 Z", c)
        + ridges
        + P("M-32,-48 C-24,-56 -14,-52 -8,-56 C-2,-50 4,-58 10,-54 C16,-58 26,-54 32,-48 C16,-43 -16,-43 -32,-48 Z", lighter(c, 0.25))
        + HL("M-22,-50 C-16,-53 -10,-52 -6,-53 C-10,-50 -16,-49 -22,-50 Z");
    },
    "liberty-caps"(c) {
      const one = (x, h, rot) => `<g transform="rotate(${rot},${x},0)">`
        + P(`M${x - 2},0 C${x - 5},${-h * 0.4} ${x + 3},${-h * 0.7} ${x - 1.5},${-h + 3} L${x + 1.5},${-h + 3} C${x + 6},${-h * 0.7} ${x - 1},${-h * 0.4} ${x + 2},0 Z`, STEM, 2.4)
        + P(`M${x - 11},${-h + 5} C${x - 11},${-h - 6} ${x - 5},${-h - 14} ${x},${-h - 24} C${x + 5},${-h - 14} ${x + 11},${-h - 6} ${x + 11},${-h + 5} Q${x},${-h + 1} ${x - 11},${-h + 5} Z`, c, 2.6)
        + line(`M${x - 10},${-h + 1} Q${x},${-h - 3} ${x + 10},${-h + 1}`, darker(c, 0.4), 2)
        + HL(`M${x - 6},${-h - 2} C${x - 5},${-h - 10} ${x - 2},${-h - 16} ${x},${-h - 20} C${x - 2},${-h - 12} ${x - 3},${-h - 6} ${x - 3},${-h} Z`)
        + "</g>";
      return one(-15, 64, -12) + one(16, 54, 15) + one(1, 84, 3);
    },
    coral(c) {
      const segs = [];
      const branch = (x, y, ang, len, depth) => {
        const x2 = x + Math.cos(ang) * len;
        const y2 = y + Math.sin(ang) * len;
        const mx = (x + x2) / 2 + Math.cos(ang + 1.5) * len * 0.12;
        const my = (y + y2) / 2 + Math.sin(ang + 1.5) * len * 0.12;
        segs.push([`M${f1(x)},${f1(y)} Q${f1(mx)},${f1(my)} ${f1(x2)},${f1(y2)}`, depth, x2, y2]);
        if (depth > 0) {
          branch(x2, y2, ang - 0.42, len * 0.74, depth - 1);
          branch(x2, y2, ang + 0.38, len * 0.7, depth - 1);
        }
      };
      branch(0, 0, -Math.PI / 2, 34, 3);
      const w = (d) => 6 + d * 2.6;
      return '<g stroke-linecap="round" fill="none">'
        + segs.map(([d, dep]) => `<path d="${d}" stroke="${INK}" stroke-width="${w(dep) + 5}"/>`).join("")
        + segs.map(([d, dep]) => `<path d="${d}" stroke="${dep > 1 ? c : lighter(c, 0.2)}" stroke-width="${w(dep)}"/>`).join("")
        + segs.filter((s) => s[1] === 0).map(([, , x, y]) => `<circle cx="${f1(x)}" cy="${f1(y)}" r="3" fill="${lighter(c, 0.55)}"/>`).join("")
        + "</g>";
    },
    parasol(c) {
      const sc = darker(c, 0.3);
      const scales = [[-36, -102], [-22, -109], [-8, -114], [8, -114], [22, -109], [36, -102], [-29, -99], [-14, -105], [0, -108], [14, -105], [29, -99]]
        .map(([x, y]) => line(`M${x - 3},${y} q3,-3 6,0`, sc, 2)).join("");
      const bands = [-18, -32, -46, -58].map((y) => line(`M-6,${y} l2,-3 l2,3 l2,-3 l2,3`, sc, 1.4)).join("");
      return P("M-4,0 C-5,-30 -4,-70 -3,-96 L3,-96 C4,-70 5,-30 4,0 Z", STEM)
        + P("M-9,0 C-9,-8 -5,-11 0,-11 C5,-11 9,-8 9,0 Z", STEM) + bands
        + P("M-4,-75 C-13,-71 -12,-66 -6,-66 L6,-66 C12,-66 13,-71 4,-75 Z", STEM)
        + P("M-52,-96 Q0,-90 52,-96 Q0,-102 -52,-96 Z", darker(STEM, 0.2))
        + P("M-54,-96 C-40,-112 -18,-120 -8,-122 C-6,-131 6,-131 8,-122 C18,-120 40,-112 54,-96 Q0,-90 -54,-96 Z", mix(c, STEM, 0.55))
        + P("M-10,-121 C-8,-132 8,-132 10,-121 C4,-118 -4,-118 -10,-121 Z", c)
        + scales + HL("M-42,-103 C-30,-112 -18,-117 -10,-118 C-20,-113 -30,-108 -36,-101 Z");
    },
    "glowing-bonnets"(c) {
      const bells = [[-20, 44, -14], [-8, 66, -5], [4, 54, 4], [15, 76, 8], [25, 38, 18]];
      let s = `<ellipse cx="2" cy="-50" rx="40" ry="38" fill="${c}" opacity=".45" filter="url(#halo)"/>`;
      for (const [x, h, bend] of bells) {
        const tx = x + bend * 0.4;
        const stem = `M0,0 C${x * 0.3},${-h * 0.3} ${x},${-h * 0.6} ${tx},${-h + 2}`;
        s += `<path d="${stem}" fill="none" stroke="${INK}" stroke-width="5" stroke-linecap="round"/>`
          + `<path d="${stem}" fill="none" stroke="${STEM}" stroke-width="2.4" stroke-linecap="round"/>`;
      }
      for (const [x, h, bend] of bells) {
        const tx = x + bend * 0.4;
        s += P(`M${tx - 8},${-h + 3} C${tx - 9},${-h - 7} ${tx - 4},${-h - 13} ${tx},${-h - 13} C${tx + 4},${-h - 13} ${tx + 9},${-h - 7} ${tx + 8},${-h + 3} Q${tx},${-h} ${tx - 8},${-h + 3} Z`, lighter(c, 0.15), 2.4)
          + `<circle cx="${tx - 3}" cy="${-h - 7}" r="2" fill="#fff" opacity=".7"/>`;
      }
      return s;
    },
  };

  const button = (c) => P("M-8,0 C-9,-6 -7,-10 -6,-12 L6,-12 C7,-10 9,-6 8,0 Z", STEM)
    + P("M-15,-10 C-17,-27 -9,-37 0,-37 C9,-37 17,-27 15,-10 Q0,-5 -15,-10 Z", c)
    + HL("M-9,-24 C-9,-30 -5,-34 -1,-34 C-5,-31 -7,-27 -7,-22 Z");

  const crystal = (c) => P("M-20,10 L-24,-4 L-12,-22 L-2,-8 L4,-30 L16,-14 L24,-20 L22,10 Z", c, 3)
    + P("M-12,-22 L-2,-8 L-6,10 M4,-30 L-2,-8 M4,-30 L8,10 M16,-14 L8,10", "none", 1.6)
    + '<path d="M-11,-18 L-4,-9 L-8,4 L-18,-3 Z" fill="#fff" opacity=".35"/>';

  /** A project's mushroom; its status is its growth (§7a). */
  function mushroom(kind, color, status) {
    if (status === "draft") return button(color);
    const body = (species[kind] || species["glowing-bonnets"])(color);
    if (status === "paused") return `<g filter="url(#paused)" opacity=".6">${body}</g>`;
    if (status === "closed") return `<g filter="url(#dried)"><g transform="rotate(-20) scale(.92,.82)">${body}</g></g>`;
    return body;
  }

  return { mushroom, crystal, button };
}

/* ---------- background recoloring: brightness mapped onto the palette's ramp ---------- */

function rampFilter(ramp) {
  const parse = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16) / 255);
  const stops = ramp.map(parse);
  const n = stops.length - 1;
  const steps = 24;
  const table = [[], [], []];
  for (let i = 0; i <= steps; i++) {
    const t = Math.pow(i / steps, 0.8) * n;
    const j = Math.min(Math.floor(t), n - 1);
    const f = t - j;
    for (let ch = 0; ch < 3; ch++) table[ch].push((stops[j][ch] + (stops[j + 1][ch] - stops[j][ch]) * f).toFixed(3));
  }
  return `<filter id="bgmap" color-interpolation-filters="sRGB">
    <feColorMatrix type="matrix" values=".2126 .7152 .0722 0 0  .2126 .7152 .0722 0 0  .2126 .7152 .0722 0 0  0 0 0 1 0"/>
    <feComponentTransfer>
      <feFuncR type="table" tableValues="${table[0].join(" ")}"/>
      <feFuncG type="table" tableValues="${table[1].join(" ")}"/>
      <feFuncB type="table" tableValues="${table[2].join(" ")}"/>
    </feComponentTransfer></filter>`;
}

const DEFS = `
  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="softglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
  <filter id="halo" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="10"/></filter>
  <filter id="paused"><feColorMatrix type="saturate" values=".2"/></filter>
  <filter id="dried"><feColorMatrix type="matrix" values=".45 .45 .15 0 0  .34 .38 .12 0 0  .2 .22 .1 0 0  0 0 0 1 0"/></filter>`;

/* ---------- the scene ---------- */

function cloud(r, seed, color) {
  const rand = seededRandom(seed);
  let dots = "";
  const n = Math.round(10 + r * 1.6);
  for (let i = 0; i < n; i++) {
    const ang = rand() * Math.PI * 2;
    const d = Math.sqrt(rand()) * r;
    dots += `<circle cx="${f1(Math.cos(ang) * d)}" cy="${f1(Math.sin(ang) * d)}" r="${f1(0.9 + rand() * 1.7)}" fill="${color}"/>`;
  }
  return dots;
}

function hyphaPath(a, b, seed, soil) {
  const rand = seededRandom(seed);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;
  const w1 = (rand() - 0.5) * len * 0.45;
  const w2 = (rand() - 0.5) * len * 0.45;
  const c1 = { x: a.x + dx * 0.33 + nx * w1, y: Math.max(soil + 8, a.y + dy * 0.33 + ny * w1) };
  const c2 = { x: a.x + dx * 0.66 + nx * w2, y: Math.max(soil + 8, a.y + dy * 0.66 + ny * w2) };
  const d = `M${f1(a.x)},${f1(a.y)} C${f1(c1.x)},${f1(c1.y)} ${f1(c2.x)},${f1(c2.y)} ${f1(b.x)},${f1(b.y)}`;
  const twigs = [];
  for (let i = 0; i < 2; i++) {
    const t = 0.25 + rand() * 0.5;
    const u = 1 - t;
    const px = u * u * u * a.x + 3 * u * u * t * c1.x + 3 * u * t * t * c2.x + t * t * t * b.x;
    const py = u * u * u * a.y + 3 * u * u * t * c1.y + 3 * u * t * t * c2.y + t * t * t * b.y;
    const ang = Math.atan2(dy, dx) + (rand() < 0.5 ? -1 : 1) * (0.6 + rand() * 0.8);
    const L = 14 + rand() * 22;
    const ex = px + Math.cos(ang) * L;
    const ey = Math.max(soil + 12, py + Math.sin(ang) * L);
    twigs.push(`M${f1(px)},${f1(py)} Q${f1((px + ex) / 2 + (rand() - 0.5) * 10)},${f1((py + ey) / 2)} ${f1(ex)},${f1(ey)}`);
  }
  return { d, twigs };
}

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
