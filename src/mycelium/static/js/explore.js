// /explore: the graph of everything, with search and filters in the side panel.
import { fold, mountGraph, relayout, tr } from "./graph.js";

const graphEl = document.querySelector("[data-graph][data-explore]");
const panel = document.getElementById("explore-panel");

function checked(name) {
  return new Set(
    [...panel.querySelectorAll(`input[name="${name}"]:checked`)].map((input) => input.value),
  );
}

function applyFilters(cy) {
  const types = checked("type");
  const categories = checked("category");
  const statuses = checked("status");
  cy.batch(() => {
    cy.nodes().forEach((node) => {
      const d = node.data();
      const nodeCategories = d.categories.length ? d.categories : ["none"];
      const visible =
        types.has(d.type) &&
        nodeCategories.some((c) => categories.has(c)) &&
        (d.ghost || statuses.has(d.status || "none"));
      node.toggleClass("hidden", !visible);
    });
  });
}

function search(cy, strings, query, result) {
  const q = fold(query.trim());
  cy.batch(() => {
    cy.elements().removeClass("dim match");
    if (!q) return;
    const visible = cy.nodes().not(".hidden");
    const matches = visible.filter((n) => fold(n.data("title")).includes(q));
    cy.elements().not(matches).addClass("dim");
    matches.addClass("match");
  });
  if (!q) {
    result.textContent = "";
    return cy.collection();
  }
  const matches = cy.nodes(".match");
  const count = matches.length;
  result.textContent =
    count === 0
      ? tr(strings, "graph.no_match")
      : count === 1
        ? tr(strings, "graph.match_one")
        : tr(strings, "graph.matches", { count });
  return matches;
}

async function start() {
  if (!graphEl || !panel) return;
  const cy = await mountGraph(graphEl);
  if (!cy) return;
  const { strings } = cy.scratch("mycelium");

  const input = panel.querySelector("#graph-search");
  const result = panel.querySelector("#graph-search-result");
  const form = panel.querySelector("form.explore-search");

  applyFilters(cy);
  panel.querySelectorAll("fieldset.filter input").forEach((box) => {
    box.addEventListener("change", () => {
      applyFilters(cy);
      search(cy, strings, input.value, result);
      relayout(cy);
    });
  });

  input.addEventListener("input", () => search(cy, strings, input.value, result));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      input.value = "";
      search(cy, strings, "", result);
    }
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const matches = search(cy, strings, input.value, result);
    if (matches.length === 1 && matches.data("href")) {
      window.location.assign(matches.data("href"));
    } else if (matches.length) {
      const duration = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 300;
      cy.animate({ fit: { eles: matches, padding: 80 } }, { duration });
    }
  });
}

start();
