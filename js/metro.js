/**
 * Metro Lines — decorative SVG routes connecting a departure station row
 * (below the hero) to each page section.  Lines use 45° / 90° metro-style
 * routing and run through the left and right margins so they never overlap
 * the centered content.  Hidden below 1280 px viewport width.
 */
(function () {
    /* ── line definitions ──────────────────────────────────────────── */
    var lines = [
        { id: 'about',    label: 'PHILOSOPHY', color: '#D64045', side: 'left',  lane: 0 },
        { id: 'roles',    label: 'DISCIPLINE', color: '#1B85B8', side: 'right', lane: 0 },
        { id: 'resume',   label: 'RESUME',     color: '#2A9D8F', side: 'left',  lane: 1 },
        { id: 'society',  label: 'SOCIETY',    color: '#C27D38', side: 'right', lane: 1 },
        { id: 'projects', label: 'PROJECTS',   color: '#E76F51', side: 'left',  lane: 2 },
        { id: 'contact',  label: 'CONTACT',    color: '#7B6D8D', side: 'right', lane: 2 }
    ];

    var NS  = 'http://www.w3.org/2000/svg';
    var svg = null;

    /* ── helpers ────────────────────────────────────────────────────── */
    function el(tag, attrs) {
        var node = document.createElementNS(NS, tag);
        for (var k in attrs) node.setAttribute(k, attrs[k]);
        return node;
    }

    function circle(cx, cy, r, fill, stroke, sw) {
        return el('circle', {
            cx: cx, cy: cy, r: r, fill: fill,
            stroke: stroke || 'none', 'stroke-width': sw || 0
        });
    }

    function label(x, y, text, color, anchor) {
        var t = el('text', {
            x: x, y: y, fill: color,
            'text-anchor': anchor || 'middle',
            'font-family': 'ui-monospace, SFMono-Regular, Menlo, monospace',
            'font-size': '9', 'font-weight': '700',
            'letter-spacing': '0.08em'
        });
        t.textContent = text;
        return t;
    }

    /* ── main draw routine ─────────────────────────────────────────── */
    function draw() {
        if (!svg) return;
        var vw   = window.innerWidth;
        var docH = Math.max(document.body.scrollHeight,
                            document.documentElement.scrollHeight);

        svg.setAttribute('width',  vw);
        svg.setAttribute('height', docH);
        svg.innerHTML = '';

        /* hide on narrow viewports — not enough margin space */
        if (vw < 1280) return;

        /* content box (max-w-5xl = 1024 px, centered, px-6 = 24 px padding) */
        var contentW = 1024;
        var contentL = (vw - contentW) / 2;
        var contentR = contentL + contentW;

        /* departure row: bottom edge of hero section */
        var hero = document.querySelector('section');
        if (!hero) return;
        var depY = hero.offsetTop + hero.offsetHeight;

        /* departure X positions — evenly spread across the content area */
        var depSpacing = contentW / (lines.length + 1);

        /* lane geometry — how far into each margin a lane sits */
        var laneGap = 20;   /* px between stacked lanes */
        var laneBase = 36;  /* first lane distance from content edge */

        for (var i = 0; i < lines.length; i++) {
            var ln = lines[i];
            var section = document.getElementById(ln.id);
            if (!section) continue;

            /* departure (start) coordinates */
            var dx = contentL + depSpacing * (i + 1);
            var dy = depY;

            /* target Y: just inside the section, below its border-top */
            var ty = section.offsetTop + 32;

            /* margin X for the vertical run */
            var mx;
            if (ln.side === 'left') {
                mx = contentL - laneBase - ln.lane * laneGap;
            } else {
                mx = contentR + laneBase + ln.lane * laneGap;
            }
            mx = Math.max(12, Math.min(vw - 12, mx));

            /* ── build metro path ─────────────────────────────────── */
            var diagDist = Math.abs(mx - dx);
            var seg1End  = dy + 40;                     /* short vertical out of station */
            var seg2End  = seg1End + diagDist;           /* 45° diagonal to margin */

            var d;
            if (seg2End < ty - 40) {
                /* plenty of room: vertical → diagonal → vertical → small horizontal into section */
                var endX = ln.side === 'left' ? contentL - 6 : contentR + 6;
                d = 'M ' + dx + ' ' + dy
                  + ' L ' + dx + ' ' + seg1End
                  + ' L ' + mx + ' ' + seg2End
                  + ' L ' + mx + ' ' + ty
                  + ' L ' + endX + ' ' + ty;
            } else {
                /* short distance — gentle diagonal straight to target */
                var endX2 = ln.side === 'left' ? contentL - 6 : contentR + 6;
                d = 'M ' + dx + ' ' + dy
                  + ' L ' + dx + ' ' + (dy + 30)
                  + ' L ' + mx + ' ' + (ty - 20)
                  + ' L ' + mx + ' ' + ty
                  + ' L ' + endX2 + ' ' + ty;
            }

            /* draw the path */
            svg.appendChild(el('path', {
                d: d,
                stroke: ln.color,
                'stroke-width': '3',
                fill: 'none',
                'stroke-linecap': 'round',
                'stroke-linejoin': 'round',
                opacity: '0.45'
            }));

            /* ── departure station circle + label ─────────────────── */
            svg.appendChild(circle(dx, dy, 5, ln.color));
            svg.appendChild(label(dx, dy - 12, ln.label, ln.color));

            /* ── terminal station circle + label ──────────────────── */
            var termX = ln.side === 'left' ? contentL - 6 : contentR + 6;
            svg.appendChild(circle(termX, ty, 7, 'white', ln.color, 3));

            var lblX   = ln.side === 'left' ? termX - 14 : termX + 14;
            var anchor = ln.side === 'left' ? 'end' : 'start';
            svg.appendChild(label(lblX, ty + 3, ln.label, ln.color, anchor));
        }
    }

    /* ── init ──────────────────────────────────────────────────────── */
    function init() {
        svg = document.createElementNS(NS, 'svg');
        svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;'
                          + 'pointer-events:none;z-index:15;overflow:visible;';
        document.body.style.position = 'relative';
        document.body.style.overflowX = 'hidden';
        document.body.appendChild(svg);
        draw();
        window.addEventListener('resize', draw);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
