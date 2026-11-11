// The Appearance page (§7b): every change saves itself and repaints the page, the soil
// value next to its slider, the prompt builder, and a click outside the panel goes back.
// Without JavaScript the page still works with its Save buttons; the prompt then shows
// the defaults.
import { rampFilter } from "./draw.js";

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

/** The theme and the painted background, redrawn after a save without reloading. */
function repaint(look) {
  const theme = document.querySelector('link[rel="stylesheet"][href^="/theme.css"]');
  if (theme) {
    // Swap once the new sheet has loaded, so the page never flashes unstyled.
    const fresh = theme.cloneNode();
    fresh.href = `/theme.css?v=${Date.now()}`;
    fresh.addEventListener("load", () => theme.remove(), { once: true });
    theme.after(fresh);
  }
  const backdrop = document.getElementById("backdrop");
  if (!backdrop || !look) return;
  const image = backdrop.querySelector("image");
  if (image) image.setAttribute("href", look.url);
  backdrop.dataset.soil = String(look.soil);
  backdrop.dataset.ramp = look.ramp;
  // The reading pages' "horizon" view: the soil line near the top (see base.html).
  const top = Math.max(Math.round((1024 * look.soil) / 100) - 330, 0);
  backdrop.setAttribute("viewBox", `0 ${top} 1536 ${1024 - top}`);
  backdrop.querySelectorAll("defs").forEach((d) => d.remove());
  if (look.ramp && image) {
    const defs = new DOMParser().parseFromString(
      `<svg xmlns="http://www.w3.org/2000/svg"><defs>${rampFilter(look.ramp.split(" ")).replace('id="bgmap"', 'id="bgmap-page"')}</defs></svg>`,
      "image/svg+xml",
    ).documentElement.firstElementChild;
    backdrop.prepend(document.importNode(defs, true));
    image.setAttribute("filter", "url(#bgmap-page)");
  } else if (image) {
    image.removeAttribute("filter");
  }
}

/** Every change saves itself: no Save button. Text waits for a pause in typing. */
function autosave() {
  const form = document.querySelector("form[data-autosave]");
  if (!form) return () => Promise.resolve();
  const status = document.getElementById("autosave-status");
  for (const button of document.querySelectorAll(".save-fallback")) button.hidden = true;
  const say = (key, cls) => {
    if (!status) return;
    status.textContent = status.dataset[key] || "";
    status.className = `autosave small ${cls}`;
  };
  let timer = null;
  let running = Promise.resolve();
  const send = () => {
    clearTimeout(timer);
    timer = null;
    const body = new URLSearchParams(new FormData(form));
    say("saving", "muted");
    running = running.then(async () => {
      try {
        const r = await fetch(form.action, {
          method: "POST",
          body,
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        });
        const answer = r.ok ? await r.json() : null;
        if (!answer || !answer.ok) throw new Error(String(r.status));
        repaint(answer.backdrop);
        say("saved", "ok");
      } catch {
        say("failed", "error");
      }
    });
    return running;
  };
  const later = (ms) => {
    clearTimeout(timer);
    timer = setTimeout(send, ms);
  };
  form.addEventListener("change", (e) => (e.target.type === "text" ? later(300) : send()));
  form.addEventListener("input", (e) => { if (e.target.type === "text") later(800); });
  form.addEventListener("submit", (e) => { e.preventDefault(); send(); });

  // A chosen image uploads at once (a normal post: the page comes back with it).
  const upload = document.getElementById("upload-form");
  const file = upload && upload.querySelector('input[type="file"]');
  if (file) file.addEventListener("change", () => { if (file.files.length) upload.submit(); });

  /** Wait for any change still on its way. */
  return () => (timer ? send() : running);
}

/** A click on the painting around the panel leaves the page, where the owner came from. */
function clickOutsideLeaves(flush) {
  const panel = document.querySelector(".page.look");
  if (!panel) return;
  const hint = document.querySelector(".leave-hint");
  if (hint) hint.hidden = false;
  document.addEventListener("click", async (e) => {
    if (e.button !== 0 || e.defaultPrevented) return;
    const target = e.target;
    if (!(target instanceof Element) || panel.contains(target) || target.closest("header, a, button, input, label, summary")) return;
    if (String(window.getSelection() || "")) return;
    await flush();
    let back = "/";
    try {
      const from = new URL(document.referrer);
      if (from.origin === location.origin && !["/appearance", "/login"].includes(from.pathname)) back = from.pathname + from.search;
    } catch {
      // no referrer: the landing
    }
    location.assign(back);
  });
}

async function start() {
  livePreview();
  const flush = autosave();
  clickOutsideLeaves(flush);
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
