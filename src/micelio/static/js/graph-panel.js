// The ⚙ panel in a graph's corner (§7): the viewer's graph settings, kept in this browser
// (graph-settings.js). A change is told to every graph on the page, which draws again.
import { tr } from "./draw.js";
import { LIMITS, defaults, load, save } from "./graph-settings.js";

function html(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) node.setAttribute(k, String(v));
  if (text) node.textContent = text;
  return node;
}

/** Fill ``section`` with the settings' controls. */
export function graphSection(section, strings) {
  const settings = load();
  const tell = (key) => window.dispatchEvent(new CustomEvent("micelio:graph-settings", { detail: { key } }));
  const inputs = {};
  const outputs = {};
  const shown = (key, value) => (key === "length" ? tr(strings, "graph.chars", { count: value }) : `${value} %`);
  const set = (key, value) => {
    if (settings[key] === value) return;
    settings[key] = value;
    save({ ...load(), [key]: value });
    inputs.length.disabled = !settings.shorten;
    tell(key);
  };
  section.appendChild(html("h2", { class: "menu-heading" }, tr(strings, "graph.settings")));
  const range = (key) => {
    const [min, max, step] = LIMITS[key];
    const row = html("label", { class: "look-range" });
    const head = html("span", { class: "look-range-head" });
    head.appendChild(html("span", {}, tr(strings, `graph.${key}`)));
    const out = html("output", {}, shown(key, settings[key]));
    head.appendChild(out);
    const input = html("input", { type: "range", min, max, step, name: `graph-${key}` });
    input.value = String(settings[key]);
    // Spacing lays the graph out again, so it waits for the slider to be let go.
    input.addEventListener("input", () => {
      out.textContent = shown(key, Number(input.value));
      if (key !== "spacing") set(key, Number(input.value));
    });
    input.addEventListener("change", () => set(key, Number(input.value)));
    row.append(head, input);
    section.appendChild(row);
    inputs[key] = input;
    outputs[key] = out;
  };
  range("spacing");
  range("labels");
  const check = html("label", { class: "menu-check" });
  const box = html("input", { type: "checkbox", name: "graph-shorten" });
  box.checked = settings.shorten;
  box.addEventListener("change", () => set("shorten", box.checked));
  check.append(box, document.createTextNode(` ${tr(strings, "graph.shorten")}`));
  section.appendChild(check);
  range("length");
  inputs.length.disabled = !settings.shorten;
  const threads = threadSection(settings, strings, (color, from) => {
    settings.threadColor = color;
    settings.threadFrom = from;
    save({ ...load(), threadColor: color, threadFrom: from });
    tell("threads");
  });
  section.appendChild(threads.node);
  section.appendChild(html("p", { class: "muted small" }, tr(strings, "graph.settings_note")));
  const reset = html("button", { type: "button", class: "link" }, tr(strings, "graph.reset"));
  reset.addEventListener("click", () => {
    const fresh = { ...defaults(), zoom: load().zoom };
    save(fresh);
    Object.assign(settings, fresh);
    for (const key of Object.keys(LIMITS)) {
      inputs[key].value = String(fresh[key]);
      outputs[key].textContent = shown(key, fresh[key]);
    }
    box.checked = fresh.shorten;
    inputs.length.disabled = !fresh.shorten;
    threads.show();
    tell("reset");
  });
  section.appendChild(reset);
}

let palettes = null;

/** The themes' palettes, asked once per page (names and colors, the same for everyone). */
function loadPalettes() {
  if (!palettes) {
    palettes = fetch("/api/palettes", { credentials: "same-origin" })
      .then((r) => (r.ok ? r.json() : []))
      .catch(() => []);
  }
  return palettes;
}

/** The threads' color: the theme's, or one picked from a theme's palette, or any color
 * ("Custom"). ``choose(color, from)`` gets "" and "" to follow the theme again. */
function threadSection(settings, strings, choose) {
  const node = html("div", { class: "thread-color" });
  const head = html("div", { class: "thread-color-head" });
  head.appendChild(html("span", {}, tr(strings, "graph.threads")));
  const now = html("span", { class: "thread-color-now" });
  const chip = html("span", { class: "thread-chip", "aria-hidden": "true" });
  const name = html("span", { class: "muted small" });
  now.append(chip, name);
  head.appendChild(now);
  const toggle = html("button", { type: "button", class: "link", "aria-expanded": "false" }, tr(strings, "graph.threads_change"));
  const picker = html("div", { class: "thread-picker" });
  picker.hidden = true;
  node.append(head, toggle, picker);

  let names = {};
  const show = () => {
    const color = settings.threadColor;
    chip.classList.toggle("theme", !color);
    chip.style.background = color || "";
    name.textContent = !color ? tr(strings, "graph.threads_theme")
      : settings.threadFrom === "custom" ? tr(strings, "graph.threads_custom")
        : names[settings.threadFrom] || settings.threadFrom;
    for (const b of picker.querySelectorAll("[data-color]")) {
      b.setAttribute("aria-pressed", String(b.dataset.color === color && b.dataset.from === settings.threadFrom));
    }
    const custom = picker.querySelector("input[type=color]");
    if (custom && color) custom.value = color;
  };
  const pick = (color, from) => { choose(color, from); show(); };

  const build = (list) => {
    names = Object.fromEntries(list.map((p) => [p.key, p.name]));
    const themeButton = html("button", { type: "button", class: "pill thread-theme", "data-color": "", "data-from": "" }, tr(strings, "graph.threads_theme"));
    themeButton.addEventListener("click", () => pick("", ""));
    picker.appendChild(themeButton);
    for (const palette of list) {
      const group = html("div", { class: "thread-palette", role: "group", "aria-label": palette.name });
      group.appendChild(html("span", { class: "thread-palette-name small" }, palette.name));
      const row = html("span", { class: "thread-swatches" });
      for (const color of palette.colors) {
        const b = html("button", { type: "button", class: "thread-swatch", "data-color": color, "data-from": palette.key, title: `${palette.name} ${color}`, "aria-label": `${palette.name} ${color}` });
        b.style.background = color;
        b.addEventListener("click", () => pick(color, palette.key));
        row.appendChild(b);
      }
      group.appendChild(row);
      picker.appendChild(group);
    }
    const custom = html("label", { class: "thread-palette thread-custom" });
    custom.appendChild(html("span", { class: "thread-palette-name small" }, tr(strings, "graph.threads_custom")));
    const input = html("input", { type: "color", name: "graph-thread-color" });
    input.value = settings.threadColor || "#ffffff";
    input.addEventListener("input", () => pick(input.value.toLowerCase(), "custom"));
    custom.appendChild(input);
    picker.appendChild(custom);
    show();
  };

  toggle.addEventListener("click", async () => {
    const open = picker.hidden;
    picker.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    if (open && !picker.childElementCount) build(await loadPalettes());
  });
  loadPalettes().then((list) => { names = Object.fromEntries(list.map((p) => [p.key, p.name])); show(); });
  show();
  return { node, show: () => { Object.assign(settings, { threadColor: load().threadColor, threadFrom: load().threadFrom }); show(); } };
}
