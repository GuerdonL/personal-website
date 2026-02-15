/**
 * Metro Lines — SVG route lines drawn on the 2D world canvas.
 *
 * Three lines radiate from the hero hub:
 *   Writer (red):      Hero → Writings → Poetry → About Me
 *   Programmer (teal): Hero → Resume
 *   Activist (purple): Hero → About Me → Society+Projects
 *
 * About Me is a shared station (Writer + Activist).
 * Lines use 45° diagonal transitions with obstacle-avoiding routing.
 * Station circles are placed on station edges and are clickable.
 * Hidden on mobile (<768px).
 */
(function () {
    var NS = 'http://www.w3.org/2000/svg';

    var MARGIN = 15;   // px outward from station edge for anchor points
    var STUB = 50;     // px outward stub before routing

    var LINES = {
        writer: {
            color: '#D64045',
            segments: [
                { from: 'hero', fromSide: 'left', to: 'writings', toSide: 'right' },
                { from: 'writings', fromSide: 'top', to: 'poetry', toSide: 'bottom' },
                { from: 'poetry', fromSide: 'left', to: 'about-me', toSide: 'top',
                  waypoints: [{ x: 20, y: 1500 }] }
            ]
        },
        programmer: {
            color: '#2A9D8F',
            segments: [
                { from: 'hero', fromSide: 'right', to: 'resume', toSide: 'left' }
            ]
        },
        activist: {
            color: '#7B6D8D',
            segments: [
                { from: 'hero', fromSide: 'bottom', to: 'about-me', toSide: 'top-right' },
                { from: 'about-me', fromSide: 'right', to: 'society-projects', toSide: 'left' }
            ]
        }
    };

    var WORLD_W = 4000;
    var WORLD_H = 4000;

    var svg = null;

    /* ── SVG helpers ─────────────────────────────────────────── */
    function el(tag, attrs) {
        var node = document.createElementNS(NS, tag);
        for (var k in attrs) node.setAttribute(k, attrs[k]);
        return node;
    }

    /* ── Station anchor calculation ─────────────────────────── */

    /**
     * Get an anchor point on a station's edge.
     * Returns { x, y, dx, dy } where (x,y) is MARGIN px outside the edge
     * and (dx,dy) is the outward unit direction.
     */
    function stationAnchor(id, side) {
        var s = document.getElementById(id);
        if (!s) return null;

        var left = s.offsetLeft;
        var top = s.offsetTop;
        var w = s.offsetWidth;
        var h = s.offsetHeight;
        var cx = left + w / 2;
        var cy = top + h / 2;
        var d = 0.7071; // 1/sqrt(2)

        switch (side) {
            case 'left':
                return { x: left - MARGIN, y: cy, dx: -1, dy: 0 };
            case 'right':
                return { x: left + w + MARGIN, y: cy, dx: 1, dy: 0 };
            case 'top':
                return { x: cx, y: top - MARGIN, dx: 0, dy: -1 };
            case 'bottom':
                return { x: cx, y: top + h + MARGIN, dx: 0, dy: 1 };
            case 'top-left':
                return { x: left - MARGIN * d, y: top - MARGIN * d, dx: -d, dy: -d };
            case 'top-right':
                return { x: left + w + MARGIN * d, y: top - MARGIN * d, dx: d, dy: -d };
            case 'bottom-left':
                return { x: left - MARGIN * d, y: top + h + MARGIN * d, dx: -d, dy: d };
            case 'bottom-right':
                return { x: left + w + MARGIN * d, y: top + h + MARGIN * d, dx: d, dy: d };
            default:
                return { x: cx, y: cy, dx: 0, dy: 0 };
        }
    }

    /* ── Metro-style path routing ───────────────────────────── */

    /**
     * Generate SVG path commands (without leading M) for a metro-style
     * route between two points using H/V/45° segments.
     * Pattern: straight → centered diagonal → straight.
     */
    function metroConnect(x1, y1, x2, y2) {
        var dx = x2 - x1;
        var dy = y2 - y1;
        var adx = Math.abs(dx);
        var ady = Math.abs(dy);
        var sx = dx >= 0 ? 1 : -1;
        var sy = dy >= 0 ? 1 : -1;

        // Degenerate: basically the same point
        if (adx < 1 && ady < 1) {
            return ' L ' + x2 + ' ' + y2;
        }

        if (adx >= ady) {
            // Horizontal dominant: H → 45° diagonal → H
            var diag = ady;
            var straight = adx - diag;
            var half = straight / 2;
            var mx1x = x1 + sx * half;
            var mx2x = mx1x + sx * diag;
            return ' L ' + mx1x + ' ' + y1
                 + ' L ' + mx2x + ' ' + y2
                 + ' L ' + x2 + ' ' + y2;
        } else {
            // Vertical dominant: V → 45° diagonal → V
            var diag = adx;
            var straight = ady - diag;
            var half = straight / 2;
            var my1 = y1 + sy * half;
            var my2 = my1 + sy * diag;
            return ' L ' + x1 + ' ' + my1
                 + ' L ' + x2 + ' ' + my2
                 + ' L ' + x2 + ' ' + y2;
        }
    }

    /**
     * Build the full SVG path 'd' string for a segment.
     * Adds outward stubs at departure and arrival, then routes through
     * optional waypoints using metroConnect.
     */
    function buildSegmentPath(seg) {
        var a = stationAnchor(seg.from, seg.fromSide);
        var b = stationAnchor(seg.to, seg.toSide);
        if (!a || !b) return null;

        // Stub endpoints (extend outward from anchor)
        var stubA = { x: a.x + a.dx * STUB, y: a.y + a.dy * STUB };
        var stubB = { x: b.x + b.dx * STUB, y: b.y + b.dy * STUB };

        // Start the path at the anchor, line to stub
        var d = 'M ' + a.x + ' ' + a.y + ' L ' + stubA.x + ' ' + stubA.y;

        // Build the chain of points to route through
        var points = [];
        if (seg.waypoints) {
            for (var i = 0; i < seg.waypoints.length; i++) {
                points.push(seg.waypoints[i]);
            }
        }
        points.push(stubB);

        // Route from stubA through each point
        var prev = stubA;
        for (var i = 0; i < points.length; i++) {
            var pt = points[i];
            d += metroConnect(prev.x, prev.y, pt.x, pt.y);
            prev = pt;
        }

        // Final line from stub to arrival anchor
        d += ' L ' + b.x + ' ' + b.y;

        return { d: d, arrival: b };
    }

    /* ── Drawing ────────────────────────────────────────────── */

    /**
     * Draw a single metro line with all its segments and station circles.
     */
    function drawLine(lineKey, lineDef) {
        var color = lineDef.color;
        var segments = lineDef.segments;

        for (var i = 0; i < segments.length; i++) {
            var seg = segments[i];
            var result = buildSegmentPath(seg);
            if (!result) continue;

            // Draw path
            var path = el('path', {
                d: result.d,
                stroke: color,
                'stroke-width': '4',
                fill: 'none',
                'stroke-linecap': 'round',
                'stroke-linejoin': 'round',
                opacity: '0.6'
            });
            svg.appendChild(path);

            // Draw station circle at arrival anchor (skip hero)
            if (seg.to !== 'hero') {
                var stopId = seg.to;
                // Determine next stop: next segment's 'to', or loop to hero
                var nextStopId = (i < segments.length - 1) ? segments[i + 1].to : 'hero';

                var cx = result.arrival.x;
                var cy = result.arrival.y;

                // Outer circle (white with line color stroke)
                var outer = el('circle', {
                    cx: cx, cy: cy, r: '12',
                    fill: 'white',
                    stroke: color,
                    'stroke-width': '4',
                    'class': 'metro-stop',
                    'data-station': stopId,
                    style: 'cursor:pointer; pointer-events:all;'
                });
                outer.addEventListener('click', (function (sid, nextSid) {
                    return function () {
                        if (window.getCurrentStation && window.getCurrentStation() === sid) {
                            window.panTo(nextSid);
                        } else {
                            window.panTo(sid);
                        }
                    };
                })(stopId, nextStopId));
                svg.appendChild(outer);

                // Inner dot
                var inner = el('circle', {
                    cx: cx, cy: cy, r: '5',
                    fill: color,
                    'pointer-events': 'none'
                });
                svg.appendChild(inner);
            }
        }
    }

    /**
     * Draw departure indicators on the hero station at each line's
     * actual departure anchor.
     */
    function drawHeroDepartures() {
        var lineKeys = ['writer', 'programmer', 'activist'];

        for (var i = 0; i < lineKeys.length; i++) {
            var key = lineKeys[i];
            var line = LINES[key];
            var firstSeg = line.segments[0];
            if (firstSeg.from !== 'hero') continue;

            var anchor = stationAnchor('hero', firstSeg.fromSide);
            if (!anchor) continue;

            svg.appendChild(el('circle', {
                cx: anchor.x, cy: anchor.y, r: '8',
                fill: line.color,
                opacity: '0.8'
            }));
        }
    }

    /* ── main draw ───────────────────────────────────────────── */
    function draw() {
        if (!svg) return;

        svg.innerHTML = '';
        svg.setAttribute('width', WORLD_W);
        svg.setAttribute('height', WORLD_H);

        if (window.innerWidth < 768) return;

        // Draw lines
        for (var key in LINES) {
            drawLine(key, LINES[key]);
        }

        // Draw hero departure indicators
        drawHeroDepartures();
    }

    /* ── init ─────────────────────────────────────────────────── */
    function init() {
        var world = document.getElementById('metro-world');
        if (!world) return;

        svg = document.createElementNS(NS, 'svg');
        svg.id = 'metro-svg';
        svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;'
                          + 'pointer-events:none;z-index:5;overflow:visible;';
        world.appendChild(svg);

        draw();
        window.addEventListener('resize', draw);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
