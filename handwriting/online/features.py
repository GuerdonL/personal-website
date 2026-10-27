"""Ink → feature sequence for the online recognizer.

Input: one line of ink in the page's pair format: strokes = [{'t0': int, 'pts': [[x, y, p], ...]}, ...]
with coordinates in any consistent unit (the line is re-normalised here: height 1, origin top-left).

Output: float32 array [T, F] with, per resampled point:
    0 dx        step from the previous point (line-height units)
    1 dy
    2 pen       1 if this point continues a stroke, 0 at the first point of a stroke
    3 cos, 4 sin   direction of the step
    5 curv      turning angle to the next step (signed, radians / π)
    6 y         vertical position in the line (0 top .. 1 bottom); ascenders/descenders live here
    7 gap       horizontal distance jumped since the previous stroke ended (0 within a stroke)

Strokes are resampled at uniform arc length (STEP × line height) so the sequence length depends on
how much ink there is, not on how fast it was written. The same code must exist in JS (ink.js);
keep it simple and deterministic for that reason.
"""
import math
import numpy as np

N_FEATURES = 8
STEP = 0.05          # resampling step, in line heights

def normalise(strokes):
    """Shift/scale so the line spans y in [0, 1]; returns list of float arrays [n, 2]."""
    pts = [np.asarray([[p[0], p[1]] for p in s['pts']], dtype=np.float64) for s in strokes if s.get('pts')]
    pts = [p for p in pts if len(p)]
    if not pts: return []
    allp = np.concatenate(pts)
    x0, y0 = allp.min(0); y1 = allp[:, 1].max()
    h = max(y1 - y0, 1e-6)
    return [(p - [x0, y0]) / h for p in pts]

def resample(p, step=STEP):
    """Uniform arc-length resampling of one stroke; keeps the first and last point."""
    if len(p) == 1: return p.copy()
    d = np.linalg.norm(np.diff(p, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(d)])
    L = cum[-1]
    if L < 1e-9: return p[:1].copy()
    n = max(2, int(L / step) + 1)
    t = np.linspace(0, L, n)
    x = np.interp(t, cum, p[:, 0]); y = np.interp(t, cum, p[:, 1])
    return np.stack([x, y], 1)

def featurize(strokes, step=STEP):
    strokes = normalise(strokes)
    if not strokes: return np.zeros((1, N_FEATURES), np.float32)
    # ink order: as written (stroke t0 if present), which is what the browser will also send
    out = []
    prev = None          # last point of the previous stroke
    for p in strokes:
        q = resample(p, step)
        n = len(q)
        f = np.zeros((n, N_FEATURES), np.float32)
        d = np.diff(q, axis=0, prepend=q[:1])            # step vectors; first is 0
        f[:, 0:2] = d
        f[:, 2] = 1.0; f[0, 2] = 0.0
        ang = np.arctan2(d[:, 1], d[:, 0]); ang[0] = ang[1] if n > 1 else 0.0
        f[:, 3] = np.cos(ang); f[:, 4] = np.sin(ang)
        if n > 1:
            turn = np.diff(ang, append=ang[-1:])
            turn = (turn + np.pi) % (2 * np.pi) - np.pi
            f[:, 5] = turn / np.pi
        f[:, 6] = q[:, 1]
        if prev is not None: f[0, 7] = q[0, 0] - prev[0]
        prev = q[-1]
        out.append(f)
    return np.concatenate(out).astype(np.float32)

# ---- augmentation in ink space (train only) ----
def augment(strokes, rng):
    """Slant, scale, rotation, per-point jitter, small per-stroke offsets. Works on the raw pair format."""
    slant = rng.uniform(-0.3, 0.3); sx = rng.uniform(0.8, 1.25); sy = rng.uniform(0.9, 1.1)
    rot = rng.uniform(-0.04, 0.04); c, s = math.cos(rot), math.sin(rot)
    jit = rng.uniform(0, 0.01)
    out = []
    for st in strokes:
        ox, oy = rng.normal(0, 0.01), rng.normal(0, 0.01)
        pts = []
        for p in st['pts']:
            x, y = p[0], p[1]
            x = (x + slant * (0.5 - y)) * sx; y = y * sy
            x, y = c * x - s * y, s * x + c * y
            x += ox + rng.normal(0, jit); y += oy + rng.normal(0, jit)
            pts.append([x, y] + list(p[2:]))
        out.append({**st, 'pts': pts})
    return out

if __name__ == '__main__':
    # tiny self-check on a synthetic 'zigzag' line
    import json, sys
    st = [{'t0': i, 'pts': [[i * 0.4 + k * 0.05, 0.5 + 0.4 * math.sin(k)] for k in range(12)]} for i in range(5)]
    f = featurize(st)
    print(f.shape, f[:3].round(3))
