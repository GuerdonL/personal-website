#!/usr/bin/env python3
"""Synthetic ink for smoke-testing the pipeline: each character is a fixed little polyline
"glyph" (not real handwriting), words are spaced, and noise is added. If the model can't learn
this, something is broken; if it can, the plumbing works. Not a substitute for IAM-OnDB.

    python synth.py --n 2000 --out synth_train.jsonl
"""
import argparse, json, math, random

def glyph(ch, rng):
    """A deterministic polyline per character, as a list of strokes in a 1×1 box."""
    r = random.Random(ord(ch) * 7919)        # deterministic across processes (hash() is not)
    # one stroke of 3–5 points on a 3×3 grid (distinct, letter-like shapes); a second short stroke for some
    grid = [(x / 2, y / 2) for y in range(3) for x in range(3)]
    k = 3 + ord(ch) % 3
    strokes = [[list(p) for p in r.sample(grid, k)]]
    if ord(ch) % 3 == 0: strokes.append([list(p) for p in r.sample(grid, 2)])
    return strokes

def line(text, rng):
    x = 0.0; strokes = []; t = 0
    for ch in text:
        if ch == ' ': x += 0.7; continue
        w = 0.5 + 0.2 * rng.random()
        for st in glyph(ch, rng):
            pts = [[x + px * w + rng.gauss(0, 0.02), py * 0.8 + 0.1 + rng.gauss(0, 0.02), 0.5] for px, py in st]
            strokes.append({'t0': t, 'pts': pts}); t += 100
        x += w + 0.12
    return {'text': text, 'strokes': strokes}

WORDS = 'the quick brown fox jumps over lazy dog and then runs home to eat some food while it rains outside today tomorrow yesterday hello world notes idea plan meeting call email'.split()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--n', type=int, default=2000); ap.add_argument('--out', required=True); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args(); rng = random.Random(a.seed)
    with open(a.out, 'w', encoding='utf-8') as f:
        for _ in range(a.n):
            words = [rng.choice(WORDS) for _ in range(rng.randint(2, 6))]
            if rng.random() < 0.3: words[0] = words[0].capitalize()
            if rng.random() < 0.3: words[-1] += rng.choice('.,?!')
            f.write(json.dumps(line(' '.join(words), rng)) + '\n')
    print('wrote', a.n, 'lines to', a.out)

if __name__ == '__main__': main()
