// A project's guide (§3.4): choose the structured or the chronological order, choose which
// kinds of notes it lists, keep both choices in this browser only, and move a note's
// previous / next to what the guide shows.
const KEY = "micelio.guide.v1";
const KINDS = ["note", "question", "gap"];

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
    return {
      order: saved.order === "time" ? "time" : "guide",
      hidden: Array.isArray(saved.hidden) ? saved.hidden.filter((k) => KINDS.includes(k)) : [],
    };
  } catch {
    return { order: "guide", hidden: [] };
  }
}

function save(state) {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* private window or blocked storage: the choice lasts until the page closes */
  }
}

/** Show the steps of the kinds chosen, and a section while something under it shows. */
function filter(list, hidden) {
  const items = [...list.children];
  for (const item of items) {
    if (item.dataset.kind !== "section") item.hidden = hidden.includes(item.dataset.kind);
  }
  items.forEach((item, i) => {
    if (item.dataset.kind !== "section") return;
    const depth = Number(item.dataset.depth || 0);
    let shown = false;
    for (const next of items.slice(i + 1)) {
      if (Number(next.dataset.depth || 0) <= depth) break;
      if (next.dataset.kind !== "section" && !next.hidden) {
        shown = true;
        break;
      }
    }
    item.hidden = !shown;
  });
}

/** Previous and next among the notes the guide shows, in its order. */
function page(pager, list) {
  if (!pager || !list) return;
  const steps = [...list.querySelectorAll(".guide-step")];
  const current = steps.findIndex((s) => s.classList.contains("current"));
  if (current < 0) return;
  const linked = (s) => !s.hidden && s.querySelector("a");
  const before = steps.slice(0, current).filter(linked);
  const after = steps.slice(current + 1).filter(linked);
  const shown = steps.filter(linked);
  const set = (anchor, step) => {
    anchor.hidden = !step;
    if (!step) return;
    const link = step.querySelector("a");
    anchor.href = link.getAttribute("href");
    anchor.querySelector(".pager-title").textContent = link.textContent;
  };
  set(pager.querySelector(".prev"), before[before.length - 1]);
  set(pager.querySelector(".next"), after[0]);
  const position = pager.querySelector(".pager-position");
  const index = shown.indexOf(steps[current]);
  position.hidden = index < 0;
  position.textContent = (pager.dataset.position || "{position} / {total}")
    .replace("{position}", String(index + 1))
    .replace("{total}", String(shown.length));
}

function apply(state) {
  const pager = document.querySelector("[data-guide-pager]");
  for (const box of document.querySelectorAll("[data-guide]")) {
    const select = box.querySelector("[data-guide-order]");
    if (select) select.value = state.order;
    for (const input of box.querySelectorAll("[data-guide-kind]")) {
      input.checked = !state.hidden.includes(input.dataset.guideKind);
    }
    for (const list of box.querySelectorAll("[data-guide-list]")) {
      list.hidden = list.dataset.guideList !== state.order;
      filter(list, state.hidden);
    }
    page(pager, box.querySelector(`[data-guide-list="${state.order}"]`));
  }
}

const state = load();
apply(state);

for (const box of document.querySelectorAll("[data-guide]")) {
  // Open beside the page on a wide screen; folded above it on a phone.
  if (window.matchMedia("(min-width: 1100px)").matches) box.open = true;
  box.addEventListener("change", (event) => {
    const select = event.target.closest("[data-guide-order]");
    if (select) state.order = select.value === "time" ? "time" : "guide";
    const input = event.target.closest("[data-guide-kind]");
    if (input) {
      const kind = input.dataset.guideKind;
      state.hidden = state.hidden.filter((k) => k !== kind);
      if (!input.checked) state.hidden.push(kind);
    }
    if (!select && !input) return;
    save(state);
    apply(state);
  });
}
