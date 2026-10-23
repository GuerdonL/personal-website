# /scribe — handwriting → tidied pseudo-handwriting

A test page. You are shown a sentence, you write it anywhere on the canvas with a
stylus (any size, any line breaks, letters joined or not), and the page fits a
connected cursive Bézier version of that sentence onto your ink. Everything runs
in the browser; nothing leaves the device.

Files

- `alphabet.js` — the ideal hand: every glyph as cubic Béziers in x-height units,
  with a lead-in upstroke that doubles as the connector, an exit point, and an
  advance width. Edit it freely.
- `index.html` — the page and the whole pipeline.

Pipeline (all in `index.html`, numbered sections)

1. **Lines.** Strokes cluster by vertical centre; small marks (i-dots, t-crosses)
   are folded into the nearest real line. Baseline and x-height come from the
   vertical ink-density profile (the x-height band holds most of the ink).
2. **Forced alignment.** Because the text is known, nothing is *recognised*. Words
   are distributed over ink lines by a DP that matches expected widths (template
   advances) to measured line widths. Inside a line, blank columns are matched to
   word gaps (another small DP, so cramped gaps still work). Inside a word, letters
   get x-windows proportional to their advance, snapped to coverage minima.
   Stroke segmentation is never needed, so one stroke spanning several letters, or
   one letter made of several strokes, is fine.
3. **Fit.** Each letter starts as the ideal glyph placed in its window, welded to
   its neighbour. Ten iterations of weighted affine ICP (size, slant, position),
   then ~30 iterations moving the Bézier control nodes themselves toward the ink
   (both directions: curve→ink and ink→curve), with a pull back to the ideal shape
   and G1 continuity kept where the ideal was smooth.
4. **Tidy slider.** 0 = your fitted hand. Up to 0.6 the shapes relax toward the
   ideal letter at your size/slant/position; from 0.4 to 1 letters also move onto
   one baseline, one size, one slant, even spacing, and a guaranteed word gap.
5. **Learning.** After a good fit, each letter's fitted nodes are mapped back into
   glyph space and averaged into a personal alphabet (localStorage), along with the
   width you give that letter. Later fits start from your alphabet, and the width
   estimates in step 2 use your widths. *Export* downloads the alphabet and the
   last 30 samples as JSON; *Forget* clears both.

Status line: `fit a → b xh` is the symmetric mean distance between the curve and
your ink before/after fitting, in x-heights.
