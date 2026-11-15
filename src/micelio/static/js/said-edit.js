// The owner's said bubbles (§8a): write one between two paragraphs, change its words,
// move it or delete it. Only on the owner's pages with editing on: the note's body then
// carries where to send changes, the key and the hash of the file shown, and each
// top-level block the lines it came from (data-l="start-end").
//
// Every screen: an "Add a note" card where the note ends, beside where the pager starts;
// a click opens the composer after the last block. Desktop: bubbles are dragged by their
// handle, or moved with Move. Phone: also hold a blank space between paragraphs, a popup
// offers "Write a note"; bubbles have a ⋯ menu (Edit, Move with ↑ ↓, Delete).
//
// The composer and the popup keep an empty slot (.said-extra) for the voice-note button
// still to come: it will record in the same composer and save into the same bubble.
//
// The rest of the note too (§8a): every other top-level block (a paragraph, a list, the
// takeaway, a table) can be changed as Markdown or deleted, and a heading deleted with
// everything under it. Desktop: the tools show over the block under the pointer. Phone:
// "Edit parts" under the text, then tap a block. "Edit note" opens the whole body as
// Markdown (the frontmatter stays as it is); its text is kept in the browser until it is
// saved, so a refused save loses nothing. "Undo" puts back what the last change replaced,
// while nobody else has written the note since.

const HOLD_MS = 500;
const HINT_KEY = "micelio.said.hint.v1";
const DRAFT_KEY = "micelio.draft.v1:";

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
  if (error.code === "not-last" || error.code === "nothing") {
    holder.append(t(error.code === "nothing" ? "nothing" : "not_last"));
  } else if (error.code === "changed") {
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
  parts(root);
  if (noteBar) noteBar.refresh();
}

/* ---------- any other block: change it, delete it, delete its section ---------- */

const isSaid = (node) => node.classList.contains("callout-said");
const headingLevel = (node) => (/^H([1-6])$/.exec(node.tagName) || [])[1];

function blockAt(root, target) {
  let node = target;
  while (node && node.parentElement !== root) node = node.parentElement;
  if (!node || node.classList.contains("said-ui") || isSaid(node)) return null;
  return blocks(root).find((b) => b.el === node) || null;
}

/** The blocks a heading's section holds: it, and all up to a heading as high as it. */
function sectionOf(root, block) {
  const level = headingLevel(block.el);
  if (!level) return [];
  const list = blocks(root);
  const from = list.findIndex((b) => b.el === block.el);
  const found = [list[from]];
  for (const b of list.slice(from + 1)) {
    const other = headingLevel(b.el);
    if (other && other <= level) break;
    found.push(b);
  }
  return found;
}

function confirmTwice(button, label, armedLabel, onArm, onDisarm, action) {
  let armed = 0;
  button.addEventListener("click", async () => {
    if (!armed) {
      button.textContent = armedLabel;
      button.classList.add("armed");
      onArm();
      armed = window.setTimeout(() => {
        armed = 0;
        button.textContent = label;
        button.classList.remove("armed");
        onDisarm();
      }, 4000);
      return;
    }
    clearTimeout(armed);
    armed = 0;
    await action();
  });
}

let partBar = null;
let partCurrent = null;

function parts(root) {
  // A fresh body (after each save) gets a fresh toolbar.
  partCurrent = null;
  const status = el("span", { class: "said-status", role: "status" });
  const edit = el("button", { type: "button", text: t("edit") });
  const remove = el("button", { type: "button", class: "said-delete", text: t("delete") });
  const section = el("button", { type: "button", class: "said-delete", text: t("delete_section") });
  const doomed = (on, list) => list.forEach((b) => b.el.classList.toggle("said-doomed", on));
  confirmTwice(remove, t("delete"), t("delete_confirm"),
    () => partCurrent && doomed(true, [partCurrent]),
    () => document.querySelectorAll(".said-doomed").forEach((n) => n.classList.remove("said-doomed")),
    async () => {
      try {
        await send({ op: "drop", start: partCurrent.start });
        await reloadBody();
      } catch (error) {
        showError(status, error);
      }
    });
  confirmTwice(section, t("delete_section"), t("delete_section_confirm"),
    () => partCurrent && doomed(true, sectionOf(prose(), partCurrent)),
    () => document.querySelectorAll(".said-doomed").forEach((n) => n.classList.remove("said-doomed")),
    async () => {
      try {
        await send({ op: "section", start: partCurrent.start });
        await reloadBody();
      } catch (error) {
        showError(status, error);
      }
    });
  edit.addEventListener("click", async () => {
    const block = partCurrent;
    if (!block) return;
    try {
      const r = await fetch(`${prose().dataset.saidSource}?start=${block.start}`, { credentials: "same-origin" });
      const data = await r.json();
      if (!r.ok || !data.ok) throw Object.assign(new Error(data.error), { code: data.error });
      blockEditor(block, data.text);
    } catch (error) {
      showError(status, error);
    }
  });
  partBar = el("div", { class: "said-ui said-tools said-part-tools", role: "toolbar", "aria-label": t("part_menu"), hidden: true }, [
    edit, remove, section, status,
  ]);
  partBar.sectionButton = section;
  partBar.status = status;
  root.append(partBar);

  const show = (block) => {
    if (partCurrent?.el === block?.el || composing) return;
    document.querySelectorAll(".said-part-on").forEach((n) => n.classList.remove("said-part-on"));
    partCurrent = block;
    if (!block) {
      partBar.hidden = true;
      return;
    }
    block.el.classList.add("said-part-on");
    status.replaceChildren();
    status.classList.remove("said-error");
    section.hidden = !headingLevel(block.el);
    const top = block.el.getBoundingClientRect().top - root.getBoundingClientRect().top;
    partBar.style.top = `${top}px`;
    partBar.hidden = false;
  };
  // Pointing at the text never offers to change it: the parts answer only with "Edit
  // parts" on; otherwise the note changes only through the Edit card.
  root.addEventListener("pointerover", (e) => {
    if (!root.classList.contains("said-parts")) return;
    if (e.pointerType === "touch" || partBar.contains(e.target)) return;
    const block = blockAt(root, e.target);
    if (block || e.target === root) show(block);
  });
  root.addEventListener("pointerleave", (e) => {
    if (e.pointerType !== "touch" && !partBar.querySelector(".armed")) show(null);
  });
  // Phone: with "Edit parts" on, a tap picks the block.
  root.addEventListener("click", (e) => {
    if (!root.classList.contains("said-parts") || partBar.contains(e.target)) return;
    const block = blockAt(root, e.target);
    if (!block) return;
    e.preventDefault();
    show(block);
  });
}

function blockEditor(block, text) {
  closeComposer();
  partBar.hidden = true;
  const area = el("textarea", { rows: "4", "aria-label": t("edit_part"), spellcheck: "true" });
  area.value = text;
  const status = el("span", { class: "said-status", role: "status" });
  const save = el("button", { type: "button", class: "said-save", text: t("save") });
  const cancel = el("button", { type: "button", class: "said-cancel", text: t("cancel"), onclick: closeComposer });
  const box = el("div", { class: "said-ui said-composer said-part-editor" }, [
    area,
    el("div", { class: "said-actions" }, [el("span", { class: "muted said-tip", text: t("part_tip") }), status, cancel, save]),
  ]);
  block.el.before(box);
  block.el.hidden = true;
  composing = { box, hidden: block.el };
  const grow = () => {
    area.style.height = "auto";
    area.style.height = `${area.scrollHeight + 2}px`;
  };
  area.addEventListener("input", grow);
  const submit = async () => {
    save.disabled = true;
    status.classList.remove("said-error");
    status.textContent = t("saving");
    try {
      await send({ op: "block", start: block.start, text: area.value });
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
}

/* ---------- the whole note, and Undo ---------- */

let noteBar = null;

function draftKey() {
  return DRAFT_KEY + prose().dataset.saidUrl;
}
function readDraft() {
  try {
    return localStorage.getItem(draftKey());
  } catch {
    return null;
  }
}
function writeDraft(text) {
  try {
    if (text === null) localStorage.removeItem(draftKey());
    else localStorage.setItem(draftKey(), text);
  } catch {
    /* blocked storage: the text stays in the box */
  }
}

async function noteEditor() {
  const root = prose();
  closeComposer();
  let text;
  try {
    const r = await fetch(root.dataset.saidSource, { credentials: "same-origin", cache: "no-store" });
    const data = await r.json();
    if (!r.ok || !data.ok) throw Object.assign(new Error(data.error), { code: data.error });
    text = data.text;
  } catch (error) {
    showError(noteBar.status, error);
    return;
  }
  const draft = readDraft();
  const area = el("textarea", { rows: "20", "aria-label": t("note_editor"), spellcheck: "true" });
  area.value = draft && draft !== text ? draft : text;
  const status = el("span", { class: "said-status", role: "status" });
  if (draft && draft !== text) {
    status.append(t("draft_back"), " ", el("button", {
      type: "button",
      class: "said-link",
      text: t("discard"),
      onclick: () => {
        area.value = text;
        writeDraft(null);
        status.replaceChildren();
      },
    }));
  }
  const save = el("button", { type: "button", class: "said-save", text: t("save") });
  const close = () => {
    box.remove();
    root.hidden = false;
    noteBar.el.hidden = false;
  };
  const cancel = el("button", {
    type: "button",
    class: "said-cancel",
    text: t("cancel"),
    onclick: () => {
      writeDraft(null);
      close();
    },
  });
  const box = el("div", { class: "said-ui said-composer said-note-editor" }, [
    el("p", { class: "muted said-tip", text: t("note_tip") }),
    area,
    el("div", { class: "said-actions" }, [status, cancel, save]),
  ]);
  root.before(box);
  root.hidden = true;
  noteBar.el.hidden = true;
  area.addEventListener("input", () => writeDraft(area.value));
  const submit = async () => {
    save.disabled = true;
    status.classList.remove("said-error");
    status.textContent = t("saving");
    try {
      await send({ op: "body", text: area.value });
      writeDraft(null);
      close();
      await reloadBody();
    } catch (error) {
      save.disabled = false;
      showError(status, error);
    }
  };
  save.addEventListener("click", submit);
  area.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit();
  });
  area.focus({ preventScroll: true });
  box.scrollIntoView({ block: "start", behavior: "smooth" });
}

function noteTools() {
  const root = prose();
  const status = el("span", { class: "said-status", role: "status" });
  // "Edit" looks like the "Add a comment" card beside it: the one way into the note's text.
  const whole = el("button", { type: "button", class: "note-card glass said-add said-edit-note", onclick: noteEditor }, [
    el("span", { class: "said-add-title" }, [el("span", { "aria-hidden": "true", text: "✎" }), document.createTextNode(` ${t("edit_note")}`)]),
  ]);
  const partsButton = el("button", {
    type: "button",
    class: "said-parts-toggle",
    "aria-pressed": "false",
    text: t("edit_parts"),
    onclick: () => {
      const on = prose().classList.toggle("said-parts");
      partsButton.setAttribute("aria-pressed", String(on));
      partsButton.textContent = on ? t("parts_done") : t("edit_parts");
      if (!on && partBar) partBar.hidden = true;
    },
  });
  const undo = el("button", {
    type: "button",
    text: `↶ ${t("undo")}`,
    title: t("undo_title"),
    onclick: async () => {
      undo.disabled = true;
      status.classList.remove("said-error");
      status.textContent = t("saving");
      try {
        await send({ op: "undo" });
        await reloadBody();
        status.textContent = t("undone");
      } catch (error) {
        showError(status, error);
      }
      undo.disabled = false;
    },
  });
  const bar = el("div", { class: "said-ui said-note-tools" }, [whole, partsButton, undo, status]);
  // On the same row as the "Add a note" card, at its left; under the text without it.
  const foot = document.querySelector(".note-foot");
  if (foot) foot.prepend(bar);
  else root.after(bar);
  noteBar = {
    el: bar,
    status,
    refresh: () => {
      const fresh = prose();
      undo.hidden = fresh.dataset.saidUndo !== "1";
      if (partsButton.getAttribute("aria-pressed") === "true") fresh.classList.add("said-parts");
    },
  };
  noteBar.refresh();
}

/* ---------- "Add a note": the card under the note ---------- */

/** The card the page puts where the note ends (desktop and phone): it writes after the
 * last block; the bubble can then be dragged or moved anywhere. */
function addCard() {
  const add = document.querySelector("[data-said-add]");
  if (!add) return;
  const last = () => {
    const all = gaps(prose());
    return all[all.length - 1] || null;
  };
  add.hidden = false;
  add.addEventListener("pointerenter", () => !composing && showLine(last()));
  add.addEventListener("focus", () => !composing && showLine(last()));
  add.addEventListener("pointerleave", hideLine);
  add.addEventListener("blur", hideLine);
  add.addEventListener("click", () => {
    const gap = last();
    if (gap) composer(gap);
  });
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
  noteTools();
  decorate();
  addCard();
  hold();
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closePopup();
  });
}

start();
