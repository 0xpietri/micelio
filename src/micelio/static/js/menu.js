// The header's corner (§7c): the Appearance menu (a visitor's own look) and the
// language menu open and close here. The graph settings live on each graph (graph-panel.js).

function start() {
  for (const corner of document.querySelectorAll(".menu-corner")) {
    const toggle = corner.querySelector(".menu-toggle");
    const panel = corner.querySelector(".menu-panel");
    const open = (yes) => {
      panel.hidden = !yes;
      toggle.setAttribute("aria-expanded", String(yes));
      if (yes) {
        const first = panel.querySelector("input, select, a");
        if (first) first.focus();
      }
    };
    toggle.addEventListener("click", () => open(panel.hidden));
    panel.addEventListener("keydown", (e) => { if (e.key === "Escape") { open(false); toggle.focus(); } });
    document.addEventListener("pointerdown", (e) => {
      if (!panel.hidden && !corner.contains(e.target)) open(false);
    });
  }
  // The language menu closes the same way.
  document.addEventListener("pointerdown", (e) => {
    for (const d of document.querySelectorAll("details.lang-menu[open]")) if (!d.contains(e.target)) d.open = false;
  });
}

start();
