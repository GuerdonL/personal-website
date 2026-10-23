#!/usr/bin/env python3
"""Fine-tune TrOCR on the line images from prepare.py.

    pip install "transformers>=4.44" datasets accelerate evaluate jiwer pillow torch
    python finetune.py --data data --base microsoft/trocr-small-handwritten --out model --epochs 20

Runs on a free Colab T4 in ~10–20 minutes for a few hundred augmented images.
Picks the checkpoint with the lowest validation CER.
"""
import argparse, pathlib, torch
from PIL import Image
from torch.utils.data import Dataset
from transformers import TrOCRProcessor, VisionEncoderDecoderModel, Seq2SeqTrainer, Seq2SeqTrainingArguments, default_data_collator
import evaluate

class Lines(Dataset):
    def __init__(self, root, split, processor, max_len=64):
        self.root = pathlib.Path(root) / split; self.p = processor; self.max_len = max_len
        self.items = [l.split('\t', 1) for l in (pathlib.Path(root) / f'{split}.tsv').read_text(encoding='utf-8').splitlines() if l.strip()]
    def __len__(self): return len(self.items)
    def __getitem__(self, i):
        name, text = self.items[i]
        img = Image.open(self.root / name).convert('RGB')
        pv = self.p(images=img, return_tensors='pt').pixel_values.squeeze(0)
        ids = self.p.tokenizer(text, padding='max_length', max_length=self.max_len, truncation=True).input_ids
        ids = [t if t != self.p.tokenizer.pad_token_id else -100 for t in ids]
        return {'pixel_values': pv, 'labels': torch.tensor(ids)}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data', default='data'); ap.add_argument('--base', default='microsoft/trocr-small-handwritten'); ap.add_argument('--out', default='model')
    ap.add_argument('--epochs', type=float, default=20); ap.add_argument('--lr', type=float, default=5e-5); ap.add_argument('--bs', type=int, default=8)
    a = ap.parse_args()
    processor = TrOCRProcessor.from_pretrained(a.base); model = VisionEncoderDecoderModel.from_pretrained(a.base)
    model.config.decoder_start_token_id = processor.tokenizer.cls_token_id or processor.tokenizer.bos_token_id
    model.config.pad_token_id = processor.tokenizer.pad_token_id; model.config.eos_token_id = processor.tokenizer.sep_token_id or processor.tokenizer.eos_token_id
    model.generation_config.max_new_tokens = 64; model.generation_config.num_beams = 3; model.generation_config.no_repeat_ngram_size = 3
    train, val = Lines(a.data, 'train', processor), Lines(a.data, 'val', processor)
    cer = evaluate.load('cer'); wer = evaluate.load('wer')
    def metrics(pred):
        ids = pred.predictions; labels = pred.label_ids.copy(); labels[labels == -100] = processor.tokenizer.pad_token_id
        p = processor.batch_decode(ids, skip_special_tokens=True); t = processor.batch_decode(labels, skip_special_tokens=True)
        return {'cer': cer.compute(predictions=p, references=t), 'wer': wer.compute(predictions=p, references=t)}
    args = Seq2SeqTrainingArguments(output_dir=a.out + '_ckpt', per_device_train_batch_size=a.bs, per_device_eval_batch_size=a.bs, num_train_epochs=a.epochs, learning_rate=a.lr,
        warmup_ratio=0.1, weight_decay=0.01, fp16=torch.cuda.is_available(), predict_with_generate=True, eval_strategy='epoch', save_strategy='epoch', save_total_limit=2,
        load_best_model_at_end=bool(len(val)), metric_for_best_model='cer', greater_is_better=False, logging_steps=10, report_to=[], remove_unused_columns=False)
    tr = Seq2SeqTrainer(model=model, args=args, train_dataset=train, eval_dataset=val if len(val) else None, data_collator=default_data_collator, compute_metrics=metrics if len(val) else None, processing_class=processor)
    if len(val): print('before:', tr.evaluate())
    tr.train()
    if len(val): print('after:', tr.evaluate())
    model.save_pretrained(a.out); processor.save_pretrained(a.out); print('saved to', a.out)

if __name__ == '__main__': main()
