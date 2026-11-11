// A visitor's own palette (§7b) on the painted background, before it paints. Classic
// script, placed right after the background's SVG and only for visitors: the server
// already wrote the site's recoloring filter; look-early.js put the visitor's palette
// and ramp on <html>, so this swaps the filter's tables (or drops the filter when the
// visitor's palette keeps the painting as it is). Same table as rampFilter in draw.js.
(function () {
  "use strict";
  var own = document.documentElement.dataset;
  if (!own.palette) return;
  var filters = document.querySelectorAll("filter.bg-ramp");
  var ramp = /^#[0-9a-fA-F]{6}( #[0-9a-fA-F]{6}){1,15}$/.test(own.ramp || "") ? own.ramp.split(" ") : null;
  var tables = null;
  if (ramp) {
    var stops = ramp.map(function (c) {
      return [1, 3, 5].map(function (i) { return parseInt(c.slice(i, i + 2), 16) / 255; });
    });
    var n = stops.length - 1;
    var steps = 24;
    tables = [[], [], []];
    for (var i = 0; i <= steps; i++) {
      var t = Math.pow(i / steps, 0.8) * n;
      var j = Math.min(Math.floor(t), n - 1);
      var f = t - j;
      for (var ch = 0; ch < 3; ch++) tables[ch].push((stops[j][ch] + (stops[j + 1][ch] - stops[j][ch]) * f).toFixed(3));
    }
  }
  for (var k = 0; k < filters.length; k++) {
    var filter = filters[k];
    var svg = filter.ownerSVGElement;
    if (!tables) {
      var images = svg ? svg.querySelectorAll("image[filter]") : [];
      for (var m = 0; m < images.length; m++) images[m].removeAttribute("filter");
      continue;
    }
    var funcs = filter.querySelectorAll("feFuncR, feFuncG, feFuncB");
    for (var c = 0; c < funcs.length && c < 3; c++) funcs[c].setAttribute("tableValues", tables[c].join(" "));
  }
})();
