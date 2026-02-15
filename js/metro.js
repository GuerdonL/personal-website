/**
 * Metro Lines — SVG route lines drawn on the 2D world canvas.
 *
 * Three lines radiate from the hero hub:
 *   Writer (red):     Hero → Writings → Poetry → About Me
 *   Programmer (teal): Hero → Resume
 *   Activist (purple): Hero → About Me → Society+Projects
 *
 * About Me is a shared station (Writer + Activist).
 * Lines use orthogonal elbow routing. Station circles are clickable.
 * Hidden on mobile (<768px).
 */
(function () {
    var NS = 'http://www.w3.org/2000/svg';

    var LINES = {
        writer: {
            color: '#D64045',
            stops: ['hero', 'writings', 'poetry', 'about-me']
        },
        programmer: {
            color: '#2A9D8F',
            stops: ['hero', 'resume']
        },
        activist: {
            color: '#7B6D8D',
            stops: ['hero', 'about-me', 'society-projects']
        }
    };

    var WORLD_W = 4000;
    var WORLD_H = 3000;

    var svg = null;

    /* ── SVG helpers ─────────────────────────────────────────── */
    function el(tag, attrs) {
        var node = document.createElementNS(NS, tag);
        for (var k in attrs) node.setAttribute(k, attrs[k]);
        return node;
    }

    /**
     * Get the center point of a station element.
     */
    function stationCenter(id) {
        var s = document.getElementById(id);
        if (!s) return null;
        return {
            x: s.offsetLeft + s.offsetWidth / 2,
            y: s.offsetTop + s.offsetHeight / 2
        };
    }

    /**
     * Build an orthogonal (elbow) path between two points.
     * Routes: go vertical first to the target's Y, then horizontal.
     */
    function elbowPath(from, to) {
        // Midpoint Y for the elbow
        var midY = from.y + (to.y - from.y) * 0.5;
        return 'M ' + from.x + ' ' + from.y
             + ' L ' + from.x + ' ' + midY
             + ' L ' + to.x + ' ' + midY
             + ' L ' + to.x + ' ' + to.y;
    }

    /**
     * Draw a single metro line with all its segments and station circles.
     */
    function drawLine(lineKey, lineDef) {
        var color = lineDef.color;
        var stops = lineDef.stops;
        var centers = [];

        for (var i = 0; i < stops.length; i++) {
            var c = stationCenter(stops[i]);
            if (!c) return;
            centers.push(c);
        }

        // Draw path segments between consecutive stops
        for (var i = 0; i < centers.length - 1; i++) {
            var d = elbowPath(centers[i], centers[i + 1]);
            var path = el('path', {
                d: d,
                stroke: color,
                'stroke-width': '4',
                fill: 'none',
                'stroke-linecap': 'round',
                'stroke-linejoin': 'round',
                opacity: '0.6'
            });
            svg.appendChild(path);
        }

        // Draw station circles (skip hero — it gets special treatment)
        for (var i = 1; i < centers.length; i++) {
            var c = centers[i];
            var stopId = stops[i];
            var nextStopId = (i < stops.length - 1) ? stops[i + 1] : 'hero';

            // Outer circle (line color)
            var outer = el('circle', {
                cx: c.x, cy: c.y, r: '12',
                fill: 'white',
                stroke: color,
                'stroke-width': '4',
                'class': 'metro-stop',
                'data-station': stopId,
                style: 'cursor:pointer; pointer-events:all;'
            });
            outer.addEventListener('click', (function (sid, nextSid) {
                return function () {
                    // If already at this station, advance to next stop
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
                cx: c.x, cy: c.y, r: '5',
                fill: color,
                'pointer-events': 'none'
            });
            svg.appendChild(inner);
        }
    }

    /**
     * Draw departure indicators on the hero station.
     */
    function drawHeroDepartures() {
        var hero = document.getElementById('hero');
        if (!hero) return;

        var hx = hero.offsetLeft + hero.offsetWidth / 2;
        var hy = hero.offsetTop + hero.offsetHeight - 20;

        // Small colored departure circles at the bottom of hero
        var lineKeys = ['writer', 'programmer', 'activist'];
        var spacing = 40;
        var startX = hx - (lineKeys.length - 1) * spacing / 2;

        for (var i = 0; i < lineKeys.length; i++) {
            var color = LINES[lineKeys[i]].color;
            var cx = startX + i * spacing;

            svg.appendChild(el('circle', {
                cx: cx, cy: hy, r: '8',
                fill: color,
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
