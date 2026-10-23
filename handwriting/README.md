# /handwriting — free-form ink → text

Write anything, anywhere: several blocks, at angles, labels, stray marks. Press
**Recognize**. Each text block is transcribed line by line; fix a line and
**Save as training data** keeps the (strokes, text) pair on the device for
fine-tuning later. **Export** downloads all pairs as JSONL.

Everything but the recognizer is in `index.html`:

1. **Specks & rules** — tiny isolated marks and long straight strokes are not text.
2. **Chunks** — strokes cluster into blocks by spatial proximity; a long pause
   between strokes makes the spatial requirement stricter (an edit touches the
   old text, a new block usually doesn't).
3. **Orientation** — per block, snapped to 15°, chosen by a scale-free "how much
   ink fits in one line band" measure plus the principal axis. Small blocks
   (a label) adopt the page's dominant angle unless their own evidence is clear.
4. **Lines** — valleys of the vertical ink-density profile in the rotated frame.
5. **Words** — adaptive gap threshold within each line (letter gaps vs word gaps).
6. **Recognition** — each line is de-rotated and rasterized (dark on white,
   IAM-style) and read by TrOCR-handwritten running in the browser through
   transformers.js. The model's decoder is a language model over the whole line,
   so l/I/1-style ambiguities are resolved from context.
7. **Correction** — edits are stored (IndexedDB) with line-normalised strokes,
   the model's original guess, timestamps and the block's angle.

Model weights are fetched from the Hugging Face hub on first use and cached by
the browser. "TrOCR small" (~80 MB, q8) is the default; "TrOCR base" is better and
~4× larger. WebGPU is used when the browser offers it, WASM otherwise.

Next steps, in order of payoff: fine-tune TrOCR on the exported pairs (a few
hundred lines of one hand moves the needle a lot); n-best decoding plus a
rescoring pass with word-level confidence; feeding block/line context between
stages (neighbouring lines, earlier blocks) into the decoder prompt.
