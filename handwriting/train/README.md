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
