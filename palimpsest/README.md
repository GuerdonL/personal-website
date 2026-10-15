# Palimpsest

A customizable Wikipedia reader in a single HTML file. Served at `/palimpsest/` on the site; it also works opened straight from disk.

- **Reader settings**: font, size, line height, column width, background/text/link colors, and per-type toggles for loading images, video and audio. Stored in `localStorage`.
- **Authorship mode**: colors each word by the editor who wrote it (WikiWho full-history attribution, with an in-browser diff of the last N revisions as fallback), outlines sections by dominant editor, and shows an edit timeline with Google-Docs-style diffs (deletions struck through and desaturated, additions highlighted, replacements flagged).
- **Source cards**: references become cards. Websites get their favicon; books are looked up on Project Gutenberg and Open Library / Internet Archive; papers on arXiv, Unpaywall, Semantic Scholar and Europe PMC.

All data comes from public, keyless APIs called directly from the browser; there is no backend and nothing secret in the page.

## Tests

```
pip install playwright && python -m playwright install chromium
python3 test/run.py wikiwho   # full-history attribution path
python3 test/run.py local     # WikiWho outage -> local diff fallback
node test/perf.mjs            # diff engine benchmark
```

The suite runs the page in headless Chromium against mocked API responses shaped like the live ones.
