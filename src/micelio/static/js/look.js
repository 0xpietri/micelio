// The visitor's appearance panel (§7b): palette, fonts and sizes kept in this browser's
// localStorage only. It never posts anything; the site stays the same for everyone else.
// look-early.js applies the saved look before the page paints; this wires the panel.

const KEY = "micelio.look.v1";
const FIELDS = ["title_font", "text_font", "title_effect", "title_size", "text_size", "graph_labels"];

function read() {
  try {
    const look = JSON.parse(localStorage.getItem(KEY) || "null");
    return look && typeof look === "object" ? look : {};
  } catch {
    return {};
  }
}

function write(look) {
  try {
    if (Object.keys(look).length) localStorage.setItem(KEY, JSON.stringify(look));
    else localStorage.removeItem(KEY);
  } catch {
    // a private window may refuse: the choice lasts until the page closes
  }
}

function applyType(look) {
  const style = document.documentElement.style;
  const set = (name, value) => (value === null ? style.removeProperty(name) : style.setProperty(name, value));
  set("--title-font", look.title_font ? `var(--font-${look.title_font})` : null);
  set("--text-font", look.text_font ? `var(--font-${look.text_font})` : null);
  set("--title-scale", look.title_size ? String(look.title_size / 100) : null);
  set("--text-size", look.text_size ? `${look.text_size}px` : null);
  set("--label-scale", look.graph_labels ? String(look.graph_labels / 100) : null);
  if (look.title_effect) {
    const poster = look.title_effect === "poster";
    set("--title-stroke", poster ? "0.08em" : "0");
    set("--title-shadow", poster ? "0.05em 0.06em 0 var(--pal-accent)" : "none");
  } else {
    set("--title-stroke", null);
    set("--title-shadow", null);
  }
}

function wire(panel) {
  const owner = panel.dataset;
  const ownerValue = (name) => owner[name.replace(/_(\w)/g, (_, c) => c.toUpperCase())];
  let look = read();
  const field = (name) => panel.querySelector(`[name="look-${name}"]`);

  const show = () => {
    const palette = look.palette || owner.palette;
    for (const radio of panel.querySelectorAll('input[name="look-palette"]')) radio.checked = radio.value === palette;
    for (const name of FIELDS) {
      const input = field(name);
      if (!input) continue;
      input.value = String(look[name] ?? ownerValue(name));
      const out = input.closest("label").querySelector("output");
      if (out) out.textContent = `${input.value} ${out.dataset.unit}`;
    }
  };

  panel.addEventListener("input", (e) => {
    const name = e.target.name.replace(/^look-/, "");
    if (!FIELDS.includes(name)) return;
    const raw = e.target.value;
    const value = e.target.type === "range" ? Number(raw) : raw;
    if (String(value) === String(ownerValue(name))) delete look[name];
    else look[name] = value;
    write(look);
    applyType(look);
    show();
  });
  panel.addEventListener("change", (e) => {
    if (e.target.name !== "look-palette") return;
    const value = e.target.value;
    if (value === owner.palette) {
      delete look.palette;
      delete look.ramp;
    } else {
      look.palette = value;
      look.ramp = e.target.dataset.ramp || "";
    }
    write(look);
    // Colors reach the theme, the background and the drawings: the page draws again.
    location.reload();
  });
  panel.querySelector(".look-reset").addEventListener("click", () => {
    const repaint = Boolean(look.palette);
    look = {};
    write(look);
    if (repaint) location.reload();
    applyType(look);
    show();
  });
  show();
}

for (const panel of document.querySelectorAll(".look-panel")) wire(panel);
