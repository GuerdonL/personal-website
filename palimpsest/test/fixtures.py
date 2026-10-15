import json

# Five wikitext revisions (oldest -> newest) by three editors, with an insertion, a deletion and a replacement.
REV_TEXTS = [
# r1 by Alice (oldest, "before window" baseline)
"""{{Short description|Imaginary coastal town}}
'''Testopolis''' is a fictional harbour town on the northern coast. It was founded in 1820 by sailors who needed a sheltered anchorage.<ref name="web1">{{cite web |title=Testopolis harbour history |url=https://example.org/harbour/history |website=Example Heritage |access-date=1 May 2026}}</ref>

== Geography ==
The town sits on a granite headland. The harbour is protected by a long breakwater that was completed in 1905.

== History ==
Early settlers built timber warehouses along the quay. Trade in salted fish grew steadily through the nineteenth century.<ref name="book1">{{cite book |last=Darwin |first=Charles |title=On the Origin of Species |year=1859 |publisher=John Murray |isbn=978-0-14-043205-1}}</ref>

== References ==
{{reflist}}
""",
# r2 by Bob: inserts a sentence in Geography
"""{{Short description|Imaginary coastal town}}
'''Testopolis''' is a fictional harbour town on the northern coast. It was founded in 1820 by sailors who needed a sheltered anchorage.<ref name="web1">{{cite web |title=Testopolis harbour history |url=https://example.org/harbour/history |website=Example Heritage |access-date=1 May 2026}}</ref>

== Geography ==
The town sits on a granite headland. The harbour is protected by a long breakwater that was completed in 1905. Winter storms frequently close the harbour mouth for days at a time.

== History ==
Early settlers built timber warehouses along the quay. Trade in salted fish grew steadily through the nineteenth century.<ref name="book1">{{cite book |last=Darwin |first=Charles |title=On the Origin of Species |year=1859 |publisher=John Murray |isbn=978-0-14-043205-1}}</ref>

== References ==
{{reflist}}
""",
# r3 by Carol: replaces "timber" with "brick", deletes "steadily", adds a journal ref
"""{{Short description|Imaginary coastal town}}
'''Testopolis''' is a fictional harbour town on the northern coast. It was founded in 1820 by sailors who needed a sheltered anchorage.<ref name="web1">{{cite web |title=Testopolis harbour history |url=https://example.org/harbour/history |website=Example Heritage |access-date=1 May 2026}}</ref>

== Geography ==
The town sits on a granite headland. The harbour is protected by a long breakwater that was completed in 1905. Winter storms frequently close the harbour mouth for days at a time.

== History ==
Early settlers built brick warehouses along the quay. Trade in salted fish grew through the nineteenth century.<ref name="book1">{{cite book |last=Darwin |first=Charles |title=On the Origin of Species |year=1859 |publisher=John Murray |isbn=978-0-14-043205-1}}</ref> Modern studies of the breakwater use attention based models.<ref name="paper1">{{cite journal |last=Vaswani |first=Ashish |title=Attention Is All You Need |journal=Advances in Neural Information Processing Systems |year=2017 |doi=10.48550/arXiv.1706.03762}}</ref>

== References ==
{{reflist}}
""",
# r4 by Bob: deletes the whole winter storms sentence
"""{{Short description|Imaginary coastal town}}
'''Testopolis''' is a fictional harbour town on the northern coast. It was founded in 1820 by sailors who needed a sheltered anchorage.<ref name="web1">{{cite web |title=Testopolis harbour history |url=https://example.org/harbour/history |website=Example Heritage |access-date=1 May 2026}}</ref>

== Geography ==
The town sits on a granite headland. The harbour is protected by a long breakwater that was completed in 1905.

== History ==
Early settlers built brick warehouses along the quay. Trade in salted fish grew through the nineteenth century.<ref name="book1">{{cite book |last=Darwin |first=Charles |title=On the Origin of Species |year=1859 |publisher=John Murray |isbn=978-0-14-043205-1}}</ref> Modern studies of the breakwater use attention based models.<ref name="paper1">{{cite journal |last=Vaswani |first=Ashish |title=Attention Is All You Need |journal=Advances in Neural Information Processing Systems |year=2017 |doi=10.48550/arXiv.1706.03762}}</ref>

== References ==
{{reflist}}
""",
# r5 by Alice: adds a new lead sentence
"""{{Short description|Imaginary coastal town}}
'''Testopolis''' is a fictional harbour town on the northern coast. It was founded in 1820 by sailors who needed a sheltered anchorage.<ref name="web1">{{cite web |title=Testopolis harbour history |url=https://example.org/harbour/history |website=Example Heritage |access-date=1 May 2026}}</ref> Today it is best known for its annual lantern festival.

== Geography ==
The town sits on a granite headland. The harbour is protected by a long breakwater that was completed in 1905.

== History ==
Early settlers built brick warehouses along the quay. Trade in salted fish grew through the nineteenth century.<ref name="book1">{{cite book |last=Darwin |first=Charles |title=On the Origin of Species |year=1859 |publisher=John Murray |isbn=978-0-14-043205-1}}</ref> Modern studies of the breakwater use attention based models.<ref name="paper1">{{cite journal |last=Vaswani |first=Ashish |title=Attention Is All You Need |journal=Advances in Neural Information Processing Systems |year=2017 |doi=10.48550/arXiv.1706.03762}}</ref>

== References ==
{{reflist}}
""",
]
USERS = ["Alice", "Bob", "Carol", "Bob", "Alice"]
IDS = [1001, 1002, 1003, 1004, 1005]
COMMENTS = ["created page", "/* Geography */ add storms sentence", "/* History */ brick, trim, cite paper", "/* Geography */ rm unsourced storms claim", "lantern festival"]

def revisions_json():
    revs = []
    for i in reversed(range(5)):
        revs.append({"revid": IDS[i], "parentid": IDS[i-1] if i else 0, "user": USERS[i], "userid": i+1,
                     "timestamp": f"2026-10-{10+i:02d}T12:00:00Z", "comment": COMMENTS[i], "size": len(REV_TEXTS[i]),
                     "slots": {"main": {"contentmodel": "wikitext", "contentformat": "text/x-wiki", "content": REV_TEXTS[i]}}})
    return {"query": {"pages": [{"pageid": 42, "ns": 0, "title": "Testopolis", "revisions": revs}]}}

# Parsoid-style HTML for the newest revision
PARSOID_HTML = """<!DOCTYPE html><html><head><title>Testopolis</title><link rel="dc:isVersionOf" href="//en.wikipedia.org/wiki/Testopolis"/><meta property="mw:revisionSHA1" content="x"/></head>
<body class="mw-content-ltr" about="http://en.wikipedia.org/wiki/Special:Redirect/revision/1005">
<section data-mw-section-id="0">
<p><b>Testopolis</b> is a fictional harbour town on the northern <a rel="mw:WikiLink" href="./Coast" title="Coast">coast</a>. It was founded in 1820 by sailors who needed a sheltered anchorage.<sup class="mw-ref reference" id="cite_ref-web1_1-0"><a href="./Testopolis#cite_note-web1-1"><span class="mw-reflink-text">[1]</span></a></sup> Today it is best known for its annual lantern festival.</p>
<figure typeof="mw:File/Thumb"><a href="./File:Harbour.jpg"><img src="//upload.wikimedia.org/wikipedia/commons/thumb/x/Harbour.jpg/220px-Harbour.jpg" srcset="//upload.wikimedia.org/x/440px-Harbour.jpg 2x" width="220" height="150" alt="Harbour view"/></a><figcaption>The harbour at dusk</figcaption></figure>
<p><video poster="//upload.wikimedia.org/poster.jpg" controls="" preload="none" width="220" height="140"><source src="//upload.wikimedia.org/storm.webm" type="video/webm"/></video></p>
</section>
<section data-mw-section-id="1"><h2 id="Geography">Geography</h2>
<p>The town sits on a granite headland. The harbour is protected by a long breakwater that was completed in 1905.<a rel="mw:ExtLink" class="external" href="https://news.example.com/story">(report)</a></p>
</section>
<section data-mw-section-id="2"><h2 id="History">History</h2>
<p>Early settlers built brick warehouses along the quay. Trade in salted fish grew through the nineteenth century.<sup class="mw-ref reference" id="cite_ref-book1_2-0"><a href="./Testopolis#cite_note-book1-2"><span class="mw-reflink-text">[2]</span></a></sup> Modern studies of the breakwater use attention based models.<sup class="mw-ref reference" id="cite_ref-paper1_3-0"><a href="./Testopolis#cite_note-paper1-3"><span class="mw-reflink-text">[3]</span></a></sup></p>
</section>
<section data-mw-section-id="3"><h2 id="References">References</h2>
<div class="mw-references-wrap"><ol class="mw-references references">
<li about="#cite_note-web1-1" id="cite_note-web1-1"><span class="mw-cite-backlink">^</span> <span id="mw-reference-text-cite_note-web1-1" class="mw-reference-text reference-text"><cite class="citation web cs1">"Testopolis harbour history". <i>Example Heritage</i>. <a rel="mw:ExtLink" href="https://example.org/harbour/history" class="external">example.org</a>. Retrieved 1 May 2026.</cite></span></li>
<li about="#cite_note-book1-2" id="cite_note-book1-2"><span class="mw-cite-backlink">^</span> <span class="mw-reference-text reference-text"><cite class="citation book cs1">Darwin, Charles (1859). <i>On the Origin of Species</i>. John Murray. <a rel="mw:WikiLink" href="./ISBN_(identifier)">ISBN</a>&nbsp;<a rel="mw:WikiLink" href="./Special:BookSources/978-0-14-043205-1">978-0-14-043205-1</a>.</cite></span></li>
<li about="#cite_note-paper1-3" id="cite_note-paper1-3"><span class="mw-cite-backlink">^</span> <span class="mw-reference-text reference-text"><cite class="citation journal cs1">Vaswani, Ashish (2017). "Attention Is All You Need". <i>Advances in Neural Information Processing Systems</i>. <a rel="mw:WikiLink" href="./Doi_(identifier)">doi</a>:<a rel="mw:ExtLink" class="external" href="https://doi.org/10.48550%2FarXiv.1706.03762">10.48550/arXiv.1706.03762</a>.</cite></span></li>
</ol></div>
</section>
</body></html>"""

COAST_HTML = """<!DOCTYPE html><html><head><title>Coast</title></head><body about="http://en.wikipedia.org/wiki/Special:Redirect/revision/77"><section data-mw-section-id="0"><p>A <b>coast</b> is where land meets sea.</p></section></body></html>"""

def wikiwho_json():
    # Token stream mirroring r5's wikitext, lowercase, with per-token origin
    toks = []
    def w(s, rev, ed):
        for part in s.split():
            toks.append({"str": part.lower(), "o_rev_id": rev, "editor": ed})
    w("{{ short description | imaginary coastal town }}", 1001, "1")
    w("''' testopolis ''' is a fictional harbour town on the northern coast . it was founded in 1820 by sailors who needed a sheltered anchorage .", 1001, "1")
    w("< ref name = \" web1 \" > {{ cite web | title = testopolis harbour history | url = https://example.org/harbour/history | website = example heritage | access-date = 1 may 2026 }} </ ref >", 1001, "1")
    w("today it is best known for its annual lantern festival .", 1005, "1")
    w("== geography ==", 1001, "1")
    w("the town sits on a granite headland . the harbour is protected by a long breakwater that was completed in 1905 .", 1001, "1")
    w("== history ==", 1001, "1")
    w("early settlers built", 1001, "1"); w("brick", 1003, "3"); w("warehouses along the quay . trade in salted fish grew through the nineteenth century .", 1001, "1")
    w("< ref name = \" book1 \" > {{ cite book | last = darwin | first = charles | title = on the origin of species | year = 1859 | publisher = john murray | isbn = 978-0-14-043205-1 }} </ ref >", 1001, "1")
    w("modern studies of the breakwater use attention based models .", 1003, "3")
    w("< ref name = \" paper1 \" > {{ cite journal | last = vaswani | first = ashish | title = attention is all you need | journal = advances in neural information processing systems | year = 2017 | doi = 10.48550/arxiv.1706.03762 }} </ ref >", 1003, "3")
    w("== references == {{ reflist }}", 1001, "1")
    return {"article_title": "Testopolis", "page_id": 42, "success": True, "message": None,
            "revisions": [{"1005": {"editor": "1", "time": "2026-10-14T12:00:00Z", "tokens": toks}}]}

USERS_JSON = {"query": {"users": [{"userid": 1, "name": "Alice"}, {"userid": 3, "name": "Carol"}]}}
OPENSEARCH = ["test", ["Testopolis", "Test cricket", "Testosterone"], [], []]
GUTENDEX = {"count": 1, "results": [{"id": 1228, "title": "On the Origin of Species By Means of Natural Selection", "authors": [{"name": "Darwin, Charles"}],
            "formats": {"text/html": "https://www.gutenberg.org/ebooks/1228.html.images", "application/epub+zip": "https://www.gutenberg.org/ebooks/1228.epub3.images"}}]}
OPENLIBRARY = {"docs": [{"key": "/works/OL20600W", "title": "On the Origin of Species", "author_name": ["Charles Darwin"], "ia": ["originofspecies00darw"], "ebook_access": "public"}]}
ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1706.03762v7</id><title>Attention Is All You Need</title><link href="http://arxiv.org/abs/1706.03762v7" rel="alternate" type="text/html"/></entry></feed>"""
UNPAYWALL = {"doi": "10.48550/arxiv.1706.03762", "is_oa": True, "best_oa_location": {"host_type": "repository", "version": "submittedVersion", "url": "https://arxiv.org/abs/1706.03762", "url_for_pdf": "https://arxiv.org/pdf/1706.03762"}, "oa_locations": []}
S2 = {"title": "Attention is All you Need", "openAccessPdf": {"url": "https://arxiv.org/pdf/1706.03762.pdf"}, "externalIds": {"ArXiv": "1706.03762"}}
EPMC = {"resultList": {"result": []}}

# An external site: boilerplate around an article, with a Wikipedia link and a relative image/link inside.
EXT_HTML = """<!DOCTYPE html><html><head><title>Testopolis harbour history | Example Heritage</title>
<meta property="og:site_name" content="Example Heritage"><meta name="author" content="J. Quayle"><meta name="description" content="How a granite headland became a harbour town.">
<style>body{font-family:Comic Sans MS}</style><script>window.ads=1</script></head>
<body><header><nav><a href="/">Home</a> <a href="/about">About</a> <a href="/shop">Shop</a> <a href="/newsletter">Newsletter</a></nav></header>
<aside class="sidebar"><h3>Trending</h3><ul><li><a href="/a">Ten lighthouses to visit</a></li><li><a href="/b">Best fish markets</a></li></ul></aside>
<main><article>
<h1>Testopolis harbour history</h1>
<p class="lede">The harbour at Testopolis is one of the oldest continuously used anchorages on the northern coast, and its story begins with a granite headland and a handful of sailors looking for shelter.</p>
<p>In the first decades after 1820 the settlement grew around a timber quay. The <a href="/breakwater">breakwater</a> that protects the harbour today was not finished until 1905, after two earlier attempts were destroyed by winter storms. Contemporary accounts describe the salted-fish trade as the town's economic engine throughout the nineteenth century.</p>
<figure><img src="/img/quay.jpg" alt="The old quay" width="800" height="500"><figcaption>The quay around 1890</figcaption></figure>
<h2>Sources</h2>
<p>Much of this account draws on the municipal archive and on the <a href="https://en.wikipedia.org/wiki/Pangolin">pangolin</a> collection catalogue, which is unrelated but delightful. Further reading is available at <a href="https://docs.example.com/report.pdf">the full report (PDF)</a>.</p>
<p onclick="alert(1)" style="color:red">Click here to subscribe to our newsletter and never miss an update from Example Heritage!</p>
</article></main>
<footer><p>© Example Heritage. <a href="/privacy">Privacy</a> <a href="/terms">Terms</a></p></footer>
<script src="/tracker.js"></script></body></html>"""

JINA_MD = """Title: A local report on the breakwater

URL Source: https://news.example.com/story

Published Time: 2026-09-30T08:00:00Z

Markdown Content:
A local report on the breakwater
================================

The council voted **unanimously** to repair the eastern arm of the breakwater after engineers found _three_ cracked blocks.

![Breakwater survey](https://news.example.com/img/survey.jpg)

## What happens next

- Surveys continue through October
- Repairs begin in spring
- Funding comes from the [harbour levy](https://news.example.com/levy)

> "The structure is safe, but it will not stay that way without work," the chief engineer said.

See also the [history of the town](https://en.wikipedia.org/wiki/Testopolis).
"""

CF_CHALLENGE = """<!DOCTYPE html><html><head><title>Just a moment...</title><script src="/cdn-cgi/challenge-platform/h/b/orchestrate/jsch/v1"></script></head>
<body><div id="cf-browser-verification"><h1>Checking your browser before accessing shop.example.com.</h1><p>Please enable JavaScript and cookies to continue.</p></div></body></html>"""
CF_CHALLENGE_MD = """Title: Just a moment...

URL Source: https://shop.example.com/item

Markdown Content:
Checking your browser before accessing shop.example.com.
"""
SHOP_HTML = """<!DOCTYPE html><html><head><title>The Testopolis lantern, reviewed</title></head><body><nav><a href="/">Shop</a></nav><article><h1>The Testopolis lantern, reviewed</h1>
<p>We carried the lantern through three winter storms on the breakwater and it never once went out, which is more than can be said for the previous model that we tested in 1905.</p>
<p>The brass fittings are heavier than they look and the glass is thick enough to survive being dropped on the granite quay. Trade in these lanterns grew through the nineteenth century for good reason.</p></article></body></html>"""
