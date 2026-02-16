/**
 * Map Navigation — panning engine for the 2D metro world.
 *
 * panTo(stationId) smoothly translates #metro-world so the target
 * station is centered in the viewport.  When a metro route exists
 * between the current and target stations, the viewport follows
 * the metro line path.  On mobile (<768px) falls back to scrollIntoView().
 */
(function () {
    var world = null;
    var viewport = null;
    var hubBtn = null;
    var currentStation = 'hero';
    var animFrameId = null;

    var WORLD_W = 8500;
    var WORLD_H = 6000;

    // Per-station scale multipliers (zoom out a bit for tight stations)
    var SCALE_FACTOR = {
        'about-me': 0.85
    };

    function isMobile() {
        return window.innerWidth < 768;
    }

    /**
     * Compute the transform parameters (tx, ty, scale) needed to
     * center a given station in the viewport.
     */
    function computeStationTransform(stationId) {
        var station = document.getElementById(stationId);
        if (!station || !viewport) return null;

        var sw = station.offsetWidth;
        var sh = station.offsetHeight;
        var sx = station.offsetLeft + sw / 2;
        var sy = station.offsetTop + sh / 2;

        var vw = viewport.offsetWidth;
        var vh = viewport.offsetHeight;

        var padTop = 80;
        var padBottom = 40;
        var padX = 60;
        var availW = vw - padX * 2;
        var availH = vh - padTop - padBottom;

        var scale = Math.min(availW / sw, availH / sh, 1);
        if (SCALE_FACTOR[stationId]) scale *= SCALE_FACTOR[stationId];

        var targetX = vw / 2;
        var targetY = padTop + availH / 2;

        var tx = targetX - sx * scale;
        var ty = targetY - sy * scale;

        var scaledW = WORLD_W * scale;
        var scaledH = WORLD_H * scale;
        tx = Math.min(0, Math.max(tx, -(scaledW - vw)));
        ty = Math.min(0, Math.max(ty, -(scaledH - vh)));

        return { tx: tx, ty: ty, scale: scale, cx: sx, cy: sy };
    }

    /**
     * Compute the transform to center an arbitrary world point (wx, wy)
     * at a given scale.
     */
    function computePointTransform(wx, wy, scale) {
        if (!viewport) return null;

        var vw = viewport.offsetWidth;
        var vh = viewport.offsetHeight;
        var padTop = 80;
        var padBottom = 40;
        var availH = vh - padTop - padBottom;

        var targetX = vw / 2;
        var targetY = padTop + availH / 2;

        var tx = targetX - wx * scale;
        var ty = targetY - wy * scale;

        var scaledW = WORLD_W * scale;
        var scaledH = WORLD_H * scale;
        tx = Math.min(0, Math.max(tx, -(scaledW - vw)));
        ty = Math.min(0, Math.max(ty, -(scaledH - vh)));

        return { tx: tx, ty: ty };
    }

    /** Cubic ease-in-out */
    function easeInOutCubic(t) {
        return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }

    /**
     * Round sharp corners in a polyline by replacing each interior vertex
     * with a short quadratic-bezier-style arc.  `radius` controls how far
     * back from the corner the rounding starts (in px).
     */
    function roundCorners(pts, radius) {
        if (pts.length < 3) return pts;
        radius = radius || 120;
        var SUBDIVS = 8;           // points per rounded corner
        var out = [pts[0]];

        for (var i = 1; i < pts.length - 1; i++) {
            var prev = pts[i - 1];
            var cur  = pts[i];
            var next = pts[i + 1];

            // Vectors into and out of the corner
            var dxIn  = cur.x - prev.x, dyIn  = cur.y - prev.y;
            var dxOut = next.x - cur.x,  dyOut = next.y - cur.y;
            var lenIn  = Math.sqrt(dxIn * dxIn + dyIn * dyIn);
            var lenOut = Math.sqrt(dxOut * dxOut + dyOut * dyOut);

            if (lenIn < 1 || lenOut < 1) { out.push(cur); continue; }

            // Don't round if the direction barely changes
            var dot = (dxIn * dxOut + dyIn * dyOut) / (lenIn * lenOut);
            if (dot > 0.98) { out.push(cur); continue; }

            // Clamp radius so we don't overshoot either segment
            var r = Math.min(radius, lenIn * 0.4, lenOut * 0.4);

            var pA = { x: cur.x - (dxIn / lenIn) * r, y: cur.y - (dyIn / lenIn) * r };
            var pB = { x: cur.x + (dxOut / lenOut) * r, y: cur.y + (dyOut / lenOut) * r };

            // Quadratic bezier: P = (1-t)^2 * pA + 2(1-t)t * cur + t^2 * pB
            for (var s = 0; s <= SUBDIVS; s++) {
                var t = s / SUBDIVS;
                var u = 1 - t;
                out.push({
                    x: u * u * pA.x + 2 * u * t * cur.x + t * t * pB.x,
                    y: u * u * pA.y + 2 * u * t * cur.y + t * t * pB.y
                });
            }
        }

        out.push(pts[pts.length - 1]);
        return out;
    }

    /**
     * Compute cumulative arc-length distances along a polyline.
     * Returns array of same length as pts, starting at 0.
     */
    function cumulativeDistances(pts) {
        var dists = [0];
        for (var i = 1; i < pts.length; i++) {
            var dx = pts[i].x - pts[i - 1].x;
            var dy = pts[i].y - pts[i - 1].y;
            dists.push(dists[i - 1] + Math.sqrt(dx * dx + dy * dy));
        }
        return dists;
    }

    /**
     * Given cumulative distances and a target distance, interpolate
     * the position along the polyline.
     */
    function interpolateAlongPath(pts, dists, targetDist) {
        if (targetDist <= 0) return { x: pts[0].x, y: pts[0].y };
        var totalDist = dists[dists.length - 1];
        if (targetDist >= totalDist) return { x: pts[pts.length - 1].x, y: pts[pts.length - 1].y };

        // Binary search for the segment
        var lo = 0, hi = dists.length - 1;
        while (lo < hi - 1) {
            var mid = (lo + hi) >> 1;
            if (dists[mid] <= targetDist) lo = mid;
            else hi = mid;
        }

        var segLen = dists[hi] - dists[lo];
        var frac = segLen > 0 ? (targetDist - dists[lo]) / segLen : 0;
        return {
            x: pts[lo].x + (pts[hi].x - pts[lo].x) * frac,
            y: pts[lo].y + (pts[hi].y - pts[lo].y) * frac
        };
    }

    /** Cancel any running path animation. */
    function cancelAnimation() {
        if (animFrameId) {
            cancelAnimationFrame(animFrameId);
            animFrameId = null;
        }
    }

    /** Apply transform and update hub button visibility. */
    function applyTransform(tx, ty, scale) {
        world.style.transform = 'translate(' + tx + 'px, ' + ty + 'px) scale(' + scale + ')';
    }

    function updateHubButton(stationId) {
        if (hubBtn) {
            if (stationId === 'hero') {
                hubBtn.classList.remove('visible');
            } else {
                hubBtn.classList.add('visible');
            }
        }
    }

    /**
     * Pan (and scale) the world so the given station fits and is
     * centered in the viewport.  If a metro route exists, animate
     * along it.
     */
    function panTo(stationId) {
        var station = document.getElementById(stationId);
        if (!station) return;

        if (isMobile()) {
            cancelAnimation();
            station.scrollIntoView({ behavior: 'smooth', block: 'start' });
            currentStation = stationId;
            return;
        }

        if (!world || !viewport) return;

        var endTransform = computeStationTransform(stationId);
        if (!endTransform) return;

        var prevStation = currentStation;
        currentStation = stationId;
        updateHubButton(stationId);

        // Try to get a metro route for path-following animation
        var route = null;
        if (prevStation !== stationId && window.getMetroRoute) {
            route = window.getMetroRoute(prevStation, stationId);
        }

        cancelAnimation();

        if (!route || route.length < 2) {
            // No route — instant jump
            world.style.transition = '';
            applyTransform(endTransform.tx, endTransform.ty, endTransform.scale);
            return;
        }

        // Compute animation parameters
        var startTransform = computeStationTransform(prevStation);
        if (!startTransform) {
            applyTransform(endTransform.tx, endTransform.ty, endTransform.scale);
            return;
        }

        // Smooth out sharp direction changes
        route = roundCorners(route, 250);

        var dists = cumulativeDistances(route);
        var totalDist = dists[dists.length - 1];

        // Duration: 1.2ms per px of path distance, clamped to [1000, 3500]ms
        var pathDuration = Math.max(1000, Math.min(totalDist * 1.2, 3500));
        // Extra time at the end for the zoom-out reveal
        var zoomOutDuration = 600;
        var totalDuration = pathDuration + zoomOutDuration;

        var startScale = startTransform.scale;
        var endScale = endTransform.scale;
        // Zoom in while traveling: closer to 1:1 world scale
        var travelScale = Math.min(1.15, Math.max(startScale, endScale) * 1.6);

        // Fraction of total time spent following the path
        var pathFrac = pathDuration / totalDuration;

        // Disable CSS transition during RAF animation
        world.style.transition = 'none';

        var startTime = null;

        function tick(timestamp) {
            if (!startTime) startTime = timestamp;
            var elapsed = timestamp - startTime;
            var rawT = Math.min(elapsed / totalDuration, 1);

            var pos, scale;

            if (rawT <= pathFrac) {
                // Phase 1: follow the path, zooming in to travelScale
                var pt = easeInOutCubic(rawT / pathFrac);
                pos = interpolateAlongPath(route, dists, pt * totalDist);
                scale = startScale + (travelScale - startScale) * pt;
            } else {
                // Phase 2: hold at destination, zoom out to fit station
                var zt = easeInOutCubic((rawT - pathFrac) / (1 - pathFrac));
                pos = route[route.length - 1];
                scale = travelScale + (endScale - travelScale) * zt;
            }

            // Compute transform to center this world point
            var transform = computePointTransform(pos.x, pos.y, scale);
            if (transform) {
                applyTransform(transform.tx, transform.ty, scale);
            }

            if (rawT < 1) {
                animFrameId = requestAnimationFrame(tick);
            } else {
                // Snap to exact final position
                animFrameId = null;
                applyTransform(endTransform.tx, endTransform.ty, endTransform.scale);
                world.style.transition = '';
            }
        }

        animFrameId = requestAnimationFrame(tick);
    }

    // Expose globally
    window.panTo = panTo;
    window.getCurrentStation = function () { return currentStation; };

    function init() {
        world = document.getElementById('metro-world');
        viewport = document.getElementById('metro-viewport');
        hubBtn = document.getElementById('hub-btn');

        if (!world || !viewport) return;

        // Start centered on the hero hub
        panTo('hero');

        // Escape key returns to hub (only when modal is not open)
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                var overlay = document.getElementById('detail-overlay');
                if (overlay && !overlay.classList.contains('invisible')) {
                    return; // Let modal handler deal with it
                }
                panTo('hero');
            }
        });

        // Re-center on resize
        window.addEventListener('resize', function () {
            cancelAnimation();
            panTo(currentStation);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
