// A visitor's own look (§7b), applied before the page paints. Classic script, run from
// <head> right after /theme.css, only for visitors. It reads the browser's localStorage;
// nothing is sent anywhere except the palette's name, to /theme.css and the graph APIs.
(function () {
  "use strict";
  var KEY = "micelio.look.v1";
  var look = null;
  try {
    look = JSON.parse(window.localStorage.getItem(KEY) || "null");
  } catch (e) {
    look = null;
  }
  if (!look || typeof look !== "object") return;
  var root = document.documentElement;
  var word = /^[a-z][a-z-]{0,30}$/;
  var color = /^#[0-9a-fA-F]{6}( #[0-9a-fA-F]{6}){1,15}$/;
  if (typeof look.palette === "string" && word.test(look.palette)) {
    root.dataset.palette = look.palette;
    var theme = document.querySelector('link[rel="stylesheet"][href^="/theme.css"]');
    if (theme) theme.setAttribute("href", theme.getAttribute("href") + "&palette=" + encodeURIComponent(look.palette));
    if (typeof look.ramp === "string" && color.test(look.ramp)) root.dataset.ramp = look.ramp;
  }
  var style = root.style;
  var num = function (v, lo, hi) { return typeof v === "number" && v >= lo && v <= hi; };
  if (typeof look.title_font === "string" && word.test(look.title_font)) style.setProperty("--title-font", "var(--font-" + look.title_font + ")");
  if (typeof look.text_font === "string" && word.test(look.text_font)) style.setProperty("--text-font", "var(--font-" + look.text_font + ")");
  if (num(look.title_size, 50, 200)) style.setProperty("--title-scale", String(look.title_size / 100));
  if (num(look.text_size, 10, 30)) style.setProperty("--text-size", look.text_size + "px");
  if (num(look.graph_labels, 50, 200)) style.setProperty("--label-scale", String(look.graph_labels / 100));
  // The title effects, as in pages.TITLE_LOOKS: an outline and shadow, nothing, or a sign.
  var plate = ["--title-plate-bg", "--title-plate-border", "--title-plate-shadow", "--title-plate-pad"];
  var effects = {
    poster: ["0.08em", "0.05em 0.06em 0 var(--pal-accent)", "transparent", "0 solid transparent", "none", "0"],
    plain: ["0", "none", "transparent", "0 solid transparent", "none", "0"],
    sign: ["0", "none", "color-mix(in srgb, var(--pal-ink) 88%, transparent)",
      "2px solid color-mix(in srgb, var(--pal-sun) 55%, var(--pal-ink))",
      "0.1em 0.1em 0 color-mix(in srgb, var(--pal-accent) 80%, var(--pal-ink))", "0.1em 0.42em 0.14em"]
  };
  if (Object.prototype.hasOwnProperty.call(effects, look.title_effect)) {
    var names = ["--title-stroke", "--title-shadow"].concat(plate);
    var values = effects[look.title_effect];
    for (var i = 0; i < names.length; i++) style.setProperty(names[i], values[i]);
  }
})();
