// A project's guide (§3.4): switch between the structured and the chronological order,
// choose which kinds of notes it lists, and keep both choices in this browser only.
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

function apply(state) {
  for (const box of document.querySelectorAll("[data-guide]")) {
    for (const button of box.querySelectorAll("[data-guide-order]")) {
      button.setAttribute("aria-pressed", String(button.dataset.guideOrder === state.order));
    }
    for (const input of box.querySelectorAll("[data-guide-kind]")) {
      input.checked = !state.hidden.includes(input.dataset.guideKind);
    }
    for (const list of box.querySelectorAll("[data-guide-list]")) {
      list.hidden = list.dataset.guideList !== state.order;
      // A stretch's heading shows while one of its steps does.
      let heading = null;
      let shown = false;
      const close = () => { if (heading) heading.hidden = !shown; };
      for (const item of list.children) {
        if (item.hasAttribute("data-guide-chapter")) {
          close();
          heading = item;
          shown = false;
          continue;
        }
        item.hidden = state.hidden.includes(item.dataset.kind);
        shown ||= !item.hidden;
      }
      close();
    }
  }
  for (const pager of document.querySelectorAll("[data-guide-pager]")) {
    pager.hidden = pager.dataset.guidePager !== state.order;
  }
}

const state = load();
apply(state);

for (const box of document.querySelectorAll("[data-guide]")) {
  // Open beside the page on a wide screen; folded above it on a phone.
  if (window.matchMedia("(min-width: 1100px)").matches) box.open = true;
  box.addEventListener("click", (event) => {
    const button = event.target.closest("[data-guide-order]");
    if (!button) return;
    state.order = button.dataset.guideOrder === "time" ? "time" : "guide";
    save(state);
    apply(state);
  });
  box.addEventListener("change", (event) => {
    const input = event.target.closest("[data-guide-kind]");
    if (!input) return;
    const kind = input.dataset.guideKind;
    state.hidden = state.hidden.filter((k) => k !== kind);
    if (!input.checked) state.hidden.push(kind);
    save(state);
    apply(state);
  });
}
