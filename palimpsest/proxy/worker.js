// Palimpsest fetch proxy — a Cloudflare Worker that fetches a public web page and returns it with CORS headers,
// so the reader can read sites that do not allow cross-origin requests themselves.
//
// Deploy: create a Worker at https://dash.cloudflare.com, paste this file, deploy, then in Palimpsest → Settings →
// "Your own fetch proxy" enter   https://<your-worker>.workers.dev/?url={url}
//
// Optional: set ALLOWED_ORIGIN below to your site's origin so only your copy of Palimpsest can use it.
const ALLOWED_ORIGIN = '*';
const MAX_BYTES = 5 * 1024 * 1024;

export default {
  async fetch(request) {
    const cors = { 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Access-Control-Allow-Methods': 'GET, OPTIONS', 'Access-Control-Allow-Headers': '*', 'Vary': 'Origin' };
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    if (request.method !== 'GET') return new Response('GET only', { status: 405, headers: cors });
    const target = new URL(request.url).searchParams.get('url');
    let u;
    try { u = new URL(target); } catch (e) { return new Response('Missing or invalid ?url=', { status: 400, headers: cors }); }
    if (!/^https?:$/.test(u.protocol)) return new Response('Only http(s) URLs', { status: 400, headers: cors });
    if (/^(localhost|127\.|10\.|0\.|169\.254\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[::1\]|\[fc|\[fd)/i.test(u.hostname)) return new Response('Refused', { status: 400, headers: cors });
    let upstream;
    try {
      upstream = await fetch(u.href, { redirect: 'follow', headers: { 'User-Agent': 'Mozilla/5.0 (compatible; PalimpsestReader/1.0)', 'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5', 'Accept-Language': request.headers.get('Accept-Language') || 'en' } });
    } catch (e) { return new Response('Upstream fetch failed: ' + e.message, { status: 502, headers: cors }); }
    const ct = upstream.headers.get('content-type') || 'text/html';
    if (!/text\/|xml|json/.test(ct)) return new Response('Not a text document (' + ct + ')', { status: 415, headers: cors });
    const buf = await upstream.arrayBuffer();
    if (buf.byteLength > MAX_BYTES) return new Response('Document too large', { status: 413, headers: cors });
    return new Response(buf, { status: upstream.status, headers: { ...cors, 'Content-Type': ct, 'X-Final-Url': upstream.url, 'Cache-Control': 'public, max-age=300' } });
  }
};
