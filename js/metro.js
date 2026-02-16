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
 *
 * Exposes window.getMetroRoute(from, to) for path-following navigation.
 */
(function () {
    var NS = 'http://www.w3.org/2000/svg';

    var MARGIN = 15;
    var STUB = 50;

    var LINES = {
        writer: {
            color: '#D64045',
            segments: [
                { from: 'hero', fromSide: 'right', to: 'writings', toSide: 'left' },
                { from: 'writings', fromSide: 'bottom', to: 'about-me', toSide: 'top' }
            ]
        },
        programmer: {
            color: '#2A9D8F',
            segments: [
                { from: 'hero', fromSide: 'left', to: 'resume', toSide: 'right' }
            ]
        },
        activist: {
            color: '#7B6D8D',
            segments: [
                { from: 'hero', fromSide: 'bottom', to: 'about-me', toSide: 'top' },
                { from: 'about-me', fromSide: 'left', to: 'society-projects', toSide: 'right' }
            ]
        }
    };

    var WORLD_W = 8500;
    var WORLD_H = 6000;

    var svg = null;
    var routeData = null;

    /* ── SVG helpers ─────────────────────────────────────────── */
    function el(tag, attrs) {
        var node = document.createElementNS(NS, tag);
        for (var k in attrs) node.setAttribute(k, attrs[k]);
        return node;
    }

    /* ── Station geometry ───────────────────────────────────── */

    function stationCenter(id) {
        var s = document.getElementById(id);
        if (!s) return null;
        return {
            x: s.offsetLeft + s.offsetWidth / 2,
            y: s.offsetTop + s.offsetHeight / 2
        };
    }

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

    function throughStationCorners(arrivalSide, departureSide) {
        var sideIdx = { top: 0, right: 1, bottom: 2, left: 3 };
        var cornerNames = ['top-right', 'bottom-right', 'bottom-left', 'top-left'];
        var a = sideIdx[arrivalSide];
        var d = sideIdx[departureSide];
        if (a === undefined || d === undefined || a === d) return [];

        var cw = [];
        var i = a;
        while (i !== d) { cw.push(cornerNames[i]); i = (i + 1) % 4; }

        var ccw = [];
        i = a;
        while (i !== d) { var p = (i + 3) % 4; ccw.push(cornerNames[p]); i = p; }

        return cw.length <= ccw.length ? cw : ccw;
    }

    /* ── Metro-style path routing ───────────────────────────── */

    /**
     * Metro-connect between two points. Returns array of intermediate
     * + endpoint {x,y} (does NOT include the start point).
     */
    function metroConnectPoints(x1, y1, x2, y2) {
        var dx = x2 - x1;
        var dy = y2 - y1;
        var adx = Math.abs(dx);
        var ady = Math.abs(dy);
        var sx = dx >= 0 ? 1 : -1;
        var sy = dy >= 0 ? 1 : -1;

        if (adx < 1 && ady < 1) return [{ x: x2, y: y2 }];

        if (adx >= ady) {
            var diag = ady;
            var half = (adx - diag) / 2;
            var mx1x = x1 + sx * half;
            var mx2x = mx1x + sx * diag;
            return [
                { x: mx1x, y: y1 },
                { x: mx2x, y: y2 },
                { x: x2, y: y2 }
            ];
        } else {
            var diag = adx;
            var half = (ady - diag) / 2;
            var my1 = y1 + sy * half;
            var my2 = my1 + sy * diag;
            return [
                { x: x1, y: my1 },
                { x: x2, y: my2 },
                { x: x2, y: y2 }
            ];
        }
    }

    /** Convert points array to SVG L commands string. */
    function pointsToPath(pts) {
        var d = '';
        for (var i = 0; i < pts.length; i++) {
            d += ' L ' + pts[i].x + ' ' + pts[i].y;
        }
        return d;
    }

    /**
     * Build one continuous SVG path for an entire line.
     * Also collects all path points and per-stop indices for route data.
     */
    function buildLinePath(lineDef) {
        var segments = lineDef.segments;
        var anchors = [];
        var allPoints = [];
        var stopIndices = [];
        var d = '';

        for (var i = 0; i < segments.length; i++) {
            var seg = segments[i];
            var from = stationAnchor(seg.from, seg.fromSide);
            var to = stationAnchor(seg.to, seg.toSide);
            if (!from || !to) return null;

            if (i === 0) {
                d = 'M ' + from.x + ' ' + from.y;
                allPoints.push({ x: from.x, y: from.y });
                stopIndices.push(0);
            } else {
                // Route around outside of intermediate station
                var prevSeg = segments[i - 1];
                var sid = seg.from;
                var corners = throughStationCorners(prevSeg.toSide, seg.fromSide);
                for (var c = 0; c < corners.length; c++) {
                    var cp = stationCorner(sid, corners[c]);
                    if (cp) {
                        d += ' L ' + cp.x + ' ' + cp.y;
                        allPoints.push({ x: cp.x, y: cp.y });
                    }
                }
                d += ' L ' + from.x + ' ' + from.y;
                allPoints.push({ x: from.x, y: from.y });
            }

            // Departure stub
            var stubA = { x: from.x + from.dx * STUB, y: from.y + from.dy * STUB };
            d += ' L ' + stubA.x + ' ' + stubA.y;
            allPoints.push(stubA);

            // Build target chain: waypoints + arrival stub
            var stubB = { x: to.x + to.dx * STUB, y: to.y + to.dy * STUB };
            var targets = [];
            if (seg.waypoints) {
                for (var w = 0; w < seg.waypoints.length; w++) {
                    targets.push(seg.waypoints[w]);
                }
            }
            targets.push(stubB);

            // Route through targets
            var prev = stubA;
            for (var t = 0; t < targets.length; t++) {
                var pt = targets[t];
                var mcPts = metroConnectPoints(prev.x, prev.y, pt.x, pt.y);
                d += pointsToPath(mcPts);
                for (var j = 0; j < mcPts.length; j++) allPoints.push(mcPts[j]);
                prev = pt;
            }

            // Arrival anchor
            d += ' L ' + to.x + ' ' + to.y;
            allPoints.push({ x: to.x, y: to.y });
            stopIndices.push(allPoints.length - 1);

            anchors.push({ stationId: seg.to, x: to.x, y: to.y, segIndex: i });
        }

        return { d: d, anchors: anchors, allPoints: allPoints, stopIndices: stopIndices };
    }

    /* ── Route data for navigation ─────────────────────────── */

    function buildRouteData(lineResults) {
        var data = {};
        for (var key in lineResults) {
            var lineDef = LINES[key];
            var result = lineResults[key];
            var stops = [lineDef.segments[0].from];
            for (var i = 0; i < lineDef.segments.length; i++) {
                stops.push(lineDef.segments[i].to);
            }
            data[key] = {
                stops: stops,
                points: result.allPoints,
                stopIndices: result.stopIndices
            };
        }
        return data;
    }

    function routeDistance(pts) {
        var d = 0;
        for (var i = 1; i < pts.length; i++) {
            var dx = pts[i].x - pts[i - 1].x;
            var dy = pts[i].y - pts[i - 1].y;
            d += Math.sqrt(dx * dx + dy * dy);
        }
        return d;
    }

    function extractRoute(lineData, fromIdx, toIdx) {
        var forward = fromIdx < toIdx;
        var lo = forward ? fromIdx : toIdx;
        var hi = forward ? toIdx : fromIdx;
        var pts = lineData.points.slice(lineData.stopIndices[lo], lineData.stopIndices[hi] + 1);
        if (!forward) pts = pts.slice().reverse();
        return pts;
    }

    window.getMetroRoute = function (fromStation, toStation) {
        if (fromStation === toStation || !routeData) return null;

        var bestRoute = null;
        var bestDist = Infinity;

        // Try direct route (both stations on same line)
        for (var key in routeData) {
            var line = routeData[key];
            var fi = line.stops.indexOf(fromStation);
            var ti = line.stops.indexOf(toStation);
            if (fi !== -1 && ti !== -1 && fi !== ti) {
                var route = extractRoute(line, fi, ti);
                var dist = routeDistance(route);
                if (dist < bestDist) { bestDist = dist; bestRoute = route; }
            }
        }

        // Try cross-line route through hero
        if (!bestRoute && fromStation !== 'hero' && toStation !== 'hero') {
            var toHero = [];
            var fromHero = [];
            for (var key in routeData) {
                var line = routeData[key];
                var fi = line.stops.indexOf(fromStation);
                var hi = line.stops.indexOf('hero');
                if (fi !== -1 && hi !== -1 && fi !== hi)
                    toHero.push(extractRoute(line, fi, hi));
                var hi2 = line.stops.indexOf('hero');
                var ti = line.stops.indexOf(toStation);
                if (hi2 !== -1 && ti !== -1 && hi2 !== ti)
                    fromHero.push(extractRoute(line, hi2, ti));
            }
            for (var i = 0; i < toHero.length; i++) {
                for (var j = 0; j < fromHero.length; j++) {
                    var combined = toHero[i].concat(fromHero[j].slice(1));
                    var dist = routeDistance(combined);
                    if (dist < bestDist) { bestDist = dist; bestRoute = combined; }
                }
            }
        }

        if (!bestRoute) return null;

        // Prepend source station center, append target station center
        var fc = stationCenter(fromStation);
        var tc = stationCenter(toStation);
        if (fc) bestRoute.unshift(fc);
        if (tc) bestRoute.push(tc);

        return bestRoute;
    };

    /* ── Drawing ────────────────────────────────────────────── */

    function halfCirclePath(cx, cy, r, side) {
        if (side === 'left') {
            return 'M ' + cx + ' ' + (cy - r)
                 + ' A ' + r + ' ' + r + ' 0 0 0 ' + cx + ' ' + (cy + r);
        } else {
            return 'M ' + cx + ' ' + (cy - r)
                 + ' A ' + r + ' ' + r + ' 0 0 1 ' + cx + ' ' + (cy + r);
        }
    }

    function drawAll() {
        var stationCircles = {};
        var lineResults = {};

        for (var key in LINES) {
            var lineDef = LINES[key];
            var result = buildLinePath(lineDef);
            if (!result) continue;
            lineResults[key] = result;

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
                    ? segments[a.segIndex + 1].to : 'hero';
                if (!stationCircles[a.stationId]) stationCircles[a.stationId] = [];
                stationCircles[a.stationId].push({
                    color: lineDef.color, x: a.x, y: a.y,
                    lineKey: key, nextStop: nextStop
                });
            }
        }

        // Build route data for navigation
        routeData = buildRouteData(lineResults);

        // Draw station circles
        for (var stationId in stationCircles) {
            var entries = stationCircles[stationId];
            var cx = entries[0].x;
            var cy = entries[0].y;
            var R = 12;
            var sid = stationId;

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
                    fill: 'white', stroke: color, 'stroke-width': '4',
                    'class': 'metro-stop', 'data-station': sid,
                    style: 'cursor:pointer; pointer-events:all;'
                });
                outer.addEventListener('click', (function (s, ns) {
                    return function () {
                        if (window.getCurrentStation && window.getCurrentStation() === s)
                            window.panTo(ns);
                        else window.panTo(s);
                    };
                })(sid, defaultNext));
                svg.appendChild(outer);
                svg.appendChild(el('circle', {
                    cx: cx, cy: cy, r: '5', fill: color, 'pointer-events': 'none'
                }));
            } else {
                var color1 = entries[0].color;
                var color2 = entries[1].color;

                svg.appendChild(el('circle', {
                    cx: cx, cy: cy, r: R + 2, fill: 'white', 'pointer-events': 'none'
                }));
                svg.appendChild(el('path', {
                    d: halfCirclePath(cx, cy, R, 'left'),
                    stroke: color1, 'stroke-width': '4', fill: 'none',
                    'stroke-linecap': 'round', 'pointer-events': 'none'
                }));
                svg.appendChild(el('path', {
                    d: halfCirclePath(cx, cy, R, 'right'),
                    stroke: color2, 'stroke-width': '4', fill: 'none',
                    'stroke-linecap': 'round', 'pointer-events': 'none'
                }));
                svg.appendChild(el('path', {
                    d: halfCirclePath(cx, cy, 5, 'left') + ' Z',
                    fill: color1, stroke: 'none', 'pointer-events': 'none'
                }));
                svg.appendChild(el('path', {
                    d: halfCirclePath(cx, cy, 5, 'right') + ' Z',
                    fill: color2, stroke: 'none', 'pointer-events': 'none'
                }));

                var clickCircle = el('circle', {
                    cx: cx, cy: cy, r: R + 2, fill: 'transparent',
                    'class': 'metro-stop', 'data-station': sid,
                    style: 'cursor:pointer; pointer-events:all;'
                });
                clickCircle.addEventListener('click', (function (s, ns) {
                    return function () {
                        if (window.getCurrentStation && window.getCurrentStation() === s)
                            window.panTo(ns);
                        else window.panTo(s);
                    };
                })(sid, defaultNext));
                svg.appendChild(clickCircle);
            }
        }
    }

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
                fill: line.color, opacity: '0.8'
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
