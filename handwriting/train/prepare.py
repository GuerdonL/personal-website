#!/usr/bin/env python3
"""Turn exported /handwriting pairs (JSONL) into a training set of line images.

    python prepare.py pairs1.jsonl pairs2.jsonl ... --out data --aug 8

Strokes are stored line-normalised (height 1, origin top-left), so augmentation is
done in vector space before rasterising: slant, scale, pen width, small rotation and
per-point jitter. One clean rendering plus --aug augmented ones per line. Lines are
split into train/val by line (15% val, deterministic), never by augmentation copy.
"""
import argparse, json, math, random, unicodedata, pathlib, sys
from PIL import Image, ImageDraw

def norm(s):
    s = unicodedata.normalize('NFKC', s)
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    return ' '.join(s.split())            # no tabs/newlines: the labels go into a TSV, one line each

def usable(r):
    if len(r.get('strokes', [])) < 3: return False                 # stray marks
    t = norm(r.get('text', ''))
    if len(t) < 2 or not any(c.isalpha() for c in t): return False  # no letters → not a real line
    # A line whose strokes drift up or down along its length was two pieces of text at
    # different angles merged by the layout stage; the crop is half-sideways. Skip it.
    cs = [(sum(p[0] for p in s['pts']) / len(s['pts']), sum(p[1] for p in s['pts']) / len(s['pts'])) for s in r['strokes'] if s['pts']]
    cs.sort(); n = len(cs)
    if n >= 6:
        a = sum(y for _, y in cs[: n // 3]) / (n // 3); b = sum(y for _, y in cs[-(n // 3):]) / (n // 3)
        dx = cs[-1][0] - cs[0][0]
        if dx > 0 and abs(b - a) / dx > 0.25: return False          # > ~14° of drift across the line (coords are height-normalised)
    return True

def render(strokes, H=128, pad=18, slant=0.0, scale=1.0, rot=0.0, width=None, jitter=0.0, rng=None, frame=None, min_aspect=2.5):
    """frame: strokes of the whole line, used only for the vertical extent — a word crop then keeps
    the line's letter proportions, exactly as the page rasterizes a word for its alternatives."""
    pts = [(p[0], p[1]) for s in strokes for p in s['pts']]
    if not pts: return None
    cr, sr = math.cos(rot), math.sin(rot)
    def tf(x, y):
        x, y = x + slant * (0.5 - y), y                    # shear about mid-height
        x, y = x * scale, y * scale
        x, y = cr * x - sr * y, sr * x + cr * y
        if jitter and rng: x += rng.gauss(0, jitter); y += rng.gauss(0, jitter)
        return x, y
    T = [[tf(p[0], p[1]) for p in s['pts']] for s in strokes]
    xs = [x for s in T for x, _ in s]; ys = [y for s in T for _, y in s]
    if frame: ys = [tf(p[0], p[1])[1] for s in frame for p in s['pts']]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sc = (H - 2 * pad) / max(y1 - y0, 1e-6)
    W = max(int(H * min_aspect), int((x1 - x0) * sc + 2 * pad))
    im = Image.new('L', (W, H), 255); d = ImageDraw.Draw(im)
    lw = width if width else max(2, min(5, int(sc * 0.055)))
    for s in T:
        xy = [(pad + (x - x0) * sc, pad + (y - y0) * sc) for x, y in s]
        if len(xy) > 1: d.line(xy, fill=0, width=lw, joint='curve')
        else: d.ellipse([xy[0][0] - lw / 2, xy[0][1] - lw / 2, xy[0][0] + lw / 2, xy[0][1] + lw / 2], fill=0)
    return im

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('files', nargs='+'); ap.add_argument('--out', default='data'); ap.add_argument('--aug', type=int, default=8); ap.add_argument('--val', type=float, default=0.15); ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--words', type=int, default=2, help='augmented word crops per corrected word (0 = lines only); word crops go to train only, so val CER stays comparable')
    a = ap.parse_args(); rng = random.Random(a.seed)
    rows = []
    for f in a.files:
        for l in open(f, encoding='utf-8'):
            if l.strip():
                r = json.loads(l)
                if usable(r): rows.append(r)
    # dedupe: the same ink is synced again every time its correction changes, so keep only the
    # NEWEST version of each stroke set (by t0 list + device); older exports without t0s fall back to content
    best = {}
    for r in rows:
        ts = tuple(s.get('t0') for s in r['strokes'])
        k = ('t0', r.get('device', ''), ts) if all(t is not None for t in ts) else ('c', norm(r['text']), len(r['strokes']), round(sum(p[0] for s in r['strokes'] for p in s['pts']), 2))
        if k not in best or r.get('ts', 0) >= best[k].get('ts', 0): best[k] = r
    rows = list(best.values()); rows.sort(key=lambda r: r.get('ts', 0))
    rng.shuffle(rows); nval = max(1, int(len(rows) * a.val)) if len(rows) >= 6 else 0
    out = pathlib.Path(a.out); (out / 'train').mkdir(parents=True, exist_ok=True); (out / 'val').mkdir(parents=True, exist_ok=True)
    tsv = {'train': [], 'val': []}
    for i, r in enumerate(rows):
        split = 'val' if i < nval else 'train'; text = norm(r['text'])
        n = 1 if split == 'val' else 1 + a.aug
        for k in range(n):
            if k == 0: im = render(r['strokes'])
            else: im = render(r['strokes'], slant=rng.uniform(-0.25, 0.25), scale=rng.uniform(0.85, 1.15), rot=rng.uniform(-0.03, 0.03), width=rng.choice([2, 3, 3, 4, 5]), jitter=rng.uniform(0, 0.012), rng=rng)
            name = f'{i:05d}_{k}.png'; im.save(out / split / name); tsv[split].append(f'{name}\t{text}')
        # word-level pairs from the page's X / typed corrections: each word owns its strokes (by t0)
        if split == 'train' and a.words and r.get('words'):
            by_t0 = {s['t0']: s for s in r['strokes']}
            for wi, w in enumerate(r['words']):
                wt = norm(w.get('text', '')); ws = [by_t0[t] for t in w.get('strokes', []) if t in by_t0]
                if not wt or not ws or not any(ch.isalnum() for ch in wt): continue
                for k in range(1 + a.words):
                    if k == 0: im = render(ws, frame=r['strokes'], min_aspect=1.2)
                    else: im = render(ws, frame=r['strokes'], min_aspect=1.2, slant=rng.uniform(-0.25, 0.25), scale=rng.uniform(0.85, 1.15), rot=rng.uniform(-0.03, 0.03), width=rng.choice([2, 3, 3, 4, 5]), jitter=rng.uniform(0, 0.012), rng=rng)
                    if im is None: continue
                    name = f'{i:05d}_w{wi}_{k}.png'; im.save(out / split / name); tsv[split].append(f'{name}\t{wt}')
    for s in tsv: (out / f'{s}.tsv').write_text('\n'.join(tsv[s]) + '\n', encoding='utf-8')
    print(f'{len(rows)} lines → train {len(tsv["train"])} images, val {len(tsv["val"])} images in {out}/')

if __name__ == '__main__': main()
