// /explore: the graph of everything, with search and filters in the side panel.
import { fold, legendIcon, mountGraph, tr } from "./graph.js";

const graphEl = document.querySelector("[data-graph][data-explore]");
const panel = document.getElementById("explore-panel");

function checked(name) {
  return new Set(
    [...panel.querySelectorAll(`input[name="${name}"]:checked`)].map((input) => input.value),
  );
}

function filterFn() {
  const types = checked("type");
  const categories = checked("category");
  const statuses = checked("status");
  return (n) => {
    const type = n.ghost ? "ghost" : n.type;
    const nodeCategories = n.categories && n.categories.length ? n.categories : ["none"];
    return (
      types.has(type) &&
      (n.ghost || nodeCategories.some((c) => categories.has(c))) &&
      (n.ghost || statuses.has(n.status || "none"))
    );
  };
}

/** Arriving from the landing (``?focus=<slug>``): rise out of the soil onto that note,
 * its neighbors lit and the rest dimmed until the first touch. */
function arrive(graph) {
  const slug = new URLSearchParams(window.location.search).get("focus");
  const stage = graphEl.closest(".explore-stage");
  let dived = false;
  try {
    dived = sessionStorage.getItem("micelio.dive") === "1";
    sessionStorage.removeItem("micelio.dive");
  } catch { /* a private window */ }
  if (dived && stage) {
    stage.classList.add("arriving");
    stage.addEventListener("animationend", () => stage.classList.remove("arriving"), { once: true });
  }
  if (!slug) return;
  const node = graph.nodes.find((n) => n.id === slug);
  if (!node) return;
  const near = new Set([slug]);
  for (const e of graph.data.edges) {
    const a = typeof e.source === "object" ? e.source.id : e.source;
    const b = typeof e.target === "object" ? e.target.id : e.target;
    if (a === slug) near.add(b);
    if (b === slug) near.add(a);
  }
  graph.highlight((n) => near.has(n.id));
  graph.fit(graph.nodes.filter((n) => near.has(n.id)));
  const mark = graph.svg.querySelector(`a.node[data-id="${CSS.escape(slug)}"]`);
  if (mark) mark.focus({ preventScroll: true });
  graph.svg.addEventListener("pointerdown", () => graph.highlight(null), { once: true });
}

async function start() {
  if (!graphEl || !panel) return;
  const graph = await mountGraph(graphEl);
  if (!graph || !graph.filter) return;
  const { strings, data } = graph;

  for (const slot of panel.querySelectorAll("[data-legend-icon]")) {
    slot.replaceChildren(legendIcon(slot.dataset.legendIcon, data));
  }

  const input = panel.querySelector("#graph-search");
  const result = panel.querySelector("#graph-search-result");
  const form = panel.querySelector("form.explore-search");
  let visible = filterFn();

  const search = () => {
    const q = fold(input.value.trim());
    if (!q) {
      graph.highlight(null);
      result.textContent = "";
      return [];
    }
    const matches = graph.nodes.filter((n) => visible(n) && fold(n.title).includes(q));
    const ids = new Set(matches.map((n) => n.id));
    graph.highlight((n) => ids.has(n.id));
    const count = matches.length;
    result.textContent =
      count === 0
        ? tr(strings, "graph.no_match")
        : count === 1
          ? tr(strings, "graph.match_one")
          : tr(strings, "graph.matches", { count });
    return matches;
  };

  graph.filter(visible);
  arrive(graph);
  panel.querySelectorAll("fieldset.filter input").forEach((box) => {
    box.addEventListener("change", () => {
      visible = filterFn();
      graph.filter(visible);
      search();
    });
  });

  input.addEventListener("input", search);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      input.value = "";
      search();
      graph.fit();
    }
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const matches = search();
    if (matches.length === 1 && matches[0].href) window.location.assign(matches[0].href);
    else if (matches.length) graph.fit(matches);
  });
}

start();
