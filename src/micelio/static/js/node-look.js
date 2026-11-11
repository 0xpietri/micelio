// The owner dresses a project or a source (§7c): on its own page, clicking its mushroom
// or mineral opens this panel. The choice is saved in Micelio's data folder (never in
// the notes) through POST /api/looks/<slug>, and the graph draws it at once.
import { MINERALS, tr } from "./draw.js";

const SPECIES = ["fly-agaric", "shaggy-inkcap", "morel", "chanterelle", "liberty-caps", "coral", "parasol", "glowing-bonnets"];

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
  const kind = project
    ? select("species", SPECIES, now.species, "species")
    : select("mineral", Object.keys(MINERALS), now.mineral, "mineral");

  const colorRow = html("label", { class: "look-range look-color" });
  colorRow.appendChild(html("span", {}, tr(strings, "graph.dress_color")));
  const color = html("input", { type: "color", name: "look-color", value: now.color });
  color.addEventListener("input", () => { look.color = color.value; draw({ ...look }); });
  color.addEventListener("change", () => { look.color = color.value; changed(); });
  colorInput = color;
  colorRow.appendChild(color);
  panel.appendChild(colorRow);

  let size = null;
  if (project) {
    const row = html("label", { class: "look-range" });
    const head = html("span", { class: "look-range-head" });
    const out = html("output", {}, `${Math.round((now.size || 1) * 100)} %`);
    head.append(html("span", {}, tr(strings, "graph.dress_size")), out);
    size = html("input", { type: "range", name: "look-size", min: 60, max: 160, step: 5 });
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
