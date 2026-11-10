// The painted background behind every page (§7c). The page already shows the image;
// this only adds the palette's recoloring filter, which is built in the browser.
import { rampFilter } from "./draw.js";

const backdrop = document.getElementById("backdrop");
if (backdrop && backdrop.dataset.ramp) {
  const image = backdrop.querySelector("image");
  const defs = new DOMParser().parseFromString(
    `<svg xmlns="http://www.w3.org/2000/svg"><defs>${rampFilter(backdrop.dataset.ramp.split(" ")).replace('id="bgmap"', 'id="bgmap-page"')}</defs></svg>`,
    "image/svg+xml",
  ).documentElement.firstElementChild;
  backdrop.prepend(document.importNode(defs, true));
  if (image) image.setAttribute("filter", "url(#bgmap-page)");
}
