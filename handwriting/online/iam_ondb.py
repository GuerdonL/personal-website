#!/usr/bin/env python3
"""IAM-OnDB → pair-format JSONL (one line of ink per row).

Register at https://fki.tic.heia-fr.ch/databases/iam-on-line-handwriting-database and download
  lineStrokes-all.tar.gz   (one XML per text line: strokes of (x, y, time) points)
  ascii-all.tar.gz         (transcriptions; the CSR: block holds one line of text per ink line)
  and the split lists: trainset.txt, testset_v.txt, testset_t.txt, testset_f.txt
Unpack them into one folder, then:

    python iam_ondb.py --root /path/to/iam --out data
      → data/iam_train.jsonl  data/iam_val.jsonl  data/iam_test.jsonl

Coordinates are left as captured (pixels of the whiteboard); features.py normalises per line.
"""
import argparse, json, pathlib, re, sys, xml.etree.ElementTree as ET

def read_transcripts(ascii_root):
    """{form id like 'a01-000u': [line texts]} from the CSR: block of each ascii file."""
    out = {}
    for f in ascii_root.rglob('*.txt'):
        txt = f.read_text(encoding='utf-8', errors='replace')
        m = re.search(r'CSR:\s*\n(.*)', txt, re.S)
        if not m: continue
        lines = [l.rstrip() for l in m.group(1).split('\n')]
        lines = [l for l in lines if l.strip()]
        out[f.stem] = lines
    return out

def read_strokes(xml_path):
    root = ET.parse(xml_path).getroot()
    strokes = []
    for st in root.iter('Stroke'):
        pts = [[float(p.get('x')), float(p.get('y')), 0.5] for p in st.iter('Point')]
        if pts: strokes.append({'t0': int(float(st.get('start_time', 0)) * 1000), 'pts': pts})
    return strokes

def read_split(root, name):
    p = root / name
    if not p.exists():
        for q in root.rglob(name): p = q; break
    return set(l.strip() for l in p.read_text().split('\n') if l.strip()) if p.exists() else set()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--out', default='data'); a = ap.parse_args()
    root = pathlib.Path(a.root); out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    stroke_root = next(root.rglob('lineStrokes'), None); ascii_root = next(root.rglob('ascii'), None)
    if not stroke_root or not ascii_root: sys.exit('could not find lineStrokes/ and ascii/ under ' + str(root))
    tr = read_transcripts(ascii_root)
    splits = {'train': read_split(root, 'trainset.txt'), 'val': read_split(root, 'testset_v.txt'), 'test': read_split(root, 'testset_t.txt') | read_split(root, 'testset_f.txt')}
    files = {k: open(out / f'iam_{k}.jsonl', 'w', encoding='utf-8') for k in splits}; counts = {k: 0 for k in splits}; missing = 0
    for xml in sorted(stroke_root.rglob('*.xml')):
        # a01-000u-01.xml → form a01-000u, line 01
        m = re.match(r'(.+)-(\d+)$', xml.stem)
        if not m: continue
        form, idx = m.group(1), int(m.group(2)) - 1
        lines = tr.get(form)
        if not lines or idx >= len(lines): missing += 1; continue
        text = lines[idx].strip()
        if not text: continue
        # the split lists name the "line id" (a01-000u-01) or the form; accept either
        key = None
        for k, ids in splits.items():
            if xml.stem in ids or form in ids or form.rsplit('-', 1)[0] in ids: key = k; break
        if key is None: key = 'train'
        strokes = read_strokes(xml)
        if len(strokes) < 2: continue
        files[key].write(json.dumps({'text': text, 'strokes': strokes, 'src': 'iam', 'id': xml.stem}, ensure_ascii=False) + '\n'); counts[key] += 1
    for f in files.values(): f.close()
    print('lines per split:', counts, '| without transcript:', missing)

if __name__ == '__main__': main()
