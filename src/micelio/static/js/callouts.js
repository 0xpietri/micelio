// The sign that closes a concept (`> [!takeaway]`) has no fixed border: colored hyphae
// wrap it and sprout outwards, in the theme's colors (they redraw when the palette or
// the box's size changes). Numbers and palette colors only enter the markup.
import { el, f1, paletteFromCss, seededRandom } from "./draw.js";

const PAD = 34; // room around the box for the hyphae that sprout out
const SHAPE = 8; // superellipse exponent: a rectangle with soft corners

function colors() {
  const pal = paletteFromCss();
  return [pal.sun, pal.accent, pal.crystals[0], pal.crystals[1], pal.spore];
}

/** A point on the box's soft outline at angle ``t``, and its outward normal. */
function outline(t, w, h, grow = 0) {
  const a = w / 2 + grow;
  const b = h / 2 + grow;
  const c = Math.cos(t);
  const s = Math.sin(t);
  const x = Math.sign(c) * Math.abs(c) ** (2 / SHAPE) * a;
  const y = Math.sign(s) * Math.abs(s) ** (2 / SHAPE) * b;
  let nx = (Math.sign(x) * Math.abs(x / a) ** (SHAPE - 1)) / a;
  let ny = (Math.sign(y) * Math.abs(y / b) ** (SHAPE - 1)) / b;
  const len = Math.hypot(nx, ny) || 1;
  nx /= len;
  ny /= len;
  return { x: x + w / 2 + PAD, y: y + h / 2 + PAD, nx, ny };
}

/** One hypha running part of the way round the box, braided with the others. */
function strand(w, h, rand) {
  const phase = [rand() * 6.3, rand() * 6.3, rand() * 6.3];
  const amp = 3 + rand() * 6;
  const start = rand() * Math.PI * 2;
  const span = Math.PI * (0.7 + rand() * 1.4);
  const steps = Math.round(60 + span * 18);
  let d = "";
  for (let i = 0; i <= steps; i++) {
    const t = start + (i / steps) * span;
    const wobble =
      Math.sin(t * 2 + phase[0]) * amp + Math.sin(t * 5 + phase[1]) * amp * 0.6 +
      Math.sin(t * 11 + phase[2]) * amp * 0.3 - amp * 0.3;
    const p = outline(t, w, h, wobble);
    d += `${i ? "L" : "M"}${f1(p.x)},${f1(p.y)}`;
  }
  return d;
}

function sprout(w, h, rand) {
  const t = rand() * Math.PI * 2;
  const p = outline(t, w, h, (rand() - 0.3) * 4);
  const len = 10 + rand() * (PAD - 8);
  const bend = (rand() - 0.5) * 1.1;
  const ang = Math.atan2(p.ny, p.nx) + bend;
  const ex = p.x + Math.cos(ang) * len;
  const ey = p.y + Math.sin(ang) * len;
  const cx = p.x + p.nx * len * 0.5 + (rand() - 0.5) * 10;
  const cy = p.y + p.ny * len * 0.5 + (rand() - 0.5) * 10;
  let d = `M${f1(p.x)},${f1(p.y)} Q${f1(cx)},${f1(cy)} ${f1(ex)},${f1(ey)}`;
  if (rand() < 0.6) {
    // a fork two thirds of the way out
    const fx = (p.x + cx * 2 + ex * 0) / 3;
    const fy = (p.y + cy * 2 + ey * 0) / 3;
    const fa = ang + (rand() < 0.5 ? -1 : 1) * (0.5 + rand() * 0.6);
    const fl = len * (0.3 + rand() * 0.3);
    d += ` M${f1(fx)},${f1(fy)} L${f1(fx + Math.cos(fa) * fl)},${f1(fy + Math.sin(fa) * fl)}`;
  }
  return { d, tip: { x: ex, y: ey } };
}

function draw(box, index) {
  const old = box.querySelector(":scope > svg.takeaway-threads");
  if (old) old.remove();
  const w = box.offsetWidth;
  const h = box.offsetHeight;
  if (!w || !h) return;
  const rand = seededRandom(`takeaway-${index}-${box.textContent.length}`);
  const palette = colors();
  const svg = el("svg", {
    class: "takeaway-threads",
    width: w + PAD * 2,
    height: h + PAD * 2,
    viewBox: `0 0 ${w + PAD * 2} ${h + PAD * 2}`,
    "aria-hidden": "true",
    focusable: "false",
  });
  for (let i = 0; i < 11; i++) {
    svg.appendChild(
      el("path", {
        d: strand(w, h, rand),
        fill: "none",
        stroke: palette[i % palette.length],
        "stroke-width": f1(0.5 + rand() * 1.5),
        "stroke-opacity": f1(0.35 + rand() * 0.55),
        "stroke-linecap": "round",
      }),
    );
  }
  const count = Math.round((w + h) / 9);
  for (let i = 0; i < count; i++) {
    const color = palette[Math.floor(rand() * palette.length)];
    const { d, tip } = sprout(w, h, rand);
    svg.appendChild(
      el("path", {
        d,
        fill: "none",
        stroke: color,
        "stroke-width": f1(0.6 + rand() * 0.9),
        "stroke-opacity": f1(0.4 + rand() * 0.5),
        "stroke-linecap": "round",
      }),
    );
    if (rand() < 0.35) {
      svg.appendChild(el("circle", { cx: f1(tip.x), cy: f1(tip.y), r: f1(1 + rand() * 1.4), fill: color, "fill-opacity": "0.85" }));
    }
  }
  box.prepend(svg);
}

const boxes = [...document.querySelectorAll(".callout-takeaway")];
if (boxes.length) {
  const redraw = () => boxes.forEach(draw);
  redraw();
  if ("ResizeObserver" in window) {
    let last = new Map();
    const watch = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const box = entry.target;
        const size = `${box.offsetWidth}x${box.offsetHeight}`;
        if (last.get(box) !== size) {
          last.set(box, size);
          draw(box, boxes.indexOf(box));
        }
      }
    });
    boxes.forEach((box) => watch.observe(box));
  }
  // A visitor's palette (look.js) or the Appearance page can change the colors.
  new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ["style", "class", "data-palette"] });
}
