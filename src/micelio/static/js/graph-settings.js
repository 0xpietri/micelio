// What a viewer chooses for the graphs: spacing, title size, short titles and zoom. Kept
// in this browser's localStorage, never on the server: they are one person's view
// settings (a phone and a desktop may want different ones), visitors can keep them too,
// and nothing new is written to Micelio's data folder. The site-wide sizes stay on the
// Appearance page; these multiply them. Plain ES module with no DOM, so it can be tested.

export const STORAGE_KEY = "micelio.graph.v1";

/** Range settings: [min, max, step, default]. Percentages, characters. */
export const LIMITS = {
  spacing: [50, 250, 10, 100],
  labels: [60, 200, 10, 100],
  length: [12, 60, 2, 28],
};
export const ZOOM_MIN = 0.25;
export const ZOOM_MAX = 8;
export const MODES = ["free", "box", "forest"];

export function defaults() {
  return {
    spacing: LIMITS.spacing[3],
    labels: LIMITS.labels[3],
    shorten: true,
    length: LIMITS.length[3],
    zoom: Object.fromEntries(MODES.map((m) => [m, 1])),
  };
}

function inRange(value, [min, max, step, fallback]) {
  const n = Number(value);
  if (value === null || value === "" || typeof value === "boolean" || !Number.isFinite(n)) return fallback;
  const snapped = min + Math.round((n - min) / step) * step;
  return Math.min(max, Math.max(min, snapped));
}

function zoomOf(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0 || typeof value === "boolean") return 1;
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, n));
}

/** Any stored value, made safe: unknown keys dropped, numbers clamped, bad values reset. */
export function clean(raw) {
  const out = defaults();
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return out;
  for (const key of Object.keys(LIMITS)) out[key] = inRange(raw[key], LIMITS[key]);
  if (typeof raw.shorten === "boolean") out.shorten = raw.shorten;
  const zoom = raw.zoom && typeof raw.zoom === "object" ? raw.zoom : {};
  for (const mode of MODES) out.zoom[mode] = zoomOf(zoom[mode]);
  return out;
}

/** The saved settings, or the defaults when there are none or storage is blocked. */
export function load(storage = globalThis.localStorage) {
  try {
    const text = storage ? storage.getItem(STORAGE_KEY) : null;
    return clean(text ? JSON.parse(text) : null);
  } catch {
    return defaults();
  }
}

/** Save ``settings``; true when it was stored (a private window may refuse). */
export function save(settings, storage = globalThis.localStorage) {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(clean(settings)));
    return true;
  } catch {
    return false;
  }
}

/** ``title`` cut to at most ``max`` characters, at a word when one is close, with "…". */
export function shorten(title, max) {
  const chars = [...String(title)];
  if (!max || chars.length <= max) return String(title);
  let cut = chars.slice(0, max - 1).join("");
  const space = cut.lastIndexOf(" ");
  if (space >= Math.floor(max * 0.6)) cut = cut.slice(0, space);
  return `${cut.replace(/[\s.,;:\-–—]+$/u, "")}…`;
}

/** The label a node shows with these settings. */
export function labelText(title, settings) {
  return settings.shorten ? shorten(title, settings.length) : String(title);
}
