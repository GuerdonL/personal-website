#!/usr/bin/env python3
"""Parity check: features.py and ink.js must produce the same numbers for the same ink.
    python check.py   (needs node)
"""
import json, math, subprocess, pathlib, numpy as np
from features import featurize
here = pathlib.Path(__file__).parent
st = [{'t0': i, 'pts': [[i * 0.4 + k * 0.05, 0.5 + 0.4 * math.sin(k * 0.7 + i), 0.5] for k in range(9)]} for i in range(4)]
st.append({'t0': 9, 'pts': [[3.0, 0.2, 0.5]]})                       # a dot
py = featurize(st)
js = subprocess.run(['node', '--input-type=module', '-e', f"""
import {{ featurize }} from '{(here / 'ink.js').as_uri()}';
const st = {json.dumps([{'pts': [{'x': p[0], 'y': p[1]} for p in s['pts']]} for s in st])};
const r = featurize(st); console.log(JSON.stringify({{T: r.T, data: Array.from(r.data)}}));
"""], capture_output=True, text=True, check=True)
j = json.loads(js.stdout); jsf = np.array(j['data'], np.float32).reshape(j['T'], -1)
print('python', py.shape, 'js', jsf.shape)
assert py.shape == jsf.shape, 'shape mismatch'
d = np.abs(py - jsf).max(0); print('max |diff| per feature:', d.round(6))
assert d.max() < 1e-5, 'feature mismatch'
print('OK: features.py and ink.js agree')
