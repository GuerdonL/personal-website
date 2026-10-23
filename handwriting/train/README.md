# Fine-tuning the /handwriting recognizer on your own hand

1. On the page: **Export** (or **Copy data**) → one or more `*.jsonl` files.
2. Open a Colab notebook with a GPU runtime and run:

   ```bash
   pip install "transformers>=4.44" datasets accelerate evaluate jiwer pillow torch "optimum[onnxruntime]" huggingface_hub
   python prepare.py pairs-*.jsonl --out data --aug 8
   python finetune.py --data data --base microsoft/trocr-small-handwritten --out model --epochs 20
   huggingface-cli login
   ./export.sh model <your-hf-user>/trocr-yourname
   ```

   `prepare.py` also cuts word crops out of lines that carry per-word corrections (from
   the page's X gesture / word box) and adds them to the training split (`--words 0` to
   skip). Rejected guesses are stored in the JSONL (`words[].rejected`) but not yet used.

   `finetune.py` prints validation CER/WER before and after. Use `--base microsoft/trocr-base-handwritten`
   for the stronger model once you have a few hundred lines (needs the T4's full memory: `--bs 4`).

3. On the page, choose **custom…** in the model menu and enter `<your-hf-user>/trocr-yourname`.

Baseline on the first 37 real lines (stock `trocr-small-handwritten`): CER 7.1 %, WER 17.1 %.
Keep correcting lines on the page and re-run every few hundred new lines; the scripts
dedupe repeated exports, so just pass all the files each time.

## Hands-off loop: page → Worker → private dataset → Kaggle GPU → hub → page

```
/handwriting ──Sync──▶ Cloudflare Worker (sync/worker.js) ──commit──▶ HF dataset  <hf-user>/handwriting-pairs  (private)
                                                                           │
GitHub Actions (train.yml, Sundays or manual) ──kaggle kernels push──▶ Kaggle GPU runs kaggle/train.py
      prepare.py → finetune.py → publish to HF model <hf-user>/trocr-guerdon only if val CER improved
                                                                           │
/handwriting model menu "mine" loads <hf-user>/trocr-guerdon ◀─────────────┘
```

- **Page**: ⚙ next to Sync stores the Worker URL and passphrase in the browser (never in the repo).
  Sync runs on the button, quietly after the idle autosave, and on Clear. Only new or changed
  pairs are sent; the trainer keeps the newest version of each stroke set.
- **Worker**: `cd handwriting/sync && npx wrangler deploy`, then `npx wrangler secret put HF_TOKEN`
  and `npx wrangler secret put PASSPHRASE`. Set `DATASET_REPO` / `ALLOWED_ORIGIN` in `wrangler.toml`.
- **Kaggle**: the kernel is `kaggle/train.py`; the workflow fills `kernel-metadata.json` from the
  `KAGGLE_USERNAME` secret. The kernel reads `HF_TOKEN` from Kaggle *Secrets* (attach it to the
  notebook once, after the first push creates it).
- **GitHub secrets**: `KAGGLE_USERNAME` (your Kaggle handle, used in the kernel id) and `KAGGLE_API_TOKEN` (Settings → API → new-style token). Run it by hand from the Actions tab
  ("Train handwriting model" → Run workflow; tick *force publish* for the very first model).
- The published model carries its `report.json` (before/after CER, data size), so each run can
  compare against what is live.
