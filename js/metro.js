/**
 * Metro Lines — decorative elbow-connector routes in the page margins.
 *
 * All lines run EXCLUSIVELY in the left / right gutters (outside the
 * max-w-5xl content container) so they never overlap any text.
 *
 * Layout per side:
 *   1. Departure circles sit in a horizontal row in the margin,
 *      just below the hero, with labels above.
 *   2. Each line drops straight down in its own lane.
 *   3. At the target section's Y it makes a clean right-angle elbow
 *      inward toward the content edge and terminates with a circle.
 *
 * Innermost lane = shortest route (terminates first), so later
 * horizontals never cross a still-active vertical line.
 *
 * Hidden below 1280 px (not enough margin space).
 */
(function () {
    var NS = 'http://www.w3.org/2000/svg';

    /* ── line definitions (ordered top→bottom per side) ──────────── */
    var leftLines = [
        { id: 'about',    label: 'PHILOSOPHY', color: '#D64045', lane: 0 },
        { id: 'resume',   label: 'RESUME',     color: '#2A9D8F', lane: 1 },
        { id: 'projects', label: 'PROJECTS',   color: '#E76F51', lane: 2 }
    ];
    var rightLines = [
        { id: 'roles',    label: 'DISCIPLINE', color: '#1B85B8', lane: 0 },
        { id: 'society',  label: 'SOCIETY',    color: '#C27D38', lane: 1 },
        { id: 'contact',  label: 'CONTACT',    color: '#7B6D8D', lane: 2 }
    ];

    var svg = null;

    /* ── SVG helpers ─────────────────────────────────────────────── */
    function el(tag, attrs) {
        var node = document.createElementNS(NS, tag);
        for (var k in attrs) node.setAttribute(k, attrs[k]);
        return node;
    }

    function addCircle(cx, cy, r, fill, stroke, sw) {
        svg.appendChild(el('circle', {
            cx: cx, cy: cy, r: r, fill: fill,
            stroke: stroke || 'none', 'stroke-width': sw || 0
        }));
    }

    function addLabel(x, y, text, color, anchor) {
        var t = el('text', {
            x: x, y: y, fill: color,
            'text-anchor': anchor || 'middle',
            'font-family': 'ui-monospace, SFMono-Regular, Menlo, monospace',
            'font-size': '9', 'font-weight': '700',
            'letter-spacing': '0.08em'
        });
        t.textContent = text;
        svg.appendChild(t);
    }

    function addPath(d, color) {
        svg.appendChild(el('path', {
            d: d, stroke: color, 'stroke-width': '3',
            fill: 'none', 'stroke-linecap': 'round',
            'stroke-linejoin': 'round', opacity: '0.5'
        }));
    }

    /* ── lane geometry ───────────────────────────────────────────── */
    var LANE_GAP  = 20;   /* px between parallel lanes            */
    var LANE_BASE = 28;   /* inner lane distance from content edge */

    function laneX(contentEdge, lane, side) {
        if (side === 'left')  return contentEdge - LANE_BASE - lane * LANE_GAP;
        return contentEdge + LANE_BASE + lane * LANE_GAP;
    }

    /* ── draw one side ───────────────────────────────────────────── */
    function drawSide(defs, contentEdge, side) {
        var hero = document.querySelector('section');
        if (!hero) return;
        var depY = hero.offsetTop + hero.offsetHeight + 16;

        /* departure connecting bar (horizontal line between outermost and innermost) */
        var innerX = laneX(contentEdge, 0, side);
        var outerX = laneX(contentEdge, defs.length - 1, side);
        svg.appendChild(el('line', {
            x1: innerX, y1: depY, x2: outerX, y2: depY,
            stroke: '#a8a29e', 'stroke-width': '2', opacity: '0.3'
        }));

        for (var i = 0; i < defs.length; i++) {
            var ln      = defs[i];
            var section = document.getElementById(ln.id);
            if (!section) continue;

            var lx  = laneX(contentEdge, ln.lane, side);
            var ty  = section.offsetTop + 30;  /* target Y: just inside the section */

            /* terminal X: near the content edge */
            var termX = side === 'left' ? contentEdge - 8 : contentEdge + 8;

            /* ── path: vertical drop → horizontal elbow ──────────── */
            var d = 'M ' + lx + ' ' + depY
                  + ' L ' + lx + ' ' + ty
                  + ' L ' + termX + ' ' + ty;
            addPath(d, ln.color);

            /* ── departure circle ────────────────────────────────── */
            addCircle(lx, depY, 5, ln.color);

            /* departure label (above circle) */
            addLabel(lx, depY - 12, ln.label, ln.color, 'middle');

            /* ── terminal circle ─────────────────────────────────── */
            addCircle(termX, ty, 6, 'white', ln.color, 3);

            /* terminal label (below the horizontal arm, tucked under) */
            var lblAnchor = side === 'left' ? 'end' : 'start';
            var lblX = side === 'left' ? termX - 10 : termX + 10;
            addLabel(lblX, ty + 18, ln.label, ln.color, lblAnchor);
        }
    }

    /* ── main draw routine ───────────────────────────────────────── */
    function draw() {
        if (!svg) return;
        var vw   = window.innerWidth;
        var docH = Math.max(document.body.scrollHeight,
                            document.documentElement.scrollHeight);

        svg.setAttribute('width',  vw);
        svg.setAttribute('height', docH);
        svg.innerHTML = '';

        if (vw < 1280) return;

        var contentW = 1024;
        var contentL = (vw - contentW) / 2;
        var contentR = contentL + contentW;

        drawSide(leftLines,  contentL, 'left');
        drawSide(rightLines, contentR, 'right');
    }

    /* ── init ─────────────────────────────────────────────────────── */
    function init() {
        svg = document.createElementNS(NS, 'svg');
        svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;'
                          + 'pointer-events:none;z-index:15;overflow:visible;';
        document.body.style.position  = 'relative';
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
