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

async function start() {
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
