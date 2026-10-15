import json, sys, os, re, time
from urllib.parse import urlparse, parse_qs, unquote
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(__file__))
import fixtures as F

HTML = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'index.html'))
MODE = sys.argv[1] if len(sys.argv) > 1 else 'wikiwho'   # 'wikiwho' or 'local'
OUT = os.path.join(os.path.dirname(__file__), 'out'); os.makedirs(OUT, exist_ok=True)
LOG = []

def body(route, data, ctype='application/json'):
    route.fulfill(status=200, content_type=ctype, headers={'Access-Control-Allow-Origin': '*'}, body=data if isinstance(data, str) else json.dumps(data))

def handler(route, request):
    u = request.url; p = urlparse(u); q = parse_qs(p.query)
    LOG.append(u)
    if request.method == 'OPTIONS':
        return route.fulfill(status=204, headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'})
    if '/w/rest.php/v1/page/' in u:
        title = unquote(p.path.split('/v1/page/')[1].split('/')[0])
        if title == 'Testopolis': return body(route, {"id": 42, "title": "Testopolis", "latest": {"id": 1005}, "html": F.PARSOID_HTML})
        return route.fulfill(status=404, body='nf')
    if 'rest_v1/page/html/' in u:
        title = unquote(p.path.split('/page/html/')[1])
        if title == 'Testopolis': return body(route, F.PARSOID_HTML, 'text/html')
        if title == 'Coast': return body(route, F.COAST_HTML, 'text/html')
        print('   REST404', title); return route.fulfill(status=404, body='nf')
    if 'api.php' in u:
        a = q.get('action', [''])[0]
        if a == 'opensearch': return body(route, F.OPENSEARCH)
        if a == 'query' and 'revisions' in q.get('prop', ['']): return body(route, F.revisions_json())
        if a == 'query' and q.get('list', [''])[0] == 'users': return body(route, F.USERS_JSON)
        if a == 'query' and q.get('list', [''])[0] == 'search': return body(route, {"query": {"search": [{"title": "Testopolis"}]}})
        return body(route, {})
    if 'wikiwho' in u:
        if MODE == 'local': return route.fulfill(status=503, body='down')
        return body(route, F.wikiwho_json())
    if 'gutendex' in u: return body(route, F.GUTENDEX)
    if 'openlibrary' in u: return body(route, F.OPENLIBRARY)
    if 'export.arxiv.org' in u: return body(route, F.ARXIV_XML, 'application/atom+xml')
    if 'unpaywall' in u: return body(route, F.UNPAYWALL)
    if 'semanticscholar' in u: return body(route, F.S2)
    if 'europepmc' in u: return body(route, F.EPMC)
    if 'duckduckgo.com/ip3' in u or 'favicons' in u:
        return route.fulfill(status=200, content_type='image/png', body=bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da6364f8cf000000020001e221bc330000000049454e44ae426082'))
    if 'upload.wikimedia.org' in u:
        return route.fulfill(status=200, content_type='image/png', body=bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da6364f8cf000000020001e221bc330000000049454e44ae426082'))
    if 'fonts.g' in u: return route.fulfill(status=200, content_type='text/css', body='')
    print('   UNHANDLED', u); return route.fulfill(status=404, body='unhandled ' + u)

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    errors = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.on('console', lambda m: errors.append('console.' + m.type + ': ' + m.text) if m.type in ('error',) else None)
    pg.route(re.compile(r'^https?://'), handler)
    pg.goto('file://' + HTML)
    pg.wait_for_timeout(300)
    check('Read Wikipedia your way' in pg.inner_text('#reader'), 'empty state renders')

    # --- search + open
    pg.fill('#q', 'test'); pg.wait_for_selector('#sugg div');
    check(pg.locator('#sugg div').count() == 3, 'suggestions appear')
    pg.press('#q', 'Enter'); pg.wait_for_selector('#reader h1.title')
    check(pg.inner_text('#reader h1.title') == 'Testopolis', 'article title rendered')
    check(pg.locator('#reader section[data-mw-section-id]').count() == 4, 'sections kept')
    check(pg.locator('#reader .ref-grid .ref-card').count() == 3, 'references became 3 cards')
    kinds = pg.eval_on_selector_all('#reader .ref-card .kind', 'els => els.map(e => e.textContent)')
    check(kinds == ['Web', 'Book', 'Paper'], f'reference kinds classified {kinds}')
    icon = pg.get_attribute('#reader .ref-card img', 'src')
    check(icon == 'https://icons.duckduckgo.com/ip3/example.org.ico', f'favicon preloaded from host ({icon})')
    check(any('icons.duckduckgo.com/ip3/example.org.ico' in u for u in LOG), 'favicon actually requested (preload)')
    check(pg.get_attribute('#reader a[data-title="Coast"]', 'href') == '#Coast', 'wiki links rewritten to in-app links')
    check(pg.get_attribute('#reader .ref-card .ref-actions a', 'target') == '_blank', 'external links open in new tab')

    # --- media settings
    check(pg.get_attribute('#reader img.wimg', 'src', ).startswith('https://upload'), 'images load by default')
    check(pg.locator('#reader video').is_hidden() and pg.locator('#reader .media-off').count() == 1, 'video withheld by default with placeholder')
    pg.click('#modeSettings'); pg.wait_for_selector('#panelSettings:not([hidden])')
    pg.uncheck('#sImages'); pg.wait_for_timeout(100)
    check(pg.locator('#reader img.wimg').is_hidden() and pg.locator('#reader .media-off').count() == 2, 'images off -> placeholder')
    check(pg.get_attribute('#reader img.wimg', 'src') in (None, ''), 'image src removed when off')
    pg.click('#reader .media-off >> nth=0'); pg.wait_for_timeout(100)
    check(pg.locator('#reader img.wimg').is_visible(), 'tap-to-load loads a single image')
    pg.check('#sVideo'); pg.wait_for_timeout(100)
    check(pg.locator('#reader video').is_visible() and pg.get_attribute('#reader video source', 'src').startswith('https://'), 'video on -> source attached')
    pg.check('#sImages')

    # --- type & color settings persist
    pg.select_option('#sFont', 'sans'); pg.fill('#sBg', '#101010'); pg.fill('#sLink', '#ffaa00')
    pg.evaluate("document.querySelector('#sBg').dispatchEvent(new Event('input',{bubbles:true}))")
    pg.evaluate("document.querySelector('#sLink').dispatchEvent(new Event('input',{bubbles:true}))")
    pg.wait_for_timeout(100)
    linkcol = pg.evaluate("getComputedStyle(document.querySelector('#reader a[data-title]')).color")
    check(linkcol == 'rgb(255, 170, 0)', f'link color applied ({linkcol})')
    fam = pg.evaluate("getComputedStyle(document.querySelector('#reader p')).fontFamily")
    check('Atkinson' in fam, f'font family applied ({fam})')
    aul = pg.evaluate("document.querySelector('#reader').style.getPropertyValue('--au-l')")
    check(aul.strip() == '30%', 'author highlights switch to dark variant on dark reader bg')
    saved = json.loads(pg.evaluate("localStorage.getItem('palimpsest.settings')"))
    check(saved['bg'] == '#101010' and saved['font'] == 'sans' and saved['video'] is True, 'settings persisted')
    pg.click('#sResetColors'); pg.wait_for_timeout(50)
    pg.select_option('#sFont', 'serif')

    # --- authorship
    pg.click('#modeAuthors'); pg.wait_for_selector('#auBody:not([hidden])', timeout=10000)
    src = pg.inner_text('#auSrc')
    check(('full history' in src) if MODE == 'wikiwho' else ('revisions' in src), f'attribution source = {src}')
    marks = pg.locator('#reader mark.au').count()
    check(marks > 5, f'{marks} attributed runs painted')
    legend = pg.eval_on_selector_all('#auLegend button .nm', 'els => els.map(e => e.textContent)')
    print('   legend:', legend)
    if MODE == 'wikiwho':
        check(legend[:2] == ['Alice', 'Carol'], 'editor ids resolved to names, sorted by share')
        # exact token ownership: "brick" by Carol, "lantern" by Alice, "granite" by Alice
        owner = lambda word: pg.evaluate(f"""(() => {{ const m=[...document.querySelectorAll('#reader mark.au')].find(m=>m.textContent.toLowerCase().includes('{word}')); if(!m) return null; const i=+m.dataset.a; return i<0?'OLD':document.querySelectorAll('#auLegend button .nm')[i].textContent; }})()""")
        check(owner('brick') == 'Carol', f'"brick" attributed to Carol ({owner("brick")})')
        check(owner('lantern') == 'Alice', f'"lantern festival" attributed to Alice ({owner("lantern")})')
        check(owner('attention based') == 'Carol', f'inserted sentence attributed to Carol')
        # infobox-like unmatched words (figcaption text is not in wikitext) stay unwrapped
        check(pg.evaluate("document.querySelector('#reader figcaption mark.au')") is None, 'text absent from wikitext (figcaption) stays unattributed')
    else:
        check('Carol' in legend and 'Bob' not in legend, 'local mode: Carol (surviving edits) credited; Bob (all reverted) absent')
        owner = lambda word: pg.evaluate(f"""(() => {{ const m=[...document.querySelectorAll('#reader mark.au')].find(m=>m.textContent.toLowerCase().includes('{word}')); if(!m) return null; const i=+m.dataset.a; return i<0?'OLD':document.querySelectorAll('#auLegend button .nm')[i].textContent; }})()""")
        check(owner('brick') == 'Carol', f'"brick" attributed to Carol ({owner("brick")})')
        check(owner('lantern') == 'Alice', f'"lantern" attributed to Alice ({owner("lantern")})')
        check(owner('granite') == 'OLD', f'untouched text marked older than window ({owner("granite")})')
    check(pg.locator('#reader .sec-outlined').count() >= 3, 'sections outlined')
    check(pg.locator('#reader .sec-bar').count() >= 3 and pg.locator('#reader .sec-stat').count() >= 3, 'section share bars + stats present')
    # isolate
    pg.click('#auLegend button >> nth=0'); pg.wait_for_timeout(50)
    check(pg.evaluate("document.querySelector('#reader').classList.contains('iso')") and pg.locator('#reader mark.au.iso-on').count() > 0, 'isolate an editor')
    pg.click('#auLegend button >> nth=0')
    # timeline
    tl = pg.locator('#tl li').count()
    check(tl == 5, f'timeline shows {tl} revisions')
    users = pg.eval_on_selector_all('#tl .u', 'els => els.map(e => e.textContent)')
    check(users == ['Alice', 'Bob', 'Carol', 'Bob', 'Alice'], f'timeline order newest first {users}')
    comments = pg.eval_on_selector_all('#tl .c', 'els => els.map(e => e.textContent)')
    check(any('rm unsourced storms' in c for c in comments), 'edit summaries (comments) shown')
    # open Bob's deletion (index 1)
    pg.click('#tl li >> nth=1 >> .hd'); pg.wait_for_selector('#tl li >> nth=1 >> .diff')
    d = pg.inner_html('#tl li >> nth=1 >> .diff')
    check('<del>' in d and 'Winter storms' in re.sub('<[^>]+>', '', d) and '<ins' not in d, 'deletion shown as strikethrough only')
    dec = pg.evaluate("getComputedStyle(document.querySelector('#tl li:nth-child(2) .diff del')).textDecorationLine")
    check('line-through' in dec, f'deleted text struck through ({dec})')
    filt = pg.evaluate("getComputedStyle(document.querySelector('#tl li:nth-child(2) .diff del')).filter")
    check('saturate' in filt, f'deleted text desaturated ({filt})')
    # open Carol's replacement (index 2)
    pg.click('#tl li >> nth=2 >> .hd'); pg.wait_for_selector('#tl li >> nth=2 >> .diff')
    d2 = pg.inner_html('#tl li >> nth=2 >> .diff')
    check('<del>timber</del>' in d2 and '<ins class="rep">brick</ins>' in d2, 'replacement = del + flagged ins')
    check('<del>steadily' in d2 or '<del> steadily' in d2, 'pure deletion of a word inside sentence')
    check('cite journal' in re.sub('<[^>]+>', '', d2), 'addition of the new reference shown')
    # per-user color on timeline dots / diff
    hues = pg.eval_on_selector_all('#tl li', 'els => els.map(e => e.style.getPropertyValue("--h"))')
    check(hues[0] == hues[4] and hues[1] == hues[3] and hues[0] != hues[1], f'timeline colors per user {hues}')
    pg.screenshot(path=os.path.join(OUT, f'authorship-{MODE}.png'), full_page=False)

    # --- toggle off cleans up
    pg.click('#modeAuthors'); pg.wait_for_timeout(100)
    check(pg.locator('#reader mark.au').count() == 0 and pg.locator('#reader .sec-bar').count() == 0, 'authorship off restores DOM')
    check(pg.inner_text('#reader section[data-mw-section-id="2"] p').startswith('Early settlers built brick'), 'text intact after unwrap')

    # --- sources lookups
    pg.click('#modeSources'); pg.wait_for_selector('#panelSources:not([hidden])')
    stats = [pg.inner_text('#stWeb'), pg.inner_text('#stBook'), pg.inner_text('#stPaper')]
    check(stats == ['1', '1', '1'], f'source stats {stats}')
    pg.click('#findAll')
    pg.wait_for_function("document.querySelectorAll('#reader .ref-card .ref-finds a').length >= 4", timeout=10000)
    book = pg.eval_on_selector_all('#cite_note-book1-2 .ref-finds a', 'els => els.map(e => e.querySelector(".src").textContent + "|" + e.href)')
    print('   book finds:', book)
    check(any(f.startswith('Gutenberg|https://www.gutenberg.org/ebooks/1228') for f in book), 'book found on Project Gutenberg')
    check(any(f.startswith('Internet Archive|https://archive.org/details/') for f in book), 'book found on Internet Archive via Open Library')
    paper = pg.eval_on_selector_all('#cite_note-paper1-3 .ref-finds a', 'els => els.map(e => e.querySelector(".src").textContent + "|" + e.href)')
    print('   paper finds:', paper)
    check(any(f.startswith('arXiv|') for f in paper), 'paper found on arXiv')
    check(any(f.startswith('Unpaywall|') for f in paper), 'paper found via Unpaywall')
    check(any('unpaywall.org/v2/10.48550' in u for u in LOG), 'Unpaywall queried with the DOI')
    check(not any('sci-hub' in u for u in LOG), 'no piracy mirrors contacted')
    check(pg.inner_text('#findProgress') == '2/2 looked up', 'progress counter')
    pg.screenshot(path=os.path.join(OUT, f'sources-{MODE}.png'))

    # --- navigate via wiki link, back
    pg.click('#reader a[data-title="Coast"]'); pg.wait_for_function("document.querySelector('#reader h1.title')?.textContent === 'Coast'")
    check(pg.evaluate('location.hash') == '#Coast', 'hash updated on navigation')
    check(any('rest_v1/page/html/Coast' in u for u in LOG) and any('/w/rest.php/v1/page/Testopolis/with_html' in u for u in LOG), 'core REST used first, rest_v1 fallback used when core 404s')
    pg.go_back(); pg.wait_for_function("document.querySelector('#reader h1.title')?.textContent === 'Testopolis'")
    check(True, 'back button returns to previous article')

    # --- phone layout
    pg.set_viewport_size({'width': 390, 'height': 800}); pg.wait_for_timeout(200)
    sw = pg.evaluate('document.documentElement.scrollWidth'); cw = pg.evaluate('document.documentElement.clientWidth')
    rw = pg.evaluate("document.querySelector('#readerWrap').scrollWidth"); rc = pg.evaluate("document.querySelector('#readerWrap').clientWidth")
    check(sw <= cw and rw <= rc, f'no horizontal overflow at phone width ({sw}/{cw}, reader {rw}/{rc})')
    pg.screenshot(path=os.path.join(OUT, f'phone-{MODE}.png'))

    print('\nPage errors:', errors or 'none')
    check(not [e for e in errors if '404' not in e and '503' not in e], 'no page errors (expected 404 on title probe excluded)')
    b.close()

print('\n%d failures' % len(fails))
for f in fails: print(' -', f)
sys.exit(1 if fails else 0)
