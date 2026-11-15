// The owner dresses a project or a source (§7c): on its own page, clicking its mushroom
// or mineral opens this panel. A mushroom has a species and a size; a drawn one may
// also take one of the palette's eight colors (by place, so it follows the palette;
// pictures take the painting's colors); a mineral a type and a color. The choice is
// saved in Micelio's data folder (never in the notes) through POST /api/looks/<slug>,
// and the graph draws it at once.
import { MINERALS, SPECIES, mushroomPicture, tr } from "./draw.js";

function html(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) node.setAttribute(k, String(v));
  if (text) node.textContent = text;
  return node;
}

/** The owner's key for saving looks, or "" for a visitor. */
export function lookKey() {
  const meta = document.querySelector('meta[name="micelio-looks"]');
  return meta ? meta.content : "";
}

/** Open the panel for ``node`` inside ``host``. ``now`` is how it looks now (with its
 * defaults filled in); ``draw(look)`` shows a look; resolves nothing. */
export function openLookPanel(host, node, now, strings, draw) {
  host.querySelector(".look-editor")?.remove();
  const project = node.type === "project";
  const panel = html("div", { class: "look-editor graph-panel glass", role: "dialog", "aria-label": tr(strings, project ? "graph.dress_project" : "graph.dress_source") });
  panel.appendChild(html("h2", { class: "menu-heading" }, tr(strings, project ? "graph.dress_project" : "graph.dress_source")));
  const look = { ...(node.look || {}) };
  const status = html("p", { class: "muted small", "aria-live": "polite" });
  let timer = null;
  const save = () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      try {
        const r = await fetch(`/api/looks/${encodeURIComponent(node.id)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Micelio-Form": lookKey() },
          body: JSON.stringify(look),
        });
        if (!r.ok) throw new Error(String(r.status));
        const body = await r.json();
        node.look = Object.keys(body.look).length ? body.look : null;
        status.textContent = tr(strings, "graph.dress_saved");
      } catch {
        status.textContent = tr(strings, "graph.dress_failed");
      }
    }, 350);
  };
  const changed = () => {
    draw(Object.keys(look).length ? { ...look } : null);
    save();
  };
  let colorInput = null;
  const select = (key, options, value, names) => {
    const row = html("label", { class: "look-range" });
    row.appendChild(html("span", {}, tr(strings, `graph.dress_${key === "species" ? "species" : "mineral"}`)));
    const input = html("select", { name: `look-${key}` });
    for (const option of options) {
      const o = html("option", { value: option }, tr(strings, `${names}.${option}`));
      if (option === value) o.selected = true;
      input.appendChild(o);
    }
    input.addEventListener("change", () => {
      look[key] = input.value;
      // A mineral without a chosen color takes its own: the picker follows.
      if (key === "mineral" && !look.color && colorInput) colorInput.value = MINERALS[input.value] || colorInput.value;
      changed();
    });
    row.appendChild(input);
    panel.appendChild(row);
    return input;
  };
  /** The species as pictures to pick from, when mushrooms are illustrated (§7b). */
  const gallery = () => {
    const group = html("div", { class: "look-species", role: "radiogroup", "aria-label": tr(strings, "graph.dress_species") });
    panel.appendChild(html("span", { class: "look-species-head" }, tr(strings, "graph.dress_species")));
    let chosen = null;
    for (const option of SPECIES) {
      const name = tr(strings, `species.${option}`);
      const button = html("button", { type: "button", class: "look-specimen", role: "radio", "aria-checked": option === now.species ? "true" : "false", title: name, "aria-label": name });
      button.appendChild(html("img", { src: mushroomPicture(option), alt: "", width: 44, height: 44, loading: "lazy" }));
      button.addEventListener("click", () => {
        for (const other of group.children) other.setAttribute("aria-checked", other === button ? "true" : "false");
        look.species = option;
        changed();
      });
      if (option === now.species) chosen = button;
      group.appendChild(button);
    }
    panel.appendChild(group);
    return chosen || group.firstElementChild;
  };
  const kind = project
    ? (mushroomPicture(now.species) ? gallery() : select("species", SPECIES, now.species, "species"))
    : select("mineral", Object.keys(MINERALS), now.mineral, "mineral");

  if (!project) {
    const colorRow = html("label", { class: "look-range look-color" });
    colorRow.appendChild(html("span", {}, tr(strings, "graph.dress_color")));
    const color = html("input", { type: "color", name: "look-color", value: now.color });
    color.addEventListener("input", () => { look.color = color.value; draw({ ...look }); });
    color.addEventListener("change", () => { look.color = color.value; changed(); });
    colorInput = color;
    colorRow.appendChild(color);
    panel.appendChild(colorRow);
  }

  // A drawn mushroom (no pictures): one of the palette's colors, or its category's.
  if (project && !mushroomPicture(now.species) && now.slots && now.slots.some(Boolean)) {
    panel.appendChild(html("span", { class: "look-species-head" }, tr(strings, "graph.dress_color")));
    const group = html("div", { class: "look-swatches", role: "radiogroup", "aria-label": tr(strings, "graph.dress_color") });
    const pick = (button, slot) => {
      for (const other of group.children) other.setAttribute("aria-checked", other === button ? "true" : "false");
      if (slot === null) delete look.slot;
      else look.slot = slot;
      changed();
    };
    const auto = html("button", { type: "button", class: "look-swatch auto", role: "radio", "aria-checked": Number.isInteger(now.slot) ? "false" : "true", title: tr(strings, "graph.dress_auto"), "aria-label": tr(strings, "graph.dress_auto") });
    auto.addEventListener("click", () => pick(auto, null));
    group.appendChild(auto);
    now.slots.forEach((hex, slot) => {
      if (!hex) return;
      const button = html("button", { type: "button", class: "look-swatch", role: "radio", "aria-checked": now.slot === slot ? "true" : "false", "aria-label": `${tr(strings, "graph.dress_color")} ${slot + 1}`, title: hex });
      button.style.setProperty("--swatch", hex);
      button.addEventListener("click", () => pick(button, slot));
      group.appendChild(button);
    });
    panel.appendChild(group);
  }

  let size = null;
  if (project) {
    const row = html("label", { class: "look-range" });
    const head = html("span", { class: "look-range-head" });
    const out = html("output", {}, `${Math.round((now.size || 1) * 100)} %`);
    head.append(html("span", {}, tr(strings, "graph.dress_size")), out);
    size = html("input", { type: "range", name: "look-size", min: 30, max: 120, step: 5 });
    size.value = String(Math.round((now.size || 1) * 100));
    size.addEventListener("input", () => { out.textContent = `${size.value} %`; look.size = Number(size.value) / 100; draw({ ...look }); });
    size.addEventListener("change", () => { look.size = Number(size.value) / 100; changed(); });
    row.append(head, size);
    panel.appendChild(row);
  }

  const reset = html("button", { type: "button", class: "link" }, tr(strings, "graph.dress_default"));
  reset.addEventListener("click", () => {
    for (const key of Object.keys(look)) delete look[key];
    draw(null);
    save();
    panel.remove();
  });
  panel.append(reset, status);

  const close = (e) => {
    if (e && panel.contains(e.target)) return;
    panel.remove();
    document.removeEventListener("pointerdown", close, true);
  };
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  setTimeout(() => document.addEventListener("pointerdown", close, true), 0);
  host.appendChild(panel);
  kind.focus();
}
