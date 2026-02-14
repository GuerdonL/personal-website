        const canvas = document.getElementById('planes-canvas');
        const ctx = canvas.getContext('2d');

        let width, height;

        // Resize Canvas to full document height
        function resize() {
            width = window.innerWidth;
            // Use the max height of the document to cover the whole scrollable area
            const body = document.body;
            const html = document.documentElement;

            height = Math.max(
                body.scrollHeight, body.offsetHeight,
                html.clientHeight, html.scrollHeight, html.offsetHeight
            );

            canvas.width = width;
            canvas.height = height;
        }
        window.addEventListener('resize', resize);
        // Call resize immediately to set initial size
        // Use setTimeout to ensure DOM is fully calculated
        setTimeout(resize, 100);

        class Plane {
            constructor() {
                // Ensure dimensions are set before init
                if (!width || !height) resize();

                this.reset();
                // Randomize start y to fill the ENTIRE page height initially
                this.y = Math.random() * height;
            }

            reset() {
                this.x = Math.random() * width;

                // Fix: Spawn relative to current scroll position so they don't disappear
                // if the user is scrolled down.
                const scrollY = window.scrollY || window.pageYOffset;
                this.y = scrollY - 50 - (Math.random() * 50);

                // Scale: Random range [0.5, 0.9] - Keeping them small/background
                this.scale = 0.5 + Math.random() * 0.4;

                // No blur needed for background planes, keeping it sharp and clean
                this.blur = 0;

                // Initial velocity: Downward bias with random spread
                // Much Slower initial speed
                const baseSpeed = 1.5 + Math.random() * 1.5;
                const speed = baseSpeed * this.scale * 0.8;

                const angle = (Math.PI / 2) + (Math.random() - 0.5) * 1.5;

                this.vx = Math.cos(angle) * speed;
                this.vy = Math.sin(angle) * speed;

                this.history = [];
                this.historyLimit = 40;

                // Physics constants
                // Low drag to keep energy for loops
                const baseDrag = 0.0005 + Math.random() * 0.0005;
                // Higher lift to make them floaty
                const baseLift = 0.005 + Math.random() * 0.002;
                // Lower gravity for slow motion feel
                const baseGravity = 0.015;

                this.dragCoeff = baseDrag / this.scale;
                this.liftCoeff = baseLift / this.scale;
                this.gravity = baseGravity * this.scale;

                this.turbulence = Math.random() * 100;
                this.loopBoost = 0; // Timer for "updraft" lift boost

                // Independent wobble phase for visual flutter
                this.wobblePhase = Math.random() * Math.PI * 2;
            }

            update() {
                // 1. Calculate Speed
                const speedSq = this.vx * this.vx + this.vy * this.vy;
                const speed = Math.sqrt(speedSq);

                // Randomly trigger a "Loop" (Updraft)
                if (this.loopBoost > 0) {
                    this.loopBoost--;
                } else if (Math.random() < 0.001) { // Reduced chance slightly
                    this.loopBoost = 60; // Boost lift for 60 frames
                }

                if (speed < 0.1) {
                    this.vy += this.gravity;
                } else {
                    // 2. Forces
                    const dragMag = this.dragCoeff * speedSq;
                    const dragX = -dragMag * (this.vx / speed);
                    const dragY = -dragMag * (this.vy / speed);

                    let liftDir = 1;
                    if (this.vx < 0) liftDir = -1;

                    let lx = (this.vy / speed);
                    let ly = (-this.vx / speed);

                    if (this.vx < 0) {
                        lx = -lx;
                        ly = -ly;
                    }

                    // Apply Lift
                    // If catching updraft (loopBoost), boost lift to force a loop
                    // Reduced multiplier slightly for stability
                    let effectiveLift = this.liftCoeff;
                    if (this.loopBoost > 0) effectiveLift *= 2.5;

                    const liftMag = effectiveLift * speedSq;
                    const liftX = liftMag * lx;
                    const liftY = liftMag * ly;

                    const gravY = this.gravity;

                    this.turbulence += 0.02;
                    // Add Vertical drafts (windY) as well as horizontal
                    const windX = Math.sin(this.turbulence) * (0.002 * this.scale);
                    const windY = Math.cos(this.turbulence * 0.5) * (0.002 * this.scale) - 0.001; // Slight updraft bias

                    this.vx += dragX + liftX + windX;
                    this.vy += dragY + liftY + gravY + windY;
                }

                this.x += this.vx;
                this.y += this.vy;

                // Bounds Check with History Reset
                let wrapped = false;
                if (this.x > width + 50) {
                    this.x = -50;
                    wrapped = true;
                }
                if (this.x < -50) {
                    this.x = width + 50;
                    wrapped = true;
                }

                // Reset if falls past the BOTTOM of the entire page OR far below viewport
                // We use scrollY to detect if it's way below the user to recycle it faster
                const scrollY = window.scrollY || window.pageYOffset;
                const viewportHeight = window.innerHeight;

                // If plane is > 100px below the current viewport bottom, recycle it
                if (this.y > scrollY + viewportHeight + 100) {
                    this.reset();
                    wrapped = true;
                }
                // Also safety check for document bottom
                else if (this.y > height + 100) {
                    this.reset();
                    wrapped = true;
                }

                if (wrapped) {
                    this.history = [];
                } else {
                    this.history.push({x: this.x, y: this.y});
                    if (this.history.length > this.historyLimit) {
                        this.history.shift();
                    }
                }
            }

            draw() {
                const angle = Math.atan2(this.vy, this.vx);

                // Add visual "Wobble" / Flutter
                // Decoupled from position (this.x) to prevent high-speed jitter
                // Slower frequency, random phase offset
                const flutter = Math.sin(Date.now() * 0.003 + this.wobblePhase) * 0.08;

                ctx.save();

                // Draw Trail
                if (this.history.length > 1) {
                    ctx.beginPath();
                    ctx.strokeStyle = 'rgba(68, 64, 60, 0.4)'; // Lower opacity trail
                    ctx.setLineDash([3 * this.scale, 5 * this.scale]);
                    ctx.lineWidth = 1 * this.scale;
                    ctx.moveTo(this.history[0].x, this.history[0].y);
                    for (let i = 1; i < this.history.length; i++) {
                        ctx.lineTo(this.history[i].x, this.history[i].y);
                    }
                    ctx.stroke();
                    ctx.setLineDash([]);
                }

                // Draw Plane
                ctx.translate(this.x, this.y);
                ctx.scale(this.scale, this.scale);
                ctx.rotate(angle + flutter); // Apply flutter here

                ctx.beginPath();
                ctx.fillStyle = '#e7e5e4';
                ctx.strokeStyle = '#292524';
                ctx.lineWidth = 1.5;

                // Plane Geometry
                ctx.moveTo(10, 0);   // Nose
                ctx.lineTo(-8, 7);   // Left Wing
                ctx.lineTo(-4, 0);   // Center Notch
                ctx.lineTo(-8, -7);  // Right Wing
                ctx.closePath();

                ctx.fill();
                ctx.stroke();

                ctx.beginPath();
                ctx.moveTo(10, 0);
                ctx.lineTo(-4, 0);
                ctx.stroke();

                ctx.restore();
            }
        }

        const planes = [];
        const planeCount = 18; // Increased slightly

        for (let i = 0; i < planeCount; i++) {
            planes.push(new Plane());
        }

        function animate() {
            ctx.clearRect(0, 0, width, height);

            planes.forEach(plane => {
                plane.update();
                plane.draw();
            });
            requestAnimationFrame(animate);
        }

        animate();
