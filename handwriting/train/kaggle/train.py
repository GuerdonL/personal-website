#!/usr/bin/env python3
"""Kaggle script kernel: fetch all synced pairs, fine-tune TrOCR, export for transformers.js,
publish to the hub if validation CER improved on the currently published model.

Runs headless on a free Kaggle GPU. Pushed by .github/workflows/train.yml (kaggle kernels push).
HF token: a private Kaggle dataset `<you>/hf-token` containing hf_token.txt (attached via kernel-metadata).
Everything else is in the CONFIG block below (edit here or override with env vars in kernel-metadata.json).
"""
import os, sys, json, subprocess, pathlib, shutil, glob
os.environ.setdefault('CUDA_VISIBLE_DEVICES', '0')   # one GPU is plenty; two makes Trainer use DataParallel

CONFIG = dict(
    REPO_GIT   = os.environ.get('REPO_GIT',   'https://github.com/GuerdonL/personal-website'),
    DATASET    = os.environ.get('DATASET',    'GuerdonL/handwriting-pairs'),     # private HF dataset the Worker writes to
    MODEL_REPO = os.environ.get('MODEL_REPO', 'GuerdonL/trocr-guerdon'),         # public HF model the page loads
    BASE_SMALL = 'microsoft/trocr-small-handwritten',
    BASE_BASE  = 'microsoft/trocr-base-handwritten',
    BASE_SWITCH_LINES = int(os.environ.get('BASE_SWITCH_LINES', '400')),         # use trocr-base once this many lines exist
    EPOCHS     = float(os.environ.get('EPOCHS', '20')),
    AUG        = int(os.environ.get('AUG', '8')),
    MIN_LINES  = int(os.environ.get('MIN_LINES', '40')),
    FORCE      = os.environ.get('FORCE_PUBLISH', '0') == '1',
)

def sh(cmd, **kw):
    print('+', cmd, flush=True); subprocess.run(cmd, shell=True, check=True, **kw)

def main():
    C = CONFIG; work = pathlib.Path('/kaggle/working'); os.chdir(work)
    # The HF token comes from an attached private Kaggle dataset (survives `kaggle kernels push`, which
    # drops notebook secrets), else from a Kaggle notebook secret, else from the environment.
    token = os.environ.get('HF_TOKEN', '')
    for f in glob.glob('/kaggle/input/**/hf_token*', recursive=True):
        if not token: token = pathlib.Path(f).read_text().strip(); print('HF token from dataset file', f)
    if not token:
        try:
            from kaggle_secrets import UserSecretsClient; token = UserSecretsClient().get_secret('HF_TOKEN')
        except Exception as e: print('kaggle secret unavailable:', e)
    if not token: sys.exit('no HF_TOKEN: attach the private dataset holding hf_token.txt (see train/README.md)')
    os.environ['HF_TOKEN'] = token; os.environ['HUGGINGFACE_HUB_TOKEN'] = token

    sh('pip install -q "transformers>=4.44" datasets accelerate evaluate jiwer pillow "optimum[onnxruntime]" huggingface_hub onnxruntime')
    if pathlib.Path('site').exists(): shutil.rmtree('site')
    sh(f'git clone -q --depth 1 {C["REPO_GIT"]} site')
    train_dir = work / 'site' / 'handwriting' / 'train'

    from huggingface_hub import snapshot_download, HfApi, upload_file
    api = HfApi(token=token)
    data_dir = snapshot_download(C['DATASET'], repo_type='dataset', token=token, local_dir=str(work / 'pairs'))
    files = sorted(glob.glob(str(pathlib.Path(data_dir) / 'pairs' / '**' / '*.jsonl'), recursive=True))
    print(f'{len(files)} synced files')
    if not files: print('no data yet — nothing to do'); return

    sh(f'python {train_dir}/prepare.py {" ".join(files)} --out data --aug {C["AUG"]}')
    nlines = sum(1 for _ in open('data/train.tsv')) ; nval = sum(1 for _ in open('data/val.tsv'))
    # prepare.py prints "N lines →"; recover N from the split sizes instead of parsing stdout
    ntotal = len({l.split('\t', 1)[0].split('_')[0] for f in ('data/train.tsv', 'data/val.tsv') for l in open(f) if l.strip()})
    print(f'{ntotal} distinct lines → {nlines} train images, {nval} val images')
    if ntotal < C['MIN_LINES']: print(f'only {ntotal} lines; need {C["MIN_LINES"]} — skipping'); return

    # nothing new since the published model? then don't spend the GPU
    try:
        from huggingface_hub import hf_hub_download
        prev = json.load(open(hf_hub_download(C['MODEL_REPO'], 'report.json', token=token)))
        if prev.get('lines') == ntotal and not C['FORCE']: print(f'published model already trained on these {ntotal} lines — skipping'); return
    except Exception as e: print('no published report yet:', type(e).__name__)
    base = C['BASE_BASE'] if ntotal >= C['BASE_SWITCH_LINES'] else C['BASE_SMALL']
    bs = 4 if 'base' in base else 8
    sh(f'python {train_dir}/finetune.py --data data --base {base} --out model --epochs {C["EPOCHS"]} --bs {bs} --report report.json')
    rep = json.load(open('report.json')); rep['trained'] = __import__('datetime').datetime.utcnow().isoformat(timespec='minutes') + 'Z'; rep['lines'] = ntotal
    json.dump(rep, open('report.json', 'w'), indent=1); print(json.dumps(rep, indent=1))
    after = rep['after'].get('eval_cer'); before = rep['before'].get('eval_cer')

    # what is published right now? (its report.json travels with the weights)
    published = None
    try:
        from huggingface_hub import hf_hub_download
        published = json.load(open(hf_hub_download(C['MODEL_REPO'], 'report.json', token=token)))
        print('published model:', published.get('after', {}).get('eval_cer'), 'on', published.get('val'), 'val lines')
    except Exception as e: print('no published report yet:', type(e).__name__)
    pub_cer = (published or {}).get('after', {}).get('eval_cer')
    improved = after is not None and (before is None or after <= before) and (pub_cer is None or after <= pub_cer + 0.005 or C['FORCE'])
    # note: pub_cer was measured on a different (smaller) val set; the +0.005 tolerance keeps a model trained on
    # more data from being blocked by noise. The real guard is after <= before on the current split.
    if not improved and not C['FORCE']:
        print(f'NOT publishing: before {before} after {after} published {pub_cer}'); return

    api.create_repo(C['MODEL_REPO'], repo_type='model', exist_ok=True)
    sh(f'chmod +x {train_dir}/export.sh && {train_dir}/export.sh model {C["MODEL_REPO"]}')
    upload_file(path_or_fileobj='report.json', path_in_repo='report.json', repo_id=C['MODEL_REPO'], token=token, commit_message=f'report: CER {after:.4f} on {rep["val"]} val lines, {ntotal} lines total')
    print(f'PUBLISHED {C["MODEL_REPO"]}: CER {before} → {after}')

if __name__ == '__main__': main()
