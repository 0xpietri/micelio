// Small mushrooms next to project names (§7c): on the project cards and in lists. Each
// placeholder says its species and status; its color is the category's, from theme.css.
import { DEFS, el, f1, fragment, mix, painter, paletteFromCss, rampFilter, seededRandom } from "./draw.js";

const pal = paletteFromCss();
const paint = painter(pal);
const backdrop = document.getElementById("backdrop");
const image = backdrop && backdrop.querySelector("image");
const soil = Math.round((1024 * Number(backdrop ? backdrop.dataset.soil : 52)) / 100);
const ramp = backdrop && backdrop.dataset.ramp ? backdrop.dataset.ramp.split(" ") : null;

function colorOf(node) {
  const value = getComputedStyle(node).getPropertyValue("--cat").trim();
  return /^#[0-9a-f]{6}$/i.test(value) ? value : mix(pal.thread, pal.ink, 0.45);
}

document.querySelectorAll("[data-mushroom]").forEach((slot, i) => {
  const color = colorOf(slot);
  const body = paint.mushroom(slot.dataset.species || "glowing-bonnets", color, slot.dataset.status || "active");
  if (slot.dataset.scene !== "card" || !image) {
    slot.replaceChildren(el("svg", { viewBox: "-34 -78 68 82", "aria-hidden": "true", focusable: "false" },
      el("defs", {}, DEFS), `<g transform="scale(.6)">${body}</g>`));
    return;
  }
  // A strip of the painting around the soil line, a different stretch for each card.
  const x = 260 + ((i * 197) % 1000);
  const rand = seededRandom(slot.dataset.seed || String(i));
  let threads = "";
  const notes = Math.min(8, Number(slot.dataset.notes || 0));
  for (let j = 0; j < notes; j++) {
    const tx = x + (rand() - 0.5) * 200;
    const ty = soil + 30 + rand() * 45;
    const c1x = x + (tx - x) * 0.3 + (rand() - 0.5) * 30;
    threads += `<path class="hypha" d="M${x},${soil + 4} Q${f1(c1x)},${f1(soil + 40)} ${f1(tx)},${f1(ty)}" stroke-width="1.4"/>`;
    threads += `<circle cx="${f1(tx)}" cy="${f1(ty)}" r="2.6" fill="${pal.thread}"/>`;
  }
  const svg = el("svg", { viewBox: `${x - 150} ${soil - 135} 300 210`, preserveAspectRatio: "xMidYMid slice", "aria-hidden": "true", focusable: "false" },
    el("defs", {}, DEFS + (ramp ? rampFilter(ramp) : "")),
    el("image", { href: image.getAttribute("href"), x: 0, y: 0, width: 1536, height: 1024, preserveAspectRatio: "xMidYMid slice", filter: ramp ? "url(#bgmap)" : null }));
  svg.appendChild(fragment(`<g filter="url(#glow)">${threads}</g><g transform="translate(${x},${soil + 4}) scale(.95)"><g class="sway">${body}</g></g>`));
  slot.replaceChildren(svg);
});
