/* Cloudflare Worker: receives training pairs from /handwriting and commits them to a PRIVATE
   Hugging Face dataset repo (one new JSONL file per upload, so there is no read-modify-write).

   Deploy:  cd handwriting/sync && npx wrangler deploy
   Secrets: npx wrangler secret put HF_TOKEN       (HF token with write access to the dataset repo)
            npx wrangler secret put PASSPHRASE     (anything; you enter the same string on the page once per device)
   Vars (wrangler.toml): DATASET_REPO = "<hf-user>/handwriting-pairs", ALLOWED_ORIGIN = "https://<your-pages-host>"

   API:  POST /pairs   header X-Passphrase, body = JSONL (one pair per line, as the page exports)  → {ok, lines, path}
         GET  /health  → "ok"
*/
const MAX_BYTES = 8 * 1024 * 1024;

function cors(env, extra = {}) {
  return { 'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN || '*', 'Access-Control-Allow-Methods': 'POST, GET, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type, X-Passphrase', 'Access-Control-Max-Age': '86400', ...extra };
}
const json = (env, status, body) => new Response(JSON.stringify(body), { status, headers: cors(env, { 'Content-Type': 'application/json' }) });

function b64(bytes) { let s = ''; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000)); return btoa(s); }

// the page's pair format, minimally: text + strokes with points; anything else is rejected
function validate(text) {
  const lines = text.split('\n').filter(l => l.trim()); if (!lines.length) throw new Error('empty');
  if (lines.length > 5000) throw new Error('too many lines');
  for (const l of lines) {
    const r = JSON.parse(l);
    if (typeof r.text !== 'string' || !Array.isArray(r.strokes) || !r.strokes.length) throw new Error('bad pair');
    for (const s of r.strokes) if (!Array.isArray(s.pts) || typeof s.t0 !== 'number') throw new Error('bad stroke');
  }
  return lines;
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(env) });
    if (req.method === 'GET' && url.pathname === '/health') return new Response('ok', { headers: cors(env) });
    if (req.method !== 'POST' || url.pathname !== '/pairs') return json(env, 404, { error: 'not found' });
    if (!env.PASSPHRASE || req.headers.get('X-Passphrase') !== env.PASSPHRASE) return json(env, 401, { error: 'bad passphrase' });
    const len = +req.headers.get('Content-Length') || 0; if (len > MAX_BYTES) return json(env, 413, { error: 'too large' });
    const text = await req.text(); if (text.length > MAX_BYTES) return json(env, 413, { error: 'too large' });
    let lines; try { lines = validate(text); } catch (e) { return json(env, 400, { error: String(e.message || e) }); }
    const now = new Date(); const day = now.toISOString().slice(0, 10);
    const path = `pairs/${day}/${now.toISOString().replace(/[:.]/g, '-')}-${Math.random().toString(36).slice(2, 8)}.jsonl`;
    const body = [
      JSON.stringify({ key: 'header', value: { summary: `${lines.length} pairs from /handwriting`, description: '' } }),
      JSON.stringify({ key: 'file', value: { path, encoding: 'base64', content: b64(new TextEncoder().encode(lines.join('\n') + '\n')) } }),
    ].join('\n');
    const r = await fetch(`https://huggingface.co/api/datasets/${env.DATASET_REPO}/commit/main`, { method: 'POST', headers: { Authorization: `Bearer ${env.HF_TOKEN}`, 'Content-Type': 'application/x-ndjson' }, body });
    if (!r.ok) return json(env, 502, { error: 'hub rejected the commit', status: r.status, detail: (await r.text()).slice(0, 300) });
    return json(env, 200, { ok: true, lines: lines.length, path });
  },
};
