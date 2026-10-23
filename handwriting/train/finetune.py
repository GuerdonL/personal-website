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
from transformers import TrOCRProcessor, VisionEncoderDecoderModel, Seq2SeqTrainer, Seq2SeqTrainingArguments, default_data_collator, EarlyStoppingCallback
import evaluate

class Lines(Dataset):
    def __init__(self, root, split, processor, max_len=64, keep_bos=True):
        self.root = pathlib.Path(root) / split; self.p = processor; self.max_len = max_len; self.keep_bos = keep_bos
        self.items = [x for x in (l.split('\t', 1) for l in (pathlib.Path(root) / f'{split}.tsv').read_text(encoding='utf-8').splitlines() if l.strip()) if len(x) == 2 and x[1].strip()]
    def __len__(self): return len(self.items)
    def __getitem__(self, i):
        name, text = self.items[i]
        img = Image.open(self.root / name).convert('RGB')
        pv = self.p(images=img, return_tensors='pt').pixel_values.squeeze(0)
        ids = self.p.tokenizer(text, max_length=self.max_len, truncation=True).input_ids
        if not self.keep_bos and ids and ids[0] == self.p.tokenizer.bos_token_id: ids = ids[1:]
        ids = ids + [-100] * (self.max_len - len(ids))
        return {'pixel_values': pv, 'labels': torch.tensor(ids)}

class Trainer(Seq2SeqTrainer):
    """Recent transformers versions route VisionEncoderDecoder through a causal-LM loss that
    shifts the labels a second time, so the targets end up off by one. Compute the loss
    ourselves: shift labels right for the decoder input, cross-entropy against the labels."""
    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs['labels']; cfg = model.config
        dec_in = labels.new_full(labels.shape, cfg.pad_token_id); dec_in[:, 1:] = labels[:, :-1]; dec_in[:, 0] = cfg.decoder_start_token_id
        dec_in = dec_in.masked_fill(dec_in == -100, cfg.pad_token_id)
        out = model(pixel_values=inputs['pixel_values'], decoder_input_ids=dec_in)
        loss = torch.nn.functional.cross_entropy(out.logits.reshape(-1, out.logits.size(-1)), labels.reshape(-1), ignore_index=-100)
        return (loss, out) if return_outputs else loss
    def prediction_step(self, model, inputs, prediction_loss_only, ignore_keys=None, **kw):
        # generation + metrics as usual, but report our loss instead of the double-shifted one
        loss, gen, labels = super().prediction_step(model, inputs, prediction_loss_only, ignore_keys=ignore_keys, **kw)
        with torch.no_grad(): loss = self.compute_loss(model, inputs).detach()
        return loss, gen, labels

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data', default='data'); ap.add_argument('--base', default='microsoft/trocr-small-handwritten'); ap.add_argument('--out', default='model')
    ap.add_argument('--epochs', type=float, default=20); ap.add_argument('--lr', type=float, default=2e-5); ap.add_argument('--bs', type=int, default=8)
    ap.add_argument('--train', default='encoder', choices=['encoder', 'all'], help='encoder: adapt the vision side only (default, best for small data); all: whole model')
    a = ap.parse_args()
    processor = TrOCRProcessor.from_pretrained(a.base); model = VisionEncoderDecoderModel.from_pretrained(a.base)
    # Keep the checkpoint's own special-token setup (TrOCR starts decoding from its EOS id, 2,
    # not from CLS/BOS); overriding it desynchronises training and generation and ruins the model.
    gc = model.generation_config
    if model.config.decoder_start_token_id is None: model.config.decoder_start_token_id = gc.decoder_start_token_id if gc.decoder_start_token_id is not None else processor.tokenizer.eos_token_id
    if model.config.pad_token_id is None: model.config.pad_token_id = processor.tokenizer.pad_token_id
    if model.config.eos_token_id is None: model.config.eos_token_id = processor.tokenizer.eos_token_id
    gc.decoder_start_token_id = model.config.decoder_start_token_id; gc.pad_token_id = model.config.pad_token_id; gc.eos_token_id = model.config.eos_token_id
    gc.max_new_tokens = 64; gc.num_beams = 3; gc.no_repeat_ngram_size = 3; gc.early_stopping = True
    print('special tokens: start', model.config.decoder_start_token_id, 'eos', model.config.eos_token_id, 'pad', model.config.pad_token_id)
    # Probe what this checkpoint actually emits after its start token, and build labels the same way.
    probe = Lines(a.data, 'val' if (pathlib.Path(a.data) / 'val.tsv').read_text().strip() else 'train', processor)
    model.eval()
    with torch.no_grad(): ids = model.generate(probe[0]['pixel_values'].unsqueeze(0), max_new_tokens=12, num_beams=1)[0].tolist()
    keep_bos = len(ids) > 1 and ids[1] == processor.tokenizer.bos_token_id
    print('probe ids:', ids, '→', repr(processor.tokenizer.decode(ids, skip_special_tokens=True)), '| labels', 'keep' if keep_bos else 'drop', '<s>')
    train, val = Lines(a.data, 'train', processor, keep_bos=keep_bos), Lines(a.data, 'val', processor, keep_bos=keep_bos)
    if a.train == 'encoder':   # the decoder is a language model; with little data it memorises your sentences
        for prm in model.decoder.parameters(): prm.requires_grad = False
    print('trainable parameters:', sum(x.numel() for x in model.parameters() if x.requires_grad) // 1_000_000, 'M of', sum(x.numel() for x in model.parameters()) // 1_000_000, 'M')
    cer = evaluate.load('cer'); wer = evaluate.load('wer')
    def metrics(pred):
        ids = pred.predictions; labels = pred.label_ids.copy(); labels[labels == -100] = processor.tokenizer.pad_token_id
        p = processor.batch_decode(ids, skip_special_tokens=True); t = processor.batch_decode(labels, skip_special_tokens=True)
        return {'cer': cer.compute(predictions=p, references=t), 'wer': wer.compute(predictions=p, references=t)}
    args = Seq2SeqTrainingArguments(output_dir=a.out + '_ckpt', per_device_train_batch_size=a.bs, per_device_eval_batch_size=a.bs, num_train_epochs=a.epochs, learning_rate=a.lr,
        warmup_ratio=0.1, weight_decay=0.01, fp16=torch.cuda.is_available(), predict_with_generate=True, eval_strategy='steps', eval_steps=max(10, len(train) // (2 * a.bs)), save_strategy='steps', save_steps=max(10, len(train) // (2 * a.bs)), save_total_limit=2,
        load_best_model_at_end=bool(len(val)), metric_for_best_model='cer', greater_is_better=False, logging_steps=10, report_to=[], remove_unused_columns=False)
    tr = Trainer(model=model, args=args, train_dataset=train, eval_dataset=val if len(val) else None, data_collator=default_data_collator, compute_metrics=metrics if len(val) else None, processing_class=processor,
                        callbacks=[EarlyStoppingCallback(early_stopping_patience=6)] if len(val) else [])
    if len(val): print('before:', tr.evaluate())
    tr.train()
    if len(val): print('after:', tr.evaluate())
    model.save_pretrained(a.out); processor.save_pretrained(a.out); print('saved to', a.out)

if __name__ == '__main__': main()
