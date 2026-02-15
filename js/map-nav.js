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
     * Pan the world so the given station is centered in the viewport.
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

        // Station center in world coordinates
        var sx = station.offsetLeft + station.offsetWidth / 2;
        var sy = station.offsetTop + station.offsetHeight / 2;

        // Viewport dimensions
        var vw = viewport.offsetWidth;
        var vh = viewport.offsetHeight;

        // Target translation: center station in viewport
        var tx = -(sx - vw / 2);
        var ty = -(sy - vh / 2);

        // Clamp so we don't show space beyond the world
        tx = Math.min(0, Math.max(tx, -(WORLD_W - vw)));
        ty = Math.min(0, Math.max(ty, -(WORLD_H - vh)));

        world.style.transform = 'translate(' + tx + 'px, ' + ty + 'px)';
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
