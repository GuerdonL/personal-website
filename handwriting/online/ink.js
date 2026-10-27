/* Ink → features in the browser. Mirror of features.py: same normalisation, same resampling,
   same 8 features in the same order. If you change one, change the other and run check.py.

   featurize(strokes) : strokes = [{pts:[{x,y}, …]}, …] (any units, in writing order) → Float32Array [T*8], T
   greedyDecode(logprobs, T, vocab) : CTC collapse of argmax → string
*/
export const N_FEATURES = 8, STEP = 0.05;

export function featurize(strokes) {
  const S = strokes.map(s => s.pts.map(p => [p.x, p.y])).filter(s => s.length);
  if (!S.length) return { data: new Float32Array(N_FEATURES), T: 1 };
  let x0 = Infinity, y0 = Infinity, y1 = -Infinity;
  for (const s of S) for (const [x, y] of s) { if (x < x0) x0 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  const h = Math.max(y1 - y0, 1e-6);
  const N = S.map(s => s.map(([x, y]) => [(x - x0) / h, (y - y0) / h]));
  const chunks = []; let T = 0, prev = null;
  for (const p of N) {
    const q = resample(p, STEP), n = q.length, f = new Float32Array(n * N_FEATURES);
    let pa = 0;
    for (let i = 0; i < n; i++) {
      const dx = i ? q[i][0] - q[i - 1][0] : 0, dy = i ? q[i][1] - q[i - 1][1] : 0;
      let ang = Math.atan2(dy, dx);
      if (i === 0) ang = n > 1 ? Math.atan2(q[1][1] - q[0][1], q[1][0] - q[0][0]) : 0;
      const o = i * N_FEATURES;
      f[o] = dx; f[o + 1] = dy; f[o + 2] = i ? 1 : 0; f[o + 3] = Math.cos(ang); f[o + 4] = Math.sin(ang); f[o + 6] = q[i][1];
      if (i > 0) { let t = ang - pa; t = ((t + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI; f[(i - 1) * N_FEATURES + 5] = t / Math.PI; }
      pa = ang;
    }
    // curvature of the last point: diff with append=last → 0 (already zero)
    if (prev) f[7] = q[0][0] - prev[0];
    prev = q[n - 1]; chunks.push(f); T += n;
  }
  const data = new Float32Array(T * N_FEATURES); let o = 0; for (const c of chunks) { data.set(c, o); o += c.length; }
  return { data, T };
}

function resample(p, step) {
  if (p.length === 1) return [p[0].slice()];
  const cum = [0]; for (let i = 1; i < p.length; i++) cum.push(cum[i - 1] + Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]));
  const L = cum[cum.length - 1]; if (L < 1e-9) return [p[0].slice()];
  const n = Math.max(2, Math.floor(L / step) + 1), out = [];
  let j = 0;
  for (let k = 0; k < n; k++) {
    const t = L * k / (n - 1);
    while (j < cum.length - 2 && cum[j + 1] < t) j++;
    const a = cum[j], b = cum[j + 1], u = b > a ? (t - a) / (b - a) : 0;
    out.push([p[j][0] + (p[j + 1][0] - p[j][0]) * u, p[j][1] + (p[j + 1][1] - p[j][1]) * u]);
  }
  return out;
}

export function greedyDecode(lp, T, vocab) {
  const V = vocab.length; let out = '', prev = 0;
  for (let t = 0; t < T; t++) {
    let best = 0, bv = -Infinity; for (let v = 0; v < V; v++) { const x = lp[t * V + v]; if (x > bv) { bv = x; best = v; } }
    if (best !== prev && best !== 0) out += vocab[best];
    prev = best;
  }
  return out;
}
