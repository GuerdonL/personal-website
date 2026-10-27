#!/usr/bin/env python3
"""Kaggle kernel: train the online recognizer.

Phase 1 (general): IAM-OnDB from the private dataset `<you>/iam-ondb` → model_general.pt, published to
the hub as <MODEL_REPO>/online/general.{pt,onnx,onnx.json} with a report.
Phase 2 (personal): fine-tune general on the synced pairs (`<you>/handwriting-pairs`), holding out the
50 oldest lines; published as online/personal.* only if holdout CER beats the published one.

Attach to the kernel (kernel-metadata dataset_sources): <you>/hf-token, <you>/iam-ondb.
"""
import os, sys, json, glob, pathlib, shutil, subprocess, hashlib
os.environ.setdefault('CUDA_VISIBLE_DEVICES', '0')

CFG = dict(
    REPO_GIT   = os.environ.get('REPO_GIT', 'https://github.com/GuerdonL/personal-website'),
    DATASET    = os.environ.get('DATASET', 'GuerdonL/handwriting-pairs'),
    MODEL_REPO = os.environ.get('MODEL_REPO', 'GuerdonL/trocr-guerdon'),     # same hub repo, under online/
    PHASE      = os.environ.get('PHASE', 'auto'),                             # general | personal | auto
    EPOCHS_GENERAL = int(os.environ.get('EPOCHS_GENERAL', '40')),
    EPOCHS_PERSONAL = int(os.environ.get('EPOCHS_PERSONAL', '40')),
    HOLDOUT = 50, FORCE = os.environ.get('FORCE_PUBLISH', '0') == '1',
)

def sh(cmd):
    print('+', cmd, flush=True)
    pr = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in pr.stdout: print(line, end='', flush=True)
    if pr.wait(): raise SystemExit(f'command failed: {cmd[:80]}')

def token():
    t = os.environ.get('HF_TOKEN', '')
    for f in glob.glob('/kaggle/input/**/hf_token*', recursive=True):
        if not t: t = pathlib.Path(f).read_text().strip()
    if not t:
        try:
            from kaggle_secrets import UserSecretsClient; t = UserSecretsClient().get_secret('HF_TOKEN')
        except Exception as e: print('no kaggle secret:', e)
    if not t: sys.exit('no HF token')
    return t

def main():
    C = CFG; work = pathlib.Path('/kaggle/working'); os.chdir(work); tok = token(); os.environ['HF_TOKEN'] = tok
    sh('pip install -q huggingface_hub onnx onnxscript')
    if pathlib.Path('site').exists(): shutil.rmtree('site')
    sh(f'git clone -q --depth 1 {C["REPO_GIT"]} site'); od = work / 'site' / 'handwriting' / 'online'
    from huggingface_hub import HfApi, hf_hub_download, snapshot_download
    api = HfApi(token=tok); api.create_repo(C['MODEL_REPO'], repo_type='model', exist_ok=True)
    def published(name):
        try: return json.load(open(hf_hub_download(C['MODEL_REPO'], f'online/{name}.report.json', token=tok)))
        except Exception: return None
    def publish(name, pt, onnx, report):
        for src, dst in [(pt, f'online/{name}.pt'), (onnx, f'online/{name}.onnx'), (onnx + '.json', f'online/{name}.onnx.json'), (report, f'online/{name}.report.json')]:
            api.upload_file(path_or_fileobj=src, path_in_repo=dst, repo_id=C['MODEL_REPO'], token=tok)
        print('PUBLISHED', name, json.load(open(report)).get('after'))

    phase = C['PHASE']
    gen_rep = published('general')
    if phase == 'auto': phase = 'general' if gen_rep is None else 'personal'
    print('phase:', phase)

    if phase == 'general':
        iam = next((pathlib.Path(p).parent for p in glob.glob('/kaggle/input/**/lineStrokes*', recursive=True)), None)
        if iam is None: sys.exit('IAM-OnDB not attached: expected a dataset containing lineStrokes/ and ascii/')
        # the dataset may hold tarballs or unpacked folders; unpack what is needed
        for tgz in glob.glob('/kaggle/input/**/*.tar.gz', recursive=True): sh(f'tar xzf "{tgz}" -C {work} 2>/dev/null || true')
        root = work if glob.glob(str(work / '**/lineStrokes'), recursive=True) else iam
        for f in glob.glob('/kaggle/input/**/*set*.txt', recursive=True): shutil.copy(f, work)
        sh(f'python {od}/iam_ondb.py --root {root} --out data')
        sh(f'python -u {od}/train.py --train data/iam_train.jsonl --val data/iam_val.jsonl --out general.pt --epochs {C["EPOCHS_GENERAL"]} --bs 32 --lr 1e-3 --export general.onnx --report general.report.json')
        rep = json.load(open('general.report.json')); rep['trained'] = __import__('datetime').datetime.utcnow().isoformat(timespec='minutes') + 'Z'; rep['data'] = 'iam-ondb'
        # phase-1 gate from PLAN.md
        rep['gate_15pct'] = rep['after']['eval_cer'] < 0.15; json.dump(rep, open('general.report.json', 'w'), indent=1); print(json.dumps(rep, indent=1))
        if gen_rep is None or rep['after']['eval_cer'] < gen_rep['after']['eval_cer'] or C['FORCE']: publish('general', 'general.pt', 'general.onnx', 'general.report.json')
        else: print('not publishing: general CER did not improve on', gen_rep['after']['eval_cer'])
        return

    # ---- personal ----
    hf_hub_download(C['MODEL_REPO'], 'online/general.pt', token=tok, local_dir='.')
    d = snapshot_download(C['DATASET'], repo_type='dataset', token=tok, local_dir=str(work / 'pairs'))
    files = sorted(glob.glob(str(pathlib.Path(d) / 'pairs' / '**' / '*.jsonl'), recursive=True))
    rows = {}
    for f in files:
        for l in open(f, encoding='utf-8'):
            if not l.strip(): continue
            r = json.loads(l)
            if not r.get('text', '').strip() or len(r.get('strokes', [])) < 2: continue
            k = hashlib.md5(json.dumps([s.get('t0') for s in r['strokes']]).encode()).hexdigest()
            if k not in rows or r.get('ts', 0) >= rows[k].get('ts', 0): rows[k] = r
    rows = sorted(rows.values(), key=lambda r: r.get('ts', 0))
    hold, train = rows[:C['HOLDOUT']], rows[C['HOLDOUT']:]
    print(f'{len(rows)} personal lines: {len(train)} train, {len(hold)} holdout (oldest, never trained on)')
    if len(train) < 30: print('not enough personal lines yet'); return
    with open('mine.jsonl', 'w') as f: f.writelines(json.dumps(r) + '\n' for r in train)
    with open('holdout.jsonl', 'w') as f: f.writelines(json.dumps(r) + '\n' for r in hold)
    sh(f'python -u {od}/train.py --train mine.jsonl --val holdout.jsonl --init online/general.pt --out personal.pt --epochs {C["EPOCHS_PERSONAL"]} --bs 16 --lr 3e-4 --export personal.onnx --report personal.report.json')
    rep = json.load(open('personal.report.json')); rep['trained'] = __import__('datetime').datetime.utcnow().isoformat(timespec='minutes') + 'Z'; rep['lines'] = len(rows)
    json.dump(rep, open('personal.report.json', 'w'), indent=1); print(json.dumps(rep, indent=1))
    prev = published('personal')
    if prev is None or rep['after']['eval_cer'] <= prev['after']['eval_cer'] or C['FORCE']: publish('personal', 'personal.pt', 'personal.onnx', 'personal.report.json')
    else: print('not publishing: holdout CER', rep['after']['eval_cer'], 'vs published', prev['after']['eval_cer'])

if __name__ == '__main__': main()
