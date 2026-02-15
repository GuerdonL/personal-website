/**
 * Metro Lines — SVG route lines drawn on the 2D world canvas.
 *
 * Three lines radiate from the hero hub:
 *   Writer (red):      Hero → Writings → Poetry → About Me
 *   Programmer (teal): Hero → Resume
 *   Activist (purple): Hero → About Me → Society+Projects
 *
 * About Me is a shared station (Writer + Activist).
 * Lines are continuous through stations, routed around station edges
 * using 45° diagonal routing. Station circles are placed on station
 * edges and are clickable. Hidden on mobile (<768px).
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
                { from: 'hero', fromSide: 'bottom', to: 'about-me', toSide: 'top' },
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

    /* ── Station geometry ───────────────────────────────────── */

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
        var d = 0.7071;

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

    /**
     * Get the outside corner point of a station (with MARGIN offset).
     */
    function stationCorner(id, corner) {
        var s = document.getElementById(id);
        if (!s) return null;

        var l = s.offsetLeft;
        var t = s.offsetTop;
        var w = s.offsetWidth;
        var h = s.offsetHeight;

        switch (corner) {
            case 'top-right':    return { x: l + w + MARGIN, y: t - MARGIN };
            case 'bottom-right': return { x: l + w + MARGIN, y: t + h + MARGIN };
            case 'bottom-left':  return { x: l - MARGIN,     y: t + h + MARGIN };
            case 'top-left':     return { x: l - MARGIN,     y: t - MARGIN };
        }
        return null;
    }

    /**
     * Determine which outside corners to route through when a line
     * passes through a station (arrival side → departure side).
     * Returns array of corner names in order, taking the shortest path
     * around the station perimeter.
     */
    function throughStationCorners(arrivalSide, departureSide) {
        var sideIdx = { top: 0, right: 1, bottom: 2, left: 3 };
        var cornerNames = ['top-right', 'bottom-right', 'bottom-left', 'top-left'];

        var a = sideIdx[arrivalSide];
        var d = sideIdx[departureSide];

        if (a === undefined || d === undefined || a === d) return [];

        // Clockwise path: from a, step clockwise collecting corners until reaching d
        var cw = [];
        var i = a;
        while (i !== d) {
            cw.push(cornerNames[i]);
            i = (i + 1) % 4;
        }

        // Counter-clockwise path
        var ccw = [];
        i = a;
        while (i !== d) {
            var prev = (i + 3) % 4;
            ccw.push(cornerNames[prev]);
            i = prev;
        }

        return cw.length <= ccw.length ? cw : ccw;
    }

    /* ── Metro-style path routing ───────────────────────────── */

    /**
     * Generate SVG path commands (L commands only) for a metro-style
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

        if (adx < 1 && ady < 1) {
            return ' L ' + x2 + ' ' + y2;
        }

        if (adx >= ady) {
            var diag = ady;
            var straight = adx - diag;
            var half = straight / 2;
            var mx1x = x1 + sx * half;
            var mx2x = mx1x + sx * diag;
            return ' L ' + mx1x + ' ' + y1
                 + ' L ' + mx2x + ' ' + y2
                 + ' L ' + x2 + ' ' + y2;
        } else {
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
     * Route from anchor A to anchor B through optional waypoints.
     * Returns SVG path fragment (L commands only, no M).
     */
    function routeThrough(from, to, waypoints) {
        var stubA = { x: from.x + from.dx * STUB, y: from.y + from.dy * STUB };
        var stubB = { x: to.x + to.dx * STUB, y: to.y + to.dy * STUB };

        var d = ' L ' + stubA.x + ' ' + stubA.y;

        var points = [];
        if (waypoints) {
            for (var i = 0; i < waypoints.length; i++) {
                points.push(waypoints[i]);
            }
        }
        points.push(stubB);

        var prev = stubA;
        for (var i = 0; i < points.length; i++) {
            var pt = points[i];
            d += metroConnect(prev.x, prev.y, pt.x, pt.y);
            prev = pt;
        }

        d += ' L ' + to.x + ' ' + to.y;
        return d;
    }

    /**
     * Build one continuous SVG path for an entire line.
     * Between consecutive segments at the same station, the line routes
     * around the outside corners of the station rather than cutting through.
     */
    function buildLinePath(lineDef) {
        var segments = lineDef.segments;
        var anchors = [];
        var d = '';

        for (var i = 0; i < segments.length; i++) {
            var seg = segments[i];
            var from = stationAnchor(seg.from, seg.fromSide);
            var to = stationAnchor(seg.to, seg.toSide);
            if (!from || !to) return null;

            if (i === 0) {
                d = 'M ' + from.x + ' ' + from.y;
            } else {
                // Route around the outside of the intermediate station
                var prevSeg = segments[i - 1];
                var stationId = seg.from; // same station as prevSeg.to
                var corners = throughStationCorners(prevSeg.toSide, seg.fromSide);

                for (var c = 0; c < corners.length; c++) {
                    var cp = stationCorner(stationId, corners[c]);
                    if (cp) d += ' L ' + cp.x + ' ' + cp.y;
                }

                d += ' L ' + from.x + ' ' + from.y;
            }

            d += routeThrough(from, to, seg.waypoints);

            anchors.push({
                stationId: seg.to,
                x: to.x,
                y: to.y,
                segIndex: i
            });
        }

        return { d: d, anchors: anchors };
    }

    /* ── Drawing ────────────────────────────────────────────── */

    /**
     * Draw a half-circle arc path for split station circles.
     */
    function halfCirclePath(cx, cy, r, side) {
        if (side === 'left') {
            return 'M ' + cx + ' ' + (cy - r)
                 + ' A ' + r + ' ' + r + ' 0 0 0 ' + cx + ' ' + (cy + r);
        } else {
            return 'M ' + cx + ' ' + (cy - r)
                 + ' A ' + r + ' ' + r + ' 0 0 1 ' + cx + ' ' + (cy + r);
        }
    }

    /**
     * Draw all metro lines and station circles.
     * Shared stations (e.g. about-me) get a split-color circle.
     */
    function drawAll() {
        var stationCircles = {};

        for (var key in LINES) {
            var lineDef = LINES[key];
            var result = buildLinePath(lineDef);
            if (!result) continue;

            svg.appendChild(el('path', {
                d: result.d,
                stroke: lineDef.color,
                'stroke-width': '4',
                fill: 'none',
                'stroke-linecap': 'round',
                'stroke-linejoin': 'round',
                opacity: '0.6'
            }));

            var segments = lineDef.segments;
            for (var i = 0; i < result.anchors.length; i++) {
                var a = result.anchors[i];
                if (a.stationId === 'hero') continue;

                var nextStop = (a.segIndex < segments.length - 1)
                    ? segments[a.segIndex + 1].to
                    : 'hero';

                if (!stationCircles[a.stationId]) {
                    stationCircles[a.stationId] = [];
                }
                stationCircles[a.stationId].push({
                    color: lineDef.color,
                    x: a.x,
                    y: a.y,
                    lineKey: key,
                    nextStop: nextStop
                });
            }
        }

        // Draw station circles, merging shared stations
        for (var stationId in stationCircles) {
            var entries = stationCircles[stationId];

            // Use first entry's position (all arrivals at same side now for shared stations)
            var cx = entries[0].x;
            var cy = entries[0].y;

            var R = 12;
            var sid = stationId;

            // For shared stations, prefer the next-stop that continues the journey
            // (i.e. not 'hero') so clicking advances meaningfully
            var defaultNext = entries[0].nextStop;
            for (var i = 0; i < entries.length; i++) {
                if (entries[i].nextStop !== 'hero') {
                    defaultNext = entries[i].nextStop;
                    break;
                }
            }

            if (entries.length === 1) {
                var color = entries[0].color;
                var outer = el('circle', {
                    cx: cx, cy: cy, r: R,
                    fill: 'white',
                    stroke: color,
                    'stroke-width': '4',
                    'class': 'metro-stop',
                    'data-station': sid,
                    style: 'cursor:pointer; pointer-events:all;'
                });
                outer.addEventListener('click', (function (s, ns) {
                    return function () {
                        if (window.getCurrentStation && window.getCurrentStation() === s) {
                            window.panTo(ns);
                        } else {
                            window.panTo(s);
                        }
                    };
                })(sid, defaultNext));
                svg.appendChild(outer);

                svg.appendChild(el('circle', {
                    cx: cx, cy: cy, r: '5',
                    fill: color,
                    'pointer-events': 'none'
                }));
            } else {
                // Shared station: split circle
                var color1 = entries[0].color;
                var color2 = entries[1].color;

                // White background
                svg.appendChild(el('circle', {
                    cx: cx, cy: cy, r: R + 2,
                    fill: 'white',
                    'pointer-events': 'none'
                }));

                // Left half stroke (color1)
                svg.appendChild(el('path', {
                    d: halfCirclePath(cx, cy, R, 'left'),
                    stroke: color1,
                    'stroke-width': '4',
                    fill: 'none',
                    'stroke-linecap': 'round',
                    'pointer-events': 'none'
                }));

                // Right half stroke (color2)
                svg.appendChild(el('path', {
                    d: halfCirclePath(cx, cy, R, 'right'),
                    stroke: color2,
                    'stroke-width': '4',
                    fill: 'none',
                    'stroke-linecap': 'round',
                    'pointer-events': 'none'
                }));

                // Left half inner fill
                svg.appendChild(el('path', {
                    d: halfCirclePath(cx, cy, 5, 'left') + ' Z',
                    fill: color1,
                    stroke: 'none',
                    'pointer-events': 'none'
                }));

                // Right half inner fill
                svg.appendChild(el('path', {
                    d: halfCirclePath(cx, cy, 5, 'right') + ' Z',
                    fill: color2,
                    stroke: 'none',
                    'pointer-events': 'none'
                }));

                // Invisible clickable circle
                var clickCircle = el('circle', {
                    cx: cx, cy: cy, r: R + 2,
                    fill: 'transparent',
                    'class': 'metro-stop',
                    'data-station': sid,
                    style: 'cursor:pointer; pointer-events:all;'
                });
                clickCircle.addEventListener('click', (function (s, ns) {
                    return function () {
                        if (window.getCurrentStation && window.getCurrentStation() === s) {
                            window.panTo(ns);
                        } else {
                            window.panTo(s);
                        }
                    };
                })(sid, defaultNext));
                svg.appendChild(clickCircle);
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

        drawAll();
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
