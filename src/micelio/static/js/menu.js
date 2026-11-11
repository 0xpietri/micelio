// The ⚙ menu in the header's corner (§7c): the viewer's graph settings (on pages with a
// graph) and the look. Graph settings live in this browser (graph-settings.js); every
// graph on the page hears a change and draws again.
import { loadStrings, tr } from "./draw.js";
import { LIMITS, defaults, load, save } from "./graph-settings.js";

function html(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) node.setAttribute(k, String(v));
  if (text) node.textContent = text;
  return node;
}

function graphSection(section, strings) {
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
    tell("reset");
  });
  section.appendChild(reset);
  section.hidden = false;
}

async function start() {
  for (const corner of document.querySelectorAll(".menu-corner")) {
    const toggle = corner.querySelector(".menu-toggle");
    const panel = corner.querySelector(".menu-panel");
    const open = (yes) => {
      panel.hidden = !yes;
      toggle.setAttribute("aria-expanded", String(yes));
      if (yes) {
        const first = panel.querySelector("input, select, a");
        if (first) first.focus();
      }
    };
    toggle.addEventListener("click", () => open(panel.hidden));
    panel.addEventListener("keydown", (e) => { if (e.key === "Escape") { open(false); toggle.focus(); } });
    document.addEventListener("pointerdown", (e) => {
      if (!panel.hidden && !corner.contains(e.target)) open(false);
    });
  }
  // The language menu closes like the ⚙ one.
  document.addEventListener("pointerdown", (e) => {
    for (const d of document.querySelectorAll("details.lang-menu[open]")) if (!d.contains(e.target)) d.open = false;
  });
  const section = document.querySelector(".menu-graph");
  if (section && document.querySelector("[data-graph]")) graphSection(section, await loadStrings());
}

start();
