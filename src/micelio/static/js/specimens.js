// Small mushrooms next to project names (§7c): on the project cards and in lists. Each
// placeholder says its species and status; its color is the category's, from theme.css.
import { DEFS, el, f1, fragment, mix, painter, paletteFromCss, rampFilter, seededRandom, shade } from "./draw.js";
import { load } from "./graph-settings.js";

const pal = paletteFromCss();
const paint = painter(pal);
const backdrop = document.getElementById("backdrop");
const image = backdrop && backdrop.querySelector("image");
const soil = Math.round((1024 * Number(backdrop ? backdrop.dataset.soil : 52)) / 100);
const ramp = backdrop && backdrop.dataset.ramp ? backdrop.dataset.ramp.split(" ") : null;
// The threads' color a viewer chose in a graph's ⚙ (kept in this browser), else the theme's.
const threadColor = load().threadColor || pal.thread;

function colorOf(node) {
  if (/^#[0-9a-f]{6}$/i.test(node.dataset.color || "")) return node.dataset.color;
  const value = getComputedStyle(node).getPropertyValue("--cat").trim();
  const base = /^#[0-9a-f]{6}$/i.test(value) ? value : mix(pal.thread, pal.ink, 0.45);
  return node.dataset.id ? shade(node.dataset.id, base, pal) : base;
}

/** Each moving part's delay (and a spore's drift) as CSS variables, set through the DOM:
 * the Content Security Policy does not let markup carry style attributes. */
function beats(svg) {
  for (const node of svg.querySelectorAll("[data-d]")) {
    node.style.setProperty("--d", `${node.dataset.d}s`);
    if (node.dataset.dx) node.style.setProperty("--dx", `${node.dataset.dx}px`);
  }
  return svg;
}

document.querySelectorAll("[data-mushroom]").forEach((slot, i) => {
  const color = colorOf(slot);
  const body = paint.mushroom(slot.dataset.species || "glowing-bonnets", color, slot.dataset.status || "active");
  if (slot.dataset.scene !== "card" || !image) {
    slot.replaceChildren(beats(el("svg", { viewBox: "-34 -78 68 82", "aria-hidden": "true", focusable: "false" },
      el("defs", {}, DEFS), `<g transform="scale(.6)"><g class="sway" data-d="-${f1((i * 1.7) % 5)}">${body}</g></g>`)));
    return;
  }
  // A strip of the painting around the soil line, a different stretch for each card.
  const x = 260 + ((i * 197) % 1000);
  const rand = seededRandom(slot.dataset.seed || String(i));
  // Each card moves on its own beat: the mushroom sways, its threads grow in and their
  // tips glow, and now and then spores rise from the cap. CSS stops it all for reduced motion.
  const beat = (i * 1.3) % 5;
  let threads = "";
  const notes = Math.min(8, Number(slot.dataset.notes || 0));
  for (let j = 0; j < notes; j++) {
    const tx = x + (rand() - 0.5) * 200;
    const ty = soil + 30 + rand() * 45;
    const c1x = x + (tx - x) * 0.3 + (rand() - 0.5) * 30;
    const d = f1(0.2 + j * 0.15);
    threads += `<path class="hypha" pathLength="1" d="M${x},${soil + 4} Q${f1(c1x)},${f1(soil + 40)} ${f1(tx)},${f1(ty)}" stroke="${threadColor}" stroke-width="1.4" data-d="${d}"/>`;
    threads += `<circle class="tip" cx="${f1(tx)}" cy="${f1(ty)}" r="2.6" fill="${threadColor}" data-d="${f1(1.6 + j * 0.15)}"/>`;
  }
  let spores = "";
  for (let j = 0; j < 3; j++) {
    const sx = x + (rand() - 0.5) * 30;
    spores += `<circle class="puff" cx="${f1(sx)}" cy="${f1(soil - 62 - rand() * 10)}" r="${f1(1.6 + rand() * 1.2)}" fill="${color}" data-d="-${f1(beat + j * 1.5)}" data-dx="${f1((rand() - 0.5) * 30)}"/>`;
  }
  const svg = el("svg", { viewBox: `${x - 150} ${soil - 135} 300 210`, preserveAspectRatio: "xMidYMid slice", "aria-hidden": "true", focusable: "false" },
    el("defs", {}, DEFS + (ramp ? rampFilter(ramp) : "")),
    el("image", { href: image.getAttribute("href"), x: 0, y: 0, width: 1536, height: 1024, preserveAspectRatio: "xMidYMid slice", filter: ramp ? "url(#bgmap)" : null }));
  svg.appendChild(fragment(`<g filter="url(#glow)">${threads}</g><g transform="translate(${x},${soil + 4}) scale(.95)"><g class="sway" data-d="-${f1(beat)}">${body}</g></g><g filter="url(#glow)">${spores}</g>`));
  slot.replaceChildren(beats(svg));
});
