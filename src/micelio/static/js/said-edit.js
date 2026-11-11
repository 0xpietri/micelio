// The owner's said bubbles (§8a): write one between two paragraphs, change its words,
// move it or delete it. Only on the owner's pages with editing on: the note's body then
// carries where to send changes, the key and the hash of the file shown, and each
// top-level block the lines it came from (data-l="start-end").
//
// Desktop: a floating "Add a note" button beside the text; the gap between paragraphs
// nearest to it lights up and a click opens the composer there. Bubbles are dragged by
// their handle, or moved with Move. Phone: hold a blank space between paragraphs, a popup
// offers "Write a note"; bubbles have a ⋯ menu (Edit, Move with ↑ ↓, Delete).
//
// The composer and the popup keep an empty slot (.said-extra) for the voice-note button
// still to come: it will record in the same composer and save into the same bubble.

const HOLD_MS = 500;
const HINT_KEY = "micelio.said.hint.v1";

let strings = {};
const t = (key, values = {}) =>
  (strings[`said.${key}`] ?? key).replace(/\{(\w+)\}/g, (all, k) => (k in values ? String(values[k]) : all));

const coarse = () => window.matchMedia("(pointer: coarse)").matches;
const prose = () => document.querySelector(".prose[data-said-url]");

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) node.setAttribute(k, v === true ? "" : v);
  }
  for (const child of children) node.append(child);
  return node;
}

/* ---------- the body's blocks and the gaps between them ---------- */

function lineOf(node) {
  const l = node.dataset.l || node.querySelector(":scope > code[data-l]")?.dataset.l;
  if (!l) return null;
  const [start, end] = l.split("-").map(Number);
  return { start, end };
}

function blocks(root) {
  const found = [];
  for (const node of root.children) {
    if (node.classList.contains("said-ui")) continue;
    const lines = lineOf(node);
    if (lines) found.push({ el: node, ...lines });
  }
  return found;
}

/** Each place a bubble can go: before a block, or after the last one; y in page pixels. */
function gaps(root) {
  const list = blocks(root);
  const top = (node) => node.getBoundingClientRect().top + window.scrollY;
  const bottom = (node) => node.getBoundingClientRect().bottom + window.scrollY;
  const result = list.map((b, i) => ({
    at: b.start,
    before: b.el,
    after: i > 0 ? list[i - 1].el : null,
    y: i > 0 ? (bottom(list[i - 1].el) + top(b.el)) / 2 : top(b.el) - 8,
  }));
  if (list.length) {
    const last = list[list.length - 1];
    result.push({ at: last.end, before: null, after: last.el, y: bottom(last.el) + 8 });
  }
  return result;
}

function nearest(root, pageY) {
  let best = null;
  for (const gap of gaps(root)) {
    if (!best || Math.abs(gap.y - pageY) < Math.abs(best.y - pageY)) best = gap;
  }
  return best;
}

/* ---------- talking to the server ---------- */

async function send(payload) {
  const root = prose();
  const response = await fetch(root.dataset.saidUrl, {
    method: "POST",
    credentials: "same-origin",
    headers: { "content-type": "application/json", "x-micelio-form": root.dataset.saidToken },
    body: JSON.stringify({ ...payload, hash: root.dataset.saidHash }),
  });
  let data = {};
  try {
    data = await response.json();
  } catch {
    /* an error page */
  }
  if (response.ok && data.ok) return data;
  throw Object.assign(new Error(data.error || String(response.status)), {
    code: data.error || String(response.status),
  });
}

async function words(start) {
  const root = prose();
  const r = await fetch(`${root.dataset.saidUrl}?start=${start}`, { credentials: "same-origin" });
  const data = await r.json();
  if (!r.ok || !data.ok) throw Object.assign(new Error(data.error), { code: data.error });
  return data.text;
}

/** The note's body (and its dates card) as it is now, without leaving the page. */
async function reloadBody() {
  try {
    const r = await fetch(location.href, { credentials: "same-origin", cache: "no-store" });
    const doc = new DOMParser().parseFromString(await r.text(), "text/html");
    const fresh = doc.querySelector(".prose[data-said-url]");
    if (!r.ok || !fresh) throw new Error("page");
    prose().replaceWith(document.adoptNode(fresh));
    const card = doc.querySelector(".note-card");
    const old = document.querySelector(".note-card");
    if (card && old) old.replaceWith(document.adoptNode(card));
    decorate();
  } catch {
    location.reload();
  }
}

function showError(holder, error) {
  holder.replaceChildren();
  if (error.code === "changed") {
    holder.append(t("changed"), " ", el("button", { type: "button", class: "said-link", text: t("reload"), onclick: () => location.reload() }));
  } else {
    holder.append(t("failed", { error: error.code || error.message }));
  }
  holder.classList.add("said-error");
}

/* ---------- the drop line ---------- */

let line = null;
function showLine(gap) {
  const root = prose();
  if (!gap) return hideLine();
  if (!line || !root.contains(line)) {
    line = el("div", { class: "said-ui said-drop", "aria-hidden": "true" });
    root.append(line);
  }
  const rootTop = root.getBoundingClientRect().top + window.scrollY;
  line.style.top = `${gap.y - rootTop}px`;
  line.hidden = false;
}
function hideLine() {
  if (line) line.hidden = true;
}

/* ---------- the composer: new words, or a bubble's words changed ---------- */

let composing = null;

function closeComposer() {
  if (!composing) return;
  composing.box.remove();
  if (composing.hidden) composing.hidden.hidden = false;
  composing = null;
}

function composer(place, { text = "", start = null, replacing = null } = {}) {
  closeComposer();
  closePopup();
  const area = el("textarea", { rows: "3", placeholder: t("placeholder"), "aria-label": t("write") });
  area.value = text;
  const status = el("span", { class: "said-status", role: "status" });
  const save = el("button", { type: "button", class: "said-save", text: t("save") });
  const cancel = el("button", { type: "button", class: "said-cancel", text: t("cancel"), onclick: closeComposer });
  // Kept empty for the voice-note button (recorded into this same bubble), not built yet.
  const extra = el("span", { class: "said-extra" });
  const box = el("div", { class: "said-ui callout callout-said said-composer" }, [
    area,
    el("div", { class: "said-actions" }, [extra, status, cancel, save]),
  ]);
  const root = prose();
  if (replacing) replacing.before(box);
  else if (place.before) place.before.before(box);
  else root.append(box);
  if (replacing) replacing.hidden = true;
  composing = { box, hidden: replacing };

  const grow = () => {
    area.style.height = "auto";
    area.style.height = `${area.scrollHeight + 2}px`;
  };
  area.addEventListener("input", grow);
  const submit = async () => {
    const value = area.value.trim();
    if (!value) return;
    save.disabled = true;
    status.classList.remove("said-error");
    status.textContent = t("saving");
    try {
      await send(start === null ? { op: "insert", at: place.at, text: value } : { op: "edit", start, text: value });
      composing = null;
      await reloadBody();
    } catch (error) {
      save.disabled = false;
      showError(status, error);
    }
  };
  save.addEventListener("click", submit);
  area.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit();
    if (e.key === "Escape") closeComposer();
  });
  grow();
  area.focus({ preventScroll: true });
  box.scrollIntoView({ block: "nearest", behavior: "smooth" });
  hideLine();
}

/* ---------- each bubble: edit, move, delete ---------- */

function moveMode(bubble, start) {
  const root = prose();
  root.classList.add("said-moving");
  bubble.classList.add("moving");
  const status = el("span", { class: "said-status", role: "status" });
  const step = (dir) => {
    const list = blocks(root).filter((b) => b.el !== bubble);
    const below = list.findIndex((b) => b.el.compareDocumentPosition(bubble) & Node.DOCUMENT_POSITION_PRECEDING);
    const next = below < 0 ? list.length : below; // index of the first block after the bubble
    const target = next + dir;
    if (target < 0 || target > list.length) return;
    if (target === list.length) list[list.length - 1].el.after(bubble);
    else list[target].el.before(bubble);
    bubble.scrollIntoView({ block: "center", behavior: "smooth" });
  };
  const finish = async () => {
    const list = blocks(root).filter((b) => b.el !== bubble);
    const below = list.find((b) => b.el.compareDocumentPosition(bubble) & Node.DOCUMENT_POSITION_PRECEDING);
    const at = below ? below.start : list[list.length - 1]?.end ?? 0;
    status.textContent = t("saving");
    try {
      await send({ op: "move", start, at });
      await reloadBody();
    } catch (error) {
      showError(status, error);
    }
  };
  const bar = el("div", { class: "said-ui said-tools said-move-tools" }, [
    el("button", { type: "button", title: t("up"), "aria-label": t("up"), text: "↑", onclick: () => step(-1) }),
    el("button", { type: "button", title: t("down"), "aria-label": t("down"), text: "↓", onclick: () => step(1) }),
    el("button", { type: "button", class: "said-save", text: t("done"), onclick: finish }),
    el("button", { type: "button", text: t("cancel"), onclick: reloadBody }),
    status,
  ]);
  bubble.querySelector(":scope > .said-tools")?.remove();
  bubble.append(bar);
}

function drag(bubble, start, handle) {
  handle.addEventListener("pointerdown", (down) => {
    if (down.button !== 0) return;
    down.preventDefault();
    handle.setPointerCapture(down.pointerId);
    const root = prose();
    bubble.classList.add("dragging");
    let gap = null;
    let y = down.clientY;
    let scrolling = 0;
    const track = () => {
      gap = nearest(root, y + window.scrollY);
      const stays = gap && (gap.before === bubble || gap.after === bubble);
      if (stays) gap = null;
      showLine(gap);
    };
    const edge = () => {
      const zone = 60;
      const speed = y < zone ? -(zone - y) / 3 : y > innerHeight - zone ? (y - innerHeight + zone) / 3 : 0;
      if (speed) {
        window.scrollBy(0, speed);
        track();
      }
      scrolling = speed ? requestAnimationFrame(edge) : 0;
    };
    const move = (e) => {
      y = e.clientY;
      track();
      if (!scrolling) scrolling = requestAnimationFrame(edge);
    };
    const up = async () => {
      handle.removeEventListener("pointermove", move);
      cancelAnimationFrame(scrolling);
      bubble.classList.remove("dragging");
      hideLine();
      if (!gap) return;
      try {
        await send({ op: "move", start, at: gap.at });
        await reloadBody();
      } catch (error) {
        const status = el("p", { class: "said-ui said-status" });
        showError(status, error);
        bubble.after(status);
      }
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up, { once: true });
    handle.addEventListener("pointercancel", () => {
      handle.removeEventListener("pointermove", move);
      bubble.classList.remove("dragging");
      hideLine();
    }, { once: true });
  });
}

function tools(bubble, start) {
  let armed = 0;
  const remove = el("button", { type: "button", class: "said-delete", text: t("delete") });
  remove.addEventListener("click", async () => {
    if (!armed) {
      remove.textContent = t("delete_confirm");
      remove.classList.add("armed");
      armed = window.setTimeout(() => {
        armed = 0;
        remove.textContent = t("delete");
        remove.classList.remove("armed");
      }, 4000);
      return;
    }
    clearTimeout(armed);
    try {
      await send({ op: "delete", start });
      await reloadBody();
    } catch (error) {
      showError(remove.parentElement.querySelector(".said-status"), error);
    }
  });
  const edit = el("button", { type: "button", text: t("edit") });
  edit.addEventListener("click", async () => {
    try {
      composer(null, { text: await words(start), start, replacing: bubble });
    } catch (error) {
      showError(bar.querySelector(".said-status"), error);
    }
  });
  const handle = el("button", { type: "button", class: "said-handle", title: t("drag"), "aria-label": t("drag"), text: "⠿" });
  drag(bubble, start, handle);
  const bar = el("div", { class: "said-ui said-tools", role: "toolbar", "aria-label": t("menu") }, [
    handle,
    edit,
    el("button", { type: "button", text: t("move"), onclick: () => moveMode(bubble, start) }),
    remove,
    el("span", { class: "said-status", role: "status" }),
  ]);
  // On a phone the tools wait behind ⋯ (there is no hover).
  const more = el("button", {
    type: "button",
    class: "said-ui said-more",
    title: t("menu"),
    "aria-label": t("menu"),
    "aria-expanded": "false",
    text: "⋯",
    onclick: () => {
      const open = bubble.classList.toggle("tools-open");
      more.setAttribute("aria-expanded", String(open));
    },
  });
  bubble.append(more, bar);
}

function decorate() {
  const root = prose();
  if (!root) return;
  for (const b of blocks(root)) {
    if (b.el.classList.contains("callout-said")) tools(b.el, b.start);
  }
  if (coarse()) hint(root);
}

/* ---------- desktop: the floating button ---------- */

function fab() {
  const add = el("button", { type: "button", class: "said-fab-add", title: t("add_here"), "aria-label": t("add_here") }, [
    el("span", { "aria-hidden": "true", text: "+" }),
    el("span", { class: "said-fab-label", text: t("add") }),
  ]);
  // The voice-note button will sit in this same floating bar, under "Add a note".
  const bar = el("div", { class: "said-ui said-fab" }, [add, el("span", { class: "said-extra" })]);
  document.body.append(bar);
  const centre = () => {
    const r = add.getBoundingClientRect();
    return r.top + r.height / 2 + window.scrollY;
  };
  const place = () => {
    const root = prose();
    const r = root.getBoundingClientRect();
    const room = innerWidth - r.right;
    bar.style.left = room > 190 ? `${r.right + 24}px` : "";
    bar.classList.toggle("tight", room <= 190);
    bar.hidden = r.bottom < innerHeight * 0.3 || r.top > innerHeight * 0.7;
    if (bar.matches(":hover, :focus-within") && !composing) showLine(nearest(root, centre()));
  };
  add.addEventListener("pointerenter", () => !composing && showLine(nearest(prose(), centre())));
  add.addEventListener("focus", () => !composing && showLine(nearest(prose(), centre())));
  add.addEventListener("pointerleave", hideLine);
  add.addEventListener("blur", hideLine);
  add.addEventListener("click", () => composer(nearest(prose(), centre())));
  window.addEventListener("scroll", place, { passive: true });
  window.addEventListener("resize", place);
  place();
}

/* ---------- phone: hold a blank space, a popup ---------- */

let popup = null;
function closePopup() {
  popup?.remove();
  popup = null;
  hideLine();
}

function openPopup(x, y, gap) {
  closePopup();
  showLine(gap);
  popup = el("div", { class: "said-ui said-popup", role: "dialog", "aria-label": t("add_here") }, [
    el("button", { type: "button", class: "said-save", text: `✎ ${t("write")}`, onclick: () => composer(gap) }),
    // The voice-note button will go here, beside "Write a note".
    el("span", { class: "said-extra" }),
  ]);
  document.body.append(popup);
  const w = popup.offsetWidth;
  popup.style.left = `${Math.max(8, Math.min(innerWidth - w - 8, x - w / 2))}px`;
  popup.style.top = `${y + window.scrollY - popup.offsetHeight - 14}px`;
  try {
    localStorage.setItem(HINT_KEY, "1");
  } catch {
    /* blocked storage */
  }
  document.querySelector(".said-hint")?.remove();
}

function isBlank(target, root) {
  if (target === root) return true;
  if (root.contains(target)) return false;
  // The page's margins beside the text, but never its words, links or controls.
  return Boolean(target.closest("main, article")) && !target.closest("p, li, a, button, input, textarea, label, h1, h2, h3, dl, svg, canvas, img, header, aside, nav, .said-ui, .tags");
}

function hold() {
  let timer = 0;
  let from = null;
  let held = false;
  document.addEventListener("pointerdown", (e) => {
    if (e.pointerType !== "touch" || composing) return;
    if (popup && !popup.contains(e.target)) closePopup();
    const root = prose();
    if (!root || !isBlank(e.target, root)) return;
    const r = root.getBoundingClientRect();
    if (e.clientY < r.top - 16 || e.clientY > r.bottom + 16) return;
    from = { x: e.clientX, y: e.clientY };
    held = false;
    timer = window.setTimeout(() => {
      held = true;
      navigator.vibrate?.(12);
      openPopup(from.x, from.y, nearest(root, from.y + window.scrollY));
    }, HOLD_MS);
  });
  const stop = () => clearTimeout(timer);
  document.addEventListener("pointermove", (e) => {
    if (from && Math.hypot(e.clientX - from.x, e.clientY - from.y) > 10) stop();
  });
  document.addEventListener("pointerup", stop);
  document.addEventListener("pointercancel", stop);
  document.addEventListener("contextmenu", (e) => {
    if (held) e.preventDefault();
  });
}

function hint(root) {
  try {
    if (localStorage.getItem(HINT_KEY)) return;
  } catch {
    return;
  }
  if (!document.querySelector(".said-hint")) root.after(el("p", { class: "said-ui said-hint muted", text: t("hint_press") }));
}

/* ---------- start ---------- */

async function start() {
  if (!prose()) return;
  try {
    const lang = document.documentElement.lang || "en";
    const r = await fetch(`/static/locales/${encodeURIComponent(lang)}.json`);
    strings = r.ok ? await r.json() : {};
  } catch {
    strings = {};
  }
  decorate();
  if (!coarse()) fab();
  hold();
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closePopup();
  });
}

start();
