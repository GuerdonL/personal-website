# Palimpsest

A customizable Wikipedia reader in a single HTML file. Served at `/palimpsest/` on the site; it also works opened straight from disk.

- **Reader settings**: font, size, line height, column width, background/text/link colors, and per-type toggles for loading images, video and audio. Stored in `localStorage`.
- **Authorship mode**: colors each word by the editor who wrote it (WikiWho full-history attribution, with an in-browser diff of the last N revisions as fallback), outlines sections by dominant editor, and shows an edit timeline with Google-Docs-style diffs (deletions struck through and desaturated, additions highlighted, replacements flagged).
- **Source cards**: references become cards. Websites get their favicon; books are looked up on Project Gutenberg and Open Library / Internet Archive; papers on arXiv, Unpaywall, Semantic Scholar and Europe PMC.

- **Linked websites in reader mode**: links to other sites open inside Palimpsest, reduced to their article with Mozilla Readability and restyled with the same type and color settings. Fetch order: your own proxy (optional), the site directly, then the keyless r.jina.ai reader service (HTML, then its Markdown rendering). Wikipedia links found inside those pages open as articles; PDFs and media files are left to the browser. Set "Open links to other sites" to "new tab" to turn this off.

`proxy/worker.js` is a Cloudflare Worker you can deploy in a minute for a private, more reliable fetch path; paste its URL with `{url}` into Settings.

All data comes from public, keyless APIs called directly from the browser; there is no backend and nothing secret in the page.

## Tests

```
pip install playwright && python -m playwright install chromium
python3 test/run.py wikiwho   # full-history attribution path
python3 test/run.py local     # WikiWho outage -> local diff fallback
node test/perf.mjs            # diff engine benchmark
```

The suite runs the page in headless Chromium against mocked API responses shaped like the live ones.
