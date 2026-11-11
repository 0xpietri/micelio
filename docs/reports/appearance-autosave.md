# Report: Appearance saves itself

Date: 2026-11-11

## Asked

marcos: choosing something on the Appearance page (a palette, the background, anything)
applies at once with no Save button; "Make your own background" folded; a click outside
the Appearance panel leaves it; an empty tagline shows nothing instead of the default.

## Done

- `static/js/appearance.js`: every change posts the form with `Accept: application/json`
  (text after 0.8 s without typing). The server answers JSON with the new background, and
  the page swaps `/theme.css` and repaints the background and its recolor filter without
  reloading. A status line says "Saved" or that it failed. The Save buttons get
  `save-fallback` and are hidden by the script, so the page still works without
  JavaScript. A chosen image uploads at once.
- `landing_web.py`: `POST /appearance` answers JSON (`{"ok", "backdrop"}`, or 403 without
  the token) when asked for it; plain form posts still redirect.
- The prompt guide is a `<details>`, folded.
- A click on the painting around the panel (not on the header, a link or a control)
  waits for any pending save and goes back to the page the owner came from, else `/`.
  A short line under the lead says so.
- `Appearance.tagline` is `None` until saved; once saved, `""` means no tagline. The
  field starts with the default text, so saving other things does not wipe it.

## Tests

`tests/test_appearance_autosave.py`: JSON save and repaint data, refusal without the
token, plain posts still redirect, the page markup, the empty tagline. Checked by hand in
Chromium: picking Tokyo Night repaints the page at once, emptying the tagline saves, a
click outside goes back. All checks pass (320 tests).
