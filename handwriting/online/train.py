#!/usr/bin/env python3
"""Train / fine-tune the online recognizer.

    python train.py --train general.jsonl --val general_val.jsonl --out model_general.pt --epochs 30
    python train.py --train mine.jsonl --val mine_holdout.jsonl --init model_general.pt --out model_mine.pt --epochs 40 --lr 3e-4

Data: JSONL in the page's pair format ({text, strokes:[{t0, pts:[[x,y,p],…]}]}); any scale.
Prints CER/WER on --val each epoch and keeps the best checkpoint. --export writes ONNX for the browser.
"""
import argparse, json, math, random, time, pathlib, sys
import numpy as np, torch, torch.nn as nn
from features import featurize, augment, N_FEATURES
from model import InkRecognizer, VOCAB, encode, decode_greedy

def load(path):
    rows = []
    for l in open(path, encoding='utf-8'):
        if l.strip():
            r = json.loads(l)
            if r.get('text', '').strip() and r.get('strokes'): rows.append(r)
    return rows

class Ink(torch.utils.data.Dataset):
    def __init__(self, rows, train):
        self.rows, self.train = rows, train; self.rng = np.random.default_rng(0)
    def __len__(self): return len(self.rows)
    def __getitem__(self, i):
        r = self.rows[i]; st = augment(r['strokes'], self.rng) if self.train else r['strokes']
        return torch.from_numpy(featurize(st)), torch.tensor(encode(r['text']), dtype=torch.long), r['text']

def collate(b):
    xs, ys, ts = zip(*b)
    xl = torch.tensor([len(x) for x in xs]); yl = torch.tensor([len(y) for y in ys])
    X = nn.utils.rnn.pad_sequence(xs, batch_first=True); Y = torch.cat(ys)
    return X, xl, Y, yl, ts

def edit(a, b):
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[-1]

@torch.no_grad()
def evaluate(model, dl, dev, show=0):
    model.eval(); ce = cn = we = wn = 0; shown = 0
    for X, xl, Y, yl, ts in dl:
        lp = model(X.to(dev), xl.to(dev)).argmax(-1).cpu(); ol = model.out_lengths(xl)
        for k, t in enumerate(ts):
            h = decode_greedy(lp[k, :ol[k]].tolist())
            ce += edit(h, t); cn += len(t); we += edit(h.split(), t.split()); wn += len(t.split())
            if shown < show: print(f'   {t!r} → {h!r}'); shown += 1
    return ce / max(1, cn), we / max(1, wn)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train', required=True); ap.add_argument('--val'); ap.add_argument('--out', default='model.pt'); ap.add_argument('--init')
    ap.add_argument('--epochs', type=int, default=30); ap.add_argument('--bs', type=int, default=32); ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--hidden', type=int, default=192); ap.add_argument('--layers', type=int, default=2); ap.add_argument('--export'); ap.add_argument('--report'); ap.add_argument('--patience', type=int, default=8)
    a = ap.parse_args()
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'; torch.manual_seed(0); random.seed(0)
    tr = load(a.train); va = load(a.val) if a.val else []
    print(f'{len(tr)} train lines, {len(va)} val lines, device {dev}')
    dtr = torch.utils.data.DataLoader(Ink(tr, True), batch_size=a.bs, shuffle=True, collate_fn=collate, num_workers=2)
    dva = torch.utils.data.DataLoader(Ink(va, False), batch_size=a.bs, collate_fn=collate) if va else None
    model = InkRecognizer(hidden=a.hidden, layers=a.layers).to(dev)
    if a.init: model.load_state_dict(torch.load(a.init, map_location=dev)); print('initialised from', a.init)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-2)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=a.epochs * len(dtr), pct_start=0.15)
    ctc = nn.CTCLoss(blank=0, zero_infinity=True)
    best = (math.inf, None); since = 0
    before = evaluate(model, dva, dev) if dva else None
    if before: print(f'before: CER {before[0]:.3f} WER {before[1]:.3f}')
    for ep in range(1, a.epochs + 1):
        model.train(); tot = 0; t0 = time.time()
        for X, xl, Y, yl, _ in dtr:
            lp = model(X.to(dev), xl.to(dev))                      # [B,T,V]
            loss = ctc(lp.transpose(0, 1), Y.to(dev), model.out_lengths(xl).clamp(max=lp.shape[1]).to(dev), yl.to(dev))
            opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 5.0); opt.step(); sched.step(); tot += loss.item()
        msg = f'epoch {ep:3d} loss {tot / len(dtr):.3f} {time.time() - t0:.0f}s'
        if dva:
            cer, wer = evaluate(model, dva, dev, show=2 if ep % 5 == 0 else 0); msg += f' | val CER {cer:.3f} WER {wer:.3f}'
            if cer < best[0]: best = (cer, ep); torch.save(model.state_dict(), a.out); since = 0; msg += ' *'
            else: since += 1
        else: torch.save(model.state_dict(), a.out)
        print(msg, flush=True)
        if dva and since >= a.patience: print('early stop'); break
    if dva:
        model.load_state_dict(torch.load(a.out, map_location=dev)); after = evaluate(model, dva, dev)
        print(f'best epoch {best[1]}: CER {after[0]:.3f} WER {after[1]:.3f}')
        if a.report: pathlib.Path(a.report).write_text(json.dumps({'before': {'eval_cer': before[0], 'eval_wer': before[1]}, 'after': {'eval_cer': after[0], 'eval_wer': after[1]}, 'train': len(tr), 'val': len(va), 'kind': 'online', 'hidden': a.hidden, 'layers': a.layers}, indent=1))
    if a.export: export(model.cpu(), a.export)

def export(model, path):
    model.eval()
    x = torch.randn(1, 40, N_FEATURES)
    torch.onnx.export(model, (x,), path, input_names=['features'], output_names=['logprobs'], dynamic_axes={'features': {0: 'batch', 1: 'time'}, 'logprobs': {0: 'batch', 1: 'time'}}, opset_version=17, dynamo=False)
    json.dump({'vocab': VOCAB, 'n_features': N_FEATURES}, open(str(path) + '.json', 'w'), ensure_ascii=False)
    print('exported', path, 'and', str(path) + '.json')

if __name__ == '__main__': main()
