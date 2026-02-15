/**
 * Map Navigation — panning engine for the 2D metro world.
 *
 * panTo(stationId) smoothly translates #metro-world so the target
 * station is centered in the viewport.  On mobile (<768px) falls
 * back to scrollIntoView().
 */
(function () {
    var world = null;
    var viewport = null;
    var hubBtn = null;
    var currentStation = 'hero';

    var WORLD_W = 4000;
    var WORLD_H = 3000;

    function isMobile() {
        return window.innerWidth < 768;
    }

    /**
     * Pan (and scale) the world so the given station fits and is
     * centered in the viewport.
     */
    function panTo(stationId) {
        var station = document.getElementById(stationId);
        if (!station) return;

        if (isMobile()) {
            station.scrollIntoView({ behavior: 'smooth', block: 'start' });
            currentStation = stationId;
            return;
        }

        if (!world || !viewport) return;

        // Station dimensions and center in world coordinates
        var sw = station.offsetWidth;
        var sh = station.offsetHeight;
        var sx = station.offsetLeft + sw / 2;
        var sy = station.offsetTop + sh / 2;

        // Viewport dimensions
        var vw = viewport.offsetWidth;
        var vh = viewport.offsetHeight;

        // Available space (account for navbar and padding)
        var padTop = 80;
        var padBottom = 40;
        var padX = 60;
        var availW = vw - padX * 2;
        var availH = vh - padTop - padBottom;

        // Scale to fit station in available space (never scale up)
        var scale = Math.min(availW / sw, availH / sh, 1);

        // Target center point in viewport (offset for navbar)
        var targetX = vw / 2;
        var targetY = padTop + availH / 2;

        // With transform-origin 0 0 and translate(tx,ty) scale(s),
        // world point (wx,wy) maps to screen (tx + wx*s, ty + wy*s)
        var tx = targetX - sx * scale;
        var ty = targetY - sy * scale;

        // Clamp so we don't show space beyond the scaled world
        var scaledW = WORLD_W * scale;
        var scaledH = WORLD_H * scale;
        tx = Math.min(0, Math.max(tx, -(scaledW - vw)));
        ty = Math.min(0, Math.max(ty, -(scaledH - vh)));

        world.style.transform = 'translate(' + tx + 'px, ' + ty + 'px) scale(' + scale + ')';
        currentStation = stationId;

        // Show/hide hub button
        if (hubBtn) {
            if (stationId === 'hero') {
                hubBtn.classList.remove('visible');
            } else {
                hubBtn.classList.add('visible');
            }
        }
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
            panTo(currentStation);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
