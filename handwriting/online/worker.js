/* Web Worker: runs the online recognizer (ONNX) off the main thread.
   messages in : {type:'load', url, vocabUrl}        → {type:'loaded', ms, vocab}
                 {type:'recognize', id, strokes}     → {type:'result', id, text, ms, T, logprobs?}
   strokes = [{pts:[{x,y}, …]}, …] in writing order, any units (one line of ink). */
import { featurize, greedyDecode, N_FEATURES } from './ink.js';
let ort = null, session = null, vocab = null;

async function load(url, vocabUrl) {
  const t0 = performance.now();
  if (!ort) ort = await import('https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/ort.webgpu.min.mjs');
  ort.env.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/';
  const opts = { executionProviders: ['wasm'] };     // the LSTM op is not on WebGPU yet; wasm is fast enough for a 2 M-param model
  session = await ort.InferenceSession.create(url, opts);
  vocab = (await (await fetch(vocabUrl)).json()).vocab;
  return { ms: performance.now() - t0, vocab };
}

async function recognize(strokes, wantLogprobs) {
  const t0 = performance.now();
  const { data, T } = featurize(strokes);
  const x = new ort.Tensor('float32', data, [1, T, N_FEATURES]);
  const out = await session.run({ features: x });
  const lp = out.logprobs; const To = lp.dims[1];
  const text = greedyDecode(lp.data, To, vocab);
  return { text, ms: performance.now() - t0, T: To, logprobs: wantLogprobs ? lp.data : undefined, V: vocab.length };
}

self.onmessage = async e => {
  const m = e.data;
  try {
    if (m.type === 'load') self.postMessage({ type: 'loaded', ...(await load(m.url, m.vocabUrl)) });
    else if (m.type === 'recognize') { const r = await recognize(m.strokes, m.logprobs); self.postMessage({ type: 'result', id: m.id, ...r }, r.logprobs ? [r.logprobs.buffer] : []); }
  } catch (err) { self.postMessage({ type: 'error', id: m.id, error: String(err && err.message || err) }); }
};
