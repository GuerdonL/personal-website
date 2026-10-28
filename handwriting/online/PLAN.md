# Online handwriting recognizer — plan

Goal: writing on /handwriting (later /notes) is recognized by a small **stroke-based** model
running in the browser, decoded with a language model so readings fit their context, trained on
public ink data and fine-tuned on Guerdon's own corrections through the existing
sync → Kaggle → Hugging Face loop. MVP bar: beats TrOCR's CER on a held-out 50 lines of his writing.

Everything lives in `handwriting/online/`. One pair format throughout (the page's JSONL):
`{text, strokes:[{t0, pts:[[x, y, p], …]}]}` with coordinates normalised so the line is height 1.

## Phases and gates

| # | Phase | Deliverable | Gate to pass |
|---|-------|-------------|--------------|
| 0 | Feasibility | `features.py`, `model.py`, `train.py`; smoke-tested on synthetic ink | scripts run end to end on CPU |
| 1 | General model | IAM-OnDB loader; BiLSTM-CTC trained on Kaggle | < 15 % CER on IAM-OnDB test without tuning (else fix features before anything else) |
| 2 | Personal model | fine-tune on synced pairs; 50-line personal holdout never trained on | CER on holdout < TrOCR's |
| 3 | In the browser | ONNX export; `ink.js` features + greedy CTC decode in a Web Worker; selectable in the model menu | < 100 ms per line on the iPad |
| 4 | Context | CTC beam search with a char n-gram LM (general text + his synced text); n-best feeds the X gesture; previous line as LM prefix | X alternatives are real readings; fewer nonsense words |
| 5 | Symbols & gestures | symbol tokens (→ • □ ✓) from a quick collection page; gesture layer stays rule-based | symbols recognised; gestures never reach the model |
| 6 | Loop & /notes | `train.py --kind online` on Kaggle, same publish gate; shared module for /notes | weekly retrain publishes; /notes shows live labels |

## Division of labour

Claude writes code, tests on synthetic data here, pushes; Guerdon does what needs an account or a
device: download IAM-OnDB (registration), run Kaggle, test on the iPad, collect symbols, judge
readings. Every phase ends with a number (CER / latency) before the next starts.

## Design decisions (so they don't get re-litigated)

- Features per point: Δx, Δy, pen-down, direction (cos, sin), curvature, normalised y, pen-up gap length.
  Strokes resampled at uniform arc length (~1/20 line height). Bézier fitting (Google) deferred: it
  shortens sequences but adds a fitting step in JS; resampling is good enough for the MVP.
- Model: 2-layer BiLSTM, hidden 192, CTC over ~90 characters + symbol tokens. ≈2 M params. A
  transformer encoder is a drop-in later if the LSTM plateaus.
- Decoding: greedy in the browser first; beam + n-gram LM in phase 4, also in JS.
- Training on Kaggle, same `train.py` entry point; `--kind online` branch.
- Personal holdout: the 50 oldest synced lines, fixed by stroke-set hash, excluded from training forever.

## Status

- [x] 0 feasibility scripts — synthetic alphabet: 0.2 % CER by epoch 20; ONNX matches torch to 1e-5; browser path 129 ms/line on CPU
- [ ] 1 IAM-OnDB → general model
- [ ] 2 personal model
- [~] 3 browser — worker + menu entry done; latency on the iPad still to measure
- [ ] 4 context
- [ ] 5 symbols
- [ ] 6 loop & /notes
