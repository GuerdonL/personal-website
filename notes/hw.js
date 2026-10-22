/* hw.js — handwriting recognition + "tidy" for the notes app.
   Everything runs on-device. Strokes are {points:[{x,y,p}], ...} in page units.

   Pipeline (HW.tidy):
     1. segment strokes into characters (spatial overlap + drawing order)
     2. cluster characters into lines, order left→right
     3. recognise each character against ideal glyph templates with a point-cloud
        matcher ($P, Vatavu/Anthony/Wobbrock 2012) — case/digit ambiguity is
        resolved afterwards from the character's height relative to its line
     4. inline: align every character to a baseline fitted through the line,
        scale it gently toward the line's x-height, even out spacing a little
     5. shape: smooth, and blend each stroke a little toward the matched glyph
   Recognised characters are returned as text too, but the ink is never replaced.
*/
(function (root) {
'use strict';

/* ---------------- ideal glyph templates ----------------
   Coordinates: ascender top y=0, x-height top y=35, baseline y=70, descender y=100.
   L(x,y,x,y,...) polyline · A(cx,cy,rx,ry,a0,a1) elliptical arc, degrees, y-down,
   '+' joins pieces into one stroke, ';' separates strokes. */
const GLYPH_SRC = {
  a: 'A(28,52,18,18,20,340);L(46,35,46,70)',
  b: 'L(10,0,10,70);A(28,52,18,18,100,-100)',
  c: 'A(28,52,18,18,40,320)',
  d: 'L(46,0,46,70);A(28,52,18,18,20,340)',
  e: 'L(10,52,46,52)+A(28,52,18,18,0,-300)',
  f: 'L(42,4,34,0,24,6,22,16,22,70);L(8,35,38,35)',
  g: 'A(28,52,18,18,20,340);L(46,35,46,84)+A(30,84,16,14,0,120)',
  h: 'L(10,0,10,70,10,52)+A(28,52,18,16,180,360)+L(46,52,46,70)',
  i: 'L(28,35,28,70);L(28,20,28,23)',
  j: 'L(32,35,32,84)+A(18,84,14,14,0,120);L(32,20,32,23)',
  k: 'L(10,0,10,70);L(40,35,12,56,42,70)',
  l: 'L(28,0,28,70)',
  m: 'L(6,70,6,35)+A(18,47,12,12,180,360)+L(30,47,30,70,30,47)+A(42,47,12,12,180,360)+L(54,47,54,70)',
  n: 'L(10,70,10,35)+A(28,47,18,12,180,360)+L(46,47,46,70)',
  o: 'A(28,52,18,18,-90,270)',
  p: 'L(10,35,10,100);A(28,52,18,18,-100,100)',
  q: 'A(28,52,18,18,20,340);L(46,35,46,100)',
  r: 'L(10,70,10,35)+A(28,47,18,12,180,330)',
  s: 'L(44,40,36,35,22,36,16,44,22,52,36,56,44,62,40,69,24,71,12,65)',
  t: 'L(28,10,28,60)+A(38,60,10,10,180,90);L(14,35,42,35)',
  u: 'L(10,35,10,58)+A(28,58,18,12,180,360)+L(46,58,46,35,46,70)',
  v: 'L(8,35,28,70,48,35)',
  w: 'L(4,35,18,70,30,45,42,70,56,35)',
  x: 'L(8,35,48,70);L(48,35,8,70)',
  y: 'L(8,35,28,70);L(48,35,24,100)',
  z: 'L(8,35,48,35,8,70,48,70)',
  A: 'L(4,70,30,0,56,70);L(16,44,44,44)',
  B: 'L(8,0,8,70);L(8,0,34,0)+A(34,17,16,17,-90,90)+L(34,34,8,34,36,34)+A(36,52,18,18,-90,90)+L(36,70,8,70)',
  C: 'A(32,35,28,35,50,310)',
  D: 'L(8,0,8,70);L(8,0,24,0)+A(24,35,32,35,-90,90)+L(24,70,8,70)',
  E: 'L(50,0,8,0,8,70,50,70);L(8,35,40,35)',
  F: 'L(50,0,8,0,8,70);L(8,35,40,35)',
  G: 'A(32,35,28,35,-40,-330)+L(60,38,36,38)',
  H: 'L(8,0,8,70);L(52,0,52,70);L(8,35,52,35)',
  I: 'L(30,0,30,70)',
  J: 'L(44,0,44,52)+A(26,52,18,18,0,120)',
  K: 'L(8,0,8,70);L(52,0,8,38,52,70)',
  L: 'L(8,0,8,70,50,70)',
  M: 'L(4,70,4,0,30,50,56,0,56,70)',
  N: 'L(8,70,8,0,52,70,52,0)',
  O: 'A(30,35,26,35,-90,270)',
  P: 'L(8,70,8,0);L(8,0,34,0)+A(34,19,18,19,-90,90)+L(34,38,8,38)',
  Q: 'A(30,35,26,35,-90,270);L(36,52,56,76)',
  R: 'L(8,70,8,0);L(8,0,34,0)+A(34,19,18,19,-90,90)+L(34,38,8,38);L(26,38,54,70)',
  S: 'L(52,8,40,0,20,0,10,10,14,24,30,34,46,44,50,58,40,70,20,70,8,62)',
  T: 'L(4,0,56,0);L(30,0,30,70)',
  U: 'L(8,0,8,50)+A(30,50,22,20,180,360)+L(52,50,52,0)',
  V: 'L(4,0,30,70,56,0)',
  W: 'L(0,0,15,70,30,25,45,70,60,0)',
  X: 'L(6,0,54,70);L(54,0,6,70)',
  Y: 'L(6,0,30,36,54,0);L(30,36,30,70)',
  Z: 'L(6,0,54,0,6,70,54,70)',
  0: 'A(30,35,20,35,-90,270)',
  1: 'L(18,14,30,0,30,70)',
  2: 'A(30,18,20,18,-160,40)+L(44,32,8,70,52,70)',
  3: 'A(30,17,18,17,-150,90)+A(30,52,20,18,-90,150)',
  4: 'L(40,0,8,48,54,48);L(40,20,40,70)',
  5: 'L(50,0,14,0,10,32,30,28)+A(32,49,20,21,-90,160)',
  6: 'L(46,2,24,24,12,48)+A(30,50,18,20,180,-180)',
  7: 'L(6,0,54,0,24,70)',
  8: 'A(30,18,16,18,-90,270)+A(30,52,19,18,-90,-450)',
  9: 'A(30,20,18,20,0,360)+L(48,20,46,42,26,70)',
  '.': 'L(30,66,30,70)',
  ',': 'L(30,64,30,74,24,82)',
  '-': 'L(10,52,50,52)',
  '!': 'L(30,0,30,52);L(30,64,30,70)',
  '?': 'A(30,18,18,18,-180,60)+L(39,33,30,42,30,52);L(30,64,30,70)',
  /* common alternative ways of writing the same letter ("ch#n") */
  'a#2': 'A(28,52,18,18,20,340)+L(46,35,46,70)',
  'b#2': 'L(10,0,10,70)+A(28,52,18,18,90,-90)',
  'd#2': 'A(28,52,18,18,20,340)+L(46,0,46,70)',
  'g#2': 'A(28,52,18,18,20,340)+L(46,35,46,84)+A(30,84,16,14,0,120)',
  'h#2': 'L(10,0,10,70);A(28,52,18,16,180,360)+L(46,52,46,70)',
  'm#2': 'L(6,35,6,70);A(18,47,12,12,180,360)+L(30,47,30,70,30,47)+A(42,47,12,12,180,360)+L(54,47,54,70)',
  'n#2': 'L(10,35,10,70);A(28,47,18,12,180,360)+L(46,47,46,70)',
  'p#2': 'L(10,35,10,100,10,52)+A(28,52,18,18,180,540)',
  'q#2': 'A(28,52,18,18,20,340)+L(46,35,46,100)',
  'r#2': 'L(10,35,10,70);A(28,47,18,12,180,330)',
  't#2': 'L(28,10,28,70);L(14,35,42,35)',
  'u#2': 'L(10,35,10,58)+A(28,58,18,12,180,360)+L(46,58,46,35);L(46,35,46,70)',
  'y#2': 'L(8,35,24,70);L(48,35,48,70)+A(34,70,14,14,0,180)',
  'k#2': 'L(10,0,10,70);L(40,35,12,56);L(20,50,42,70)',
  'f#2': 'L(42,4,34,0,24,6,22,16,22,70)',
  'B#2': 'L(8,0,8,70);L(8,0,34,0)+A(34,17,16,17,-90,90)+L(34,34,8,34);L(8,34,36,34)+A(36,52,18,18,-90,90)+L(36,70,8,70)',
  'A#2': 'L(4,70,30,0);L(30,0,56,70);L(16,44,44,44)',
  'M#2': 'L(4,70,4,0);L(4,0,30,50,56,0);L(56,0,56,70)',
  'N#2': 'L(8,70,8,0);L(8,0,52,70);L(52,70,52,0)',
  'E#2': 'L(50,0,8,0);L(8,0,8,70);L(8,70,50,70);L(8,35,40,35)',
  '1#2': 'L(30,0,30,70)',
  '1#3': 'L(18,14,30,0,30,70);L(14,70,46,70)',
  '4#2': 'L(8,0,8,40,54,40);L(40,0,40,70)',
  '7#2': 'L(6,0,54,0,24,70);L(14,36,40,36)',
  '9#2': 'A(30,20,18,20,0,360)+L(48,20,48,70)',
  'z#2': 'L(8,35,48,35,8,70,48,70);L(16,52,40,52)',
  'x#2': 'L(8,35,48,70);L(48,35,8,70)',
};
/* shapes that are the same glyph at two sizes: decided by height, not by matching */
const CASE_PAIRS = { c: 'C', o: 'O', s: 'S', v: 'V', w: 'W', x: 'X', z: 'Z', k: 'K', p: 'P', u: 'U', j: 'J', y: 'Y', l: 'I', i: 'l' };
const DIGIT_TWINS = { O: '0', I: '1', l: '1' };
const X_HEIGHT = new Set('aceimnorsuvwxz');          // sit between x-height and baseline
const DESCENDERS = new Set('gjpqy,');

function parseGlyph(src) {
  return src.split(';').map(strokeSrc => {
    const pts = [];
    for (const piece of strokeSrc.split('+')) {
      const m = piece.match(/^([LA])\(([^)]*)\)$/); const v = m[2].split(',').map(Number);
      if (m[1] === 'L') for (let i = 0; i < v.length; i += 2) pts.push({ x: v[i], y: v[i + 1] });
      else { const [cx, cy, rx, ry, a0, a1] = v; const n = Math.max(6, Math.round(Math.abs(a1 - a0) / 10)); for (let i = 0; i <= n; i++) { const a = (a0 + (a1 - a0) * i / n) * Math.PI / 180; pts.push({ x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a) }); } }
    }
    return pts;
  });
}
const GLYPHS = {}; for (const k in GLYPH_SRC) GLYPHS[k] = parseGlyph(GLYPH_SRC[k]);
const baseCh = key => key.split('#')[0];

/* ---------------- geometry helpers ---------------- */
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
function pathLen(pts) { let L = 0; for (let i = 1; i < pts.length; i++) L += dist(pts[i - 1], pts[i]); return L; }
function resample(pts, n) { // n points evenly spaced along the path, keeping pressure
  if (pts.length === 1) return Array.from({ length: n }, () => ({ ...pts[0] }));
  const I = pathLen(pts) / (n - 1); if (I === 0) return Array.from({ length: n }, () => ({ ...pts[0] }));
  const out = [{ ...pts[0] }]; let D = 0;
  const src = pts.map(p => ({ ...p }));
  for (let i = 1; i < src.length; i++) {
    const d = dist(src[i - 1], src[i]);
    if (D + d >= I && d > 0) {
      const t = (I - D) / d, a = src[i - 1], b = src[i];
      const q = { x: a.x + t * (b.x - a.x), y: a.y + t * (b.y - a.y), p: a.p == null ? undefined : (a.p + t * ((b.p == null ? a.p : b.p) - a.p)) };
      out.push(q); src.splice(i, 0, q); D = 0;
    } else D += d;
  }
  while (out.length < n) out.push({ ...src[src.length - 1] });
  return out.slice(0, n);
}
function bbox(pts) { let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity; for (const p of pts) { if (p.x < x0) x0 = p.x; if (p.y < y0) y0 = p.y; if (p.x > x1) x1 = p.x; if (p.y > y1) y1 = p.y; } return { x0, y0, x1, y1, w: x1 - x0, h: y1 - y0 }; }
const flat = strokes => strokes.flatMap(s => s);
function median(a) { if (!a.length) return 0; const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }

/* ---------------- $P point-cloud matcher ---------------- */
const N = 40;
function cloud(strokes) { // normalised point cloud with stroke ids
  const total = strokes.reduce((a, s) => a + pathLen(s), 0) || 1;
  let pts = [];
  strokes.forEach((s, i) => { const n = Math.max(2, Math.round(N * pathLen(s) / total)) || 2; for (const p of resample(s, n)) pts.push({ x: p.x, y: p.y, id: i }); });
  pts = resampleCloud(pts, N);
  const b = bbox(pts), sc = Math.max(b.w, b.h) || 1;
  const cx = pts.reduce((a, p) => a + p.x, 0) / pts.length, cy = pts.reduce((a, p) => a + p.y, 0) / pts.length;
  return pts.map(p => ({ x: (p.x - cx) / sc, y: (p.y - cy) / sc, id: p.id }));
}
function resampleCloud(pts, n) { // thin or pad to exactly n points keeping order
  if (pts.length === n) return pts;
  if (pts.length > n) { const out = []; for (let i = 0; i < n; i++) out.push(pts[Math.round(i * (pts.length - 1) / (n - 1))]); return out; }
  const out = [...pts]; while (out.length < n) out.push({ ...pts[pts.length - 1] }); return out;
}
function cloudDist(a, b, start) {
  const n = a.length, matched = new Array(n).fill(false); let sum = 0, i = start;
  do {
    let best = Infinity, idx = -1;
    for (let j = 0; j < n; j++) if (!matched[j]) { const d = (a[i].x - b[j].x) ** 2 + (a[i].y - b[j].y) ** 2; if (d < best) { best = d; idx = j; } }
    matched[idx] = true; sum += (1 - ((i - start + n) % n) / n) * Math.sqrt(best); i = (i + 1) % n;
  } while (i !== start);
  return sum;
}
function greedyMatch(a, b) {
  const n = a.length, step = Math.max(1, Math.floor(Math.pow(n, 0.5)));
  let best = Infinity;
  for (let i = 0; i < n; i += step) { best = Math.min(best, cloudDist(a, b, i), cloudDist(b, a, i)); }
  return best / n;
}
const TEMPLATE_CLOUDS = Object.keys(GLYPHS).map(key => ({ key, ch: baseCh(key), cloud: cloud(GLYPHS[key]), aspect: (() => { const b = bbox(flat(GLYPHS[key])); return b.w / Math.max(1, b.h); })(), nStrokes: GLYPHS[key].length }));

/* recognise one character (array of point arrays). Returns ranked candidates. */
function recognise(strokes) {
  const c = cloud(strokes);
  const b = bbox(flat(strokes)); const aspect = b.w / Math.max(1, b.h);
  const scored = TEMPLATE_CLOUDS.map(t => {
    let d = greedyMatch(c, t.cloud);
    const ar = Math.abs(Math.log((aspect + 0.05) / (t.aspect + 0.05)));   // aspect ratio disagreement (scale-normalised cloud loses it)
    d += 0.12 * ar;
    d += 0.03 * Math.abs(strokes.length - t.nStrokes);                     // mild stroke-count prior
    return { ch: t.ch, key: t.key, d };
  }).sort((x, y) => x.d - y.d);
  return scored;
}

/* ---------------- segmentation ---------------- */
function segment(strokes) {
  // strokes in drawing order; each becomes {strokes:[...], box}
  const chars = [];
  for (const s of strokes) {
    const b = bbox(s.points);
    const last = chars[chars.length - 1];
    if (last) {
      const lb = last.box, h = Math.max(lb.h, b.h, 8);
      const overlapX = Math.min(lb.x1, b.x1) - Math.max(lb.x0, b.x0);
      const tiny = b.w < h * 0.35 && b.h < h * 0.35, lastTiny = lb.w < h * 0.35 && lb.h < h * 0.35;
      const thin = lb.w < h * 0.2;                                                   // a stem: arms/bowls attach just beside it
      const ratio = overlapX / Math.max(1, Math.min(lb.w, b.w));
      const sameBand = b.y0 < lb.y1 + h * 0.6 && b.y1 > lb.y0 - h * 0.6;
      const mergedW = Math.max(lb.x1, b.x1) - Math.min(lb.x0, b.x0);
      let near = ratio > 0.35;
      if (!near && (tiny || lastTiny)) near = overlapX > -h * 0.3;                   // dots, crossbars, short serifs
      if (!near && thin) { const stem = (lb.x0 + lb.x1) / 2; near = (Math.abs(b.x0 - stem) < h * 0.1 || Math.abs(b.x1 - stem) < h * 0.1) && overlapX > -h * 0.12; } // attaches to the stem
      const ok = near && sameBand && (mergedW < h * 1.15 || tiny);
      if (ok) { last.strokes.push(s); last.box = bbox(flat(last.strokes.map(x => x.points))); continue; }
    }
    chars.push({ strokes: [s], box: b });
  }
  return chars;
}
function lines(chars) {
  const sorted = [...chars].sort((a, b) => (a.box.y0 + a.box.y1) - (b.box.y0 + b.box.y1));
  const medH = median(chars.map(c => c.box.h)) || 20;
  const out = [];
  for (const c of sorted) {
    const cy = (c.box.y0 + c.box.y1) / 2;
    let best = null, bd = Infinity;
    for (const L of out) { const d = Math.abs(cy - L.cy); if (d < bd) { bd = d; best = L; } }
    if (best && bd < medH * 0.9) { best.chars.push(c); best.cy = (best.cy * (best.chars.length - 1) + cy) / best.chars.length; }
    else out.push({ chars: [c], cy });
  }
  for (const L of out) L.chars.sort((a, b) => a.box.x0 - b.box.x0);
  return out.sort((a, b) => a.cy - b.cy);
}

/* ---------------- recognition with line context ---------------- */
function recogniseLine(L) {
  for (const c of L.chars) { c.cands = recognise(c.strokes.map(s => s.points)); c.ch = c.cands[0].ch; c.key = c.cands[0].key; c.conf = c.cands[0].d; }
  // estimate the line's x-height and cap height from confident characters
  const xh = [], ch = [];
  for (const c of L.chars) {
    const g = c.ch, tb = bbox(flat(GLYPHS[c.key]));
    const unit = c.box.h / Math.max(1, tb.h);           // page px per template unit
    if (X_HEIGHT.has(g) || g in CASE_PAIRS) xh.push(unit * 35); else ch.push(unit * 70);
    c.unit = unit;
  }
  L.xHeight = xh.length ? median(xh) : (ch.length ? median(ch) * 0.5 : median(L.chars.map(c => c.box.h)) * 0.8);
  L.capHeight = ch.length ? median(ch) : L.xHeight * 1.9;
  const digits = L.chars.filter(c => /\d/.test(c.ch)).length;
  // a provisional baseline: bottoms of characters that don't descend
  const base = median(L.chars.filter(c => !DESCENDERS.has(c.ch)).map(c => c.box.y1)) || median(L.chars.map(c => c.box.y1));
  for (const c of L.chars) {
    // case by height: a shape that exists in both cases is upper when it stands well above x-height;
    // y/j/p vs Y/J/P by whether it hangs below the baseline
    let g = c.ch;
    const tall = c.box.h > L.xHeight * 1.35, hangs = c.box.y1 > base + L.xHeight * 0.35;
    const lowerOf = G => Object.keys(CASE_PAIRS).find(k => CASE_PAIRS[k] === G);
    if ('yjp'.includes(g) || 'YJP'.includes(g)) g = hangs ? (lowerOf(g) || g).toLowerCase() : CASE_PAIRS[g.toLowerCase()] || g;
    else if (g in CASE_PAIRS && tall) g = CASE_PAIRS[g];
    else if (/[A-Z]/.test(g) && !tall) { const lower = lowerOf(g); if (lower) g = lower; }
    if (digits > L.chars.length / 2 && g in DIGIT_TWINS) g = DIGIT_TWINS[g];
    if (g !== c.cands[0].ch) c.key = g;              // case/digit swap: use that character's base glyph
    c.ch = g; c.tb = bbox(flat(GLYPHS[c.key]));
    // trusted when the best match is close and clearly better than the next different shape
    const sameShape = (a, b) => a === b || CASE_PAIRS[a] === b || CASE_PAIRS[b] === a || DIGIT_TWINS[a] === b || DIGIT_TWINS[b] === a;
    const alt = c.cands.find(k => !sameShape(k.ch, c.cands[0].ch));
    c.margin = alt ? (alt.d - c.conf) / Math.max(1e-6, c.conf) : 1;
    c.ok = c.conf < 0.065 && c.margin > 0.15;
    c.trust = Math.max(0.3, Math.min(1, (0.065 - c.conf) / 0.04));
  }
  const gaps = L.chars.slice(1).map((c, i) => c.box.x0 - L.chars[i].box.x1);
  const letterGap = median(gaps.filter(g => g < L.xHeight * 0.5));
  L.wordGap = Math.max(L.xHeight * 0.5, letterGap * 2.5);
  L.text = L.chars.map((c, i) => { const gap = i ? gaps[i - 1] : 0; return (gap > L.wordGap ? ' ' : '') + (c.ok ? c.ch : '·'); }).join('');
}

/* ---------------- tidy ---------------- */
function smooth(pts, k = 1) {
  if (pts.length < 4) return pts.map(p => ({ ...p }));
  let a = pts.map(p => ({ ...p }));
  for (let r = 0; r < k; r++) {
    const b = a.map(p => ({ ...p }));
    for (let i = 1; i < a.length - 1; i++) { b[i].x = (a[i - 1].x + 2 * a[i].x + a[i + 1].x) / 4; b[i].y = (a[i - 1].y + 2 * a[i].y + a[i + 1].y) / 4; }
    a = b;
  }
  return a;
}
function transformChar(c, fn) { for (const s of c.strokes) s.points = s.points.map(p => { const q = fn(p); return { x: q.x, y: q.y, p: p.p }; }); c.box = bbox(flat(c.strokes.map(s => s.points))); }

/* Blend a character's strokes toward its glyph: template fitted into the character's box. */
function blendToGlyph(c, amount) {
  const g = GLYPHS[c.key] || GLYPHS[c.ch]; if (!g || g.length !== c.strokes.length) return false;
  const tb = c.tb, b = c.box;
  const sx = b.w / Math.max(1, tb.w), sy = b.h / Math.max(1, tb.h);
  const mapT = p => ({ x: b.x0 + (p.x - tb.x0) * sx, y: b.y0 + (p.y - tb.y0) * sy });
  // pair strokes by nearest centroid so drawing order doesn't matter
  const tc = g.map(s => { const bb = bbox(s.map(mapT)); return { x: (bb.x0 + bb.x1) / 2, y: (bb.y0 + bb.y1) / 2 }; });
  const used = new Set();
  for (const s of c.strokes) {
    const sb = bbox(s.points), sc = { x: (sb.x0 + sb.x1) / 2, y: (sb.y0 + sb.y1) / 2 };
    let bi = -1, bd = Infinity; tc.forEach((t, i) => { if (!used.has(i)) { const d = dist(t, sc); if (d < bd) { bd = d; bi = i; } } });
    used.add(bi);
    const n = Math.max(12, s.points.length);
    const u = resample(s.points, n); let t = resample(g[bi].map(mapT), n);
    const fwd = u.reduce((a, p, i) => a + dist(p, t[i]), 0), rev = u.reduce((a, p, i) => a + dist(p, t[n - 1 - i]), 0);
    if (rev < fwd) t = t.reverse();
    // the template is a stiff ideal; keep the writer's ends, pull the middle
    s.points = u.map((p, i) => { const w = amount * Math.sin(Math.PI * i / (n - 1)) ** 0.5; return { x: p.x + w * (t[i].x - p.x), y: p.y + w * (t[i].y - p.y), p: p.p }; });
  }
  c.box = bbox(flat(c.strokes.map(s => s.points)));
  return true;
}

/* Main entry. strokes: the app's stroke objects (mutated in place). opts: {blend, smooth, scale, space} 0..1 */
function tidy(strokes, opts = {}) {
  const blend = opts.blend ?? 0.3, smoothK = opts.smooth ?? 1, scaleAmt = opts.scale ?? 0.5, spaceAmt = opts.space ?? 0.3;
  const chars = segment(strokes), Ls = lines(chars);
  const texts = [];
  for (const L of Ls) {
    recogniseLine(L);
    texts.push(L.text);
    // baseline through the line: least squares on the recognised characters' baseline points
    const pts = L.chars.map(c => { const r = c.ok ? (70 - c.tb.y0) / Math.max(1, c.tb.h) : 1; return { x: (c.box.x0 + c.box.x1) / 2, y: c.box.y0 + r * c.box.h, w: c.ok ? 1 : 0.4 }; });
    let W = 0, mx = 0, my = 0; for (const p of pts) { W += p.w; mx += p.w * p.x; my += p.w * p.y; } mx /= W; my /= W;
    let num = 0, den = 0; for (const p of pts) { num += p.w * (p.x - mx) * (p.y - my); den += p.w * (p.x - mx) ** 2; }
    const slope = L.chars.length > 2 && den > 0 ? Math.max(-0.25, Math.min(0.25, num / den)) : 0;
    const baseAt = x => my + slope * (x - mx);
    for (const c of L.chars) {
      const r = c.ok ? (70 - c.tb.y0) / Math.max(1, c.tb.h) : 1;        // where the baseline sits inside this character's box
      const cx = (c.box.x0 + c.box.x1) / 2, baseY = c.box.y0 + r * c.box.h;
      // scale gently toward the size the glyph should have on this line
      let f = 1;
      if (c.ok) { const want = c.tb.h * L.xHeight / 35; f = 1 + scaleAmt * (want / Math.max(1, c.box.h) - 1); f = Math.max(0.7, Math.min(1.4, f)); }
      const dy = baseAt(cx) - baseY;
      transformChar(c, p => ({ x: cx + (p.x - cx) * f, y: baseY + dy + (p.y - baseY) * f }));
      for (const s of c.strokes) s.points = smooth(s.points, smoothK);
      if (c.ok && blend > 0) blendToGlyph(c, blend * c.trust);
    }
    // even out spacing a little (word gaps are left alone)
    if (spaceAmt > 0 && L.chars.length > 2) {
      const gaps = L.chars.slice(1).map((c, i) => c.box.x0 - L.chars[i].box.x1);
      const letterGaps = gaps.filter(g => g < L.wordGap), g0 = letterGaps.length ? median(letterGaps) : 0;
      let shift = 0;
      for (let i = 1; i < L.chars.length; i++) {
        const g = gaps[i - 1];
        if (g < L.wordGap) shift += spaceAmt * (g0 - g);
        if (shift) transformChar(L.chars[i], p => ({ x: p.x + shift, y: p.y }));
      }
    }
  }
  return { text: texts.join('\n'), chars: chars.length, lines: Ls.length };
}

/* recognition only (no edits) */
function read(strokes) {
  const copy = strokes.map(s => ({ points: s.points.map(p => ({ ...p })) }));
  const Ls = lines(segment(copy)); for (const L of Ls) recogniseLine(L);
  return Ls.map(L => L.text).join('\n');
}

root.HW = { tidy, read, recognise, segment, lines, GLYPHS, _resample: resample };
})(typeof window !== 'undefined' ? window : globalThis);
