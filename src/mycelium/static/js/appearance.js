// The Appearance page (§7b): the soil value next to its slider and the prompt builder.
// Without JavaScript the page still works; the prompt then shows the defaults.

async function loadStrings() {
  const lang = document.documentElement.lang || "en";
  try {
    const r = await fetch(`/static/locales/${encodeURIComponent(lang)}.json`);
    return r.ok ? await r.json() : {};
  } catch {
    return {};
  }
}

function fill(text, values) {
  return text.replace(/\{(\w+)\}/g, (all, name) => (name in values ? String(values[name]).trim().replace(/\.$/, "") : all));
}

/** Fonts and sizes show on the page as soon as they change, before saving (§7b). */
function livePreview() {
  const form = document.getElementById("look-form");
  if (!form) return;
  const root = document.documentElement.style;
  const preview = document.getElementById("toml-preview");
  const value = (name) => {
    const field = form.querySelector(`[name="${name}"]:checked`) || form.querySelector(`[name="${name}"]`);
    return field ? field.value : "";
  };
  const apply = () => {
    root.setProperty("--title-font", `var(--font-${value("title_font")})`);
    root.setProperty("--text-font", `var(--font-${value("text_font")})`);
    root.setProperty("--title-scale", String(Number(value("title_size")) / 100));
    root.setProperty("--text-size", `${value("text_size")}px`);
    root.setProperty("--label-scale", String(Number(value("graph_labels")) / 100));
    const poster = value("title_effect") === "poster";
    root.setProperty("--title-stroke", poster ? "0.08em" : "0");
    root.setProperty("--title-shadow", poster ? "0.05em 0.06em 0 var(--pal-accent)" : "none");
    for (const range of form.querySelectorAll('input[type="range"][data-unit]')) {
      const out = document.getElementById(`${range.id}-value`);
      if (out) out.textContent = `${range.value} ${range.dataset.unit}`;
    }
    const name = form.querySelector('[name="site_name"]');
    const shown = (name && name.value.trim()) || (name && name.placeholder) || "";
    for (const sample of form.querySelectorAll(".title-sample")) sample.textContent = shown;
    const brand = document.querySelector(".brand");
    if (brand && shown) brand.textContent = shown;
    if (preview) {
      preview.textContent = [
        "[typography]",
        `title_font = "${value("title_font")}"`,
        `text_font = "${value("text_font")}"`,
        `title_size = ${value("title_size")}`,
        `text_size = ${value("text_size")}`,
        `graph_labels = ${value("graph_labels")}`,
        `title_effect = "${value("title_effect")}"`,
      ].join("\n");
    }
  };
  form.addEventListener("input", apply);
  form.addEventListener("change", apply);
}

async function start() {
  livePreview();
  const strings = await loadStrings();
  const soil = document.getElementById("soil");
  const soilValue = document.getElementById("soil-value");
  const section = document.getElementById("prompt");
  const output = document.getElementById("prompt-output");
  const fixed = document.getElementById("prompt-fixed");
  const status = document.getElementById("prompt-status");
  const copy = document.getElementById("prompt-copy");
  if (!section || !output) return;
  const fields = [...section.querySelectorAll("textarea[data-field]")];
  const colors = fields.find((f) => f.dataset.field === "colors");
  let colorsEdited = false;

  const update = () => {
    const level = Number(soil ? soil.value : section.dataset.soil);
    const values = { soil: level, rest: 100 - level };
    for (const f of fields) values[f.dataset.field] = f.value;
    if (strings["prompt.template"]) output.value = fill(strings["prompt.template"], values);
    if (strings["prompt.fixed"]) fixed.textContent = fill(strings["prompt.fixed"], { soil: level });
    if (soilValue) soilValue.textContent = `${level}%`;
  };

  for (const f of fields) {
    f.addEventListener("input", () => {
      if (f === colors) colorsEdited = true;
      update();
    });
  }
  if (soil) soil.addEventListener("input", update);
  for (const radio of document.querySelectorAll('input[name="palette"]')) {
    radio.addEventListener("change", () => {
      if (colors && !colorsEdited) {
        colors.value = radio.dataset.swatch;
        update();
      }
    });
  }
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(output.value);
      status.textContent = strings["prompt.copied"] || "";
    } catch {
      output.focus();
      output.select();
      status.textContent = strings["prompt.copy_failed"] || "";
    }
    setTimeout(() => { status.textContent = ""; }, 2500);
  });
  update();
}

start();
