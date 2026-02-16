        const canvas = document.getElementById('planes-canvas');
        const ctx = canvas.getContext('2d');

        let width, height;

        // Size canvas to the metro world dimensions
        function resize() {
            var world = document.getElementById('metro-world');
            if (world) {
                width = world.offsetWidth;
                height = world.offsetHeight;
            } else {
                width = 8500;
                height = 6000;
            }
            canvas.width = width;
            canvas.height = height;
        }
        resize();

        class Plane {
            constructor() {
                if (!width || !height) resize();
                this.reset();
                // Randomize start y across the viewport
                this.y = Math.random() * height;
            }

            reset() {
                this.x = Math.random() * width;
                // Spawn above the viewport
                this.y = -50 - (Math.random() * 50);

                // Scale: Random range [0.5, 0.9]
                this.scale = 0.5 + Math.random() * 0.4;

                this.blur = 0;

                // Initial velocity: Downward bias with random spread
                const baseSpeed = 1.5 + Math.random() * 1.5;
                const speed = baseSpeed * this.scale * 0.8;

                const angle = (Math.PI / 2) + (Math.random() - 0.5) * 1.5;

                this.vx = Math.cos(angle) * speed;
                this.vy = Math.sin(angle) * speed;

                this.history = [];
                this.historyLimit = 40;

                // Physics constants
                const baseDrag = 0.0005 + Math.random() * 0.0005;
                const baseLift = 0.005 + Math.random() * 0.002;
                const baseGravity = 0.015;

                this.dragCoeff = baseDrag / this.scale;
                this.liftCoeff = baseLift / this.scale;
                this.gravity = baseGravity * this.scale;

                this.turbulence = Math.random() * 100;
                this.loopBoost = 0;
                this.wobblePhase = Math.random() * Math.PI * 2;
            }

            update() {
                const speedSq = this.vx * this.vx + this.vy * this.vy;
                const speed = Math.sqrt(speedSq);

                if (this.loopBoost > 0) {
                    this.loopBoost--;
                } else if (Math.random() < 0.001) {
                    this.loopBoost = 60;
                }

                if (speed < 0.1) {
                    this.vy += this.gravity;
                } else {
                    const dragMag = this.dragCoeff * speedSq;
                    const dragX = -dragMag * (this.vx / speed);
                    const dragY = -dragMag * (this.vy / speed);

                    let lx = (this.vy / speed);
                    let ly = (-this.vx / speed);

                    if (this.vx < 0) {
                        lx = -lx;
                        ly = -ly;
                    }

                    let effectiveLift = this.liftCoeff;
                    if (this.loopBoost > 0) effectiveLift *= 2.5;

                    const liftMag = effectiveLift * speedSq;
                    const liftX = liftMag * lx;
                    const liftY = liftMag * ly;

                    const gravY = this.gravity;

                    this.turbulence += 0.02;
                    const windX = Math.sin(this.turbulence) * (0.002 * this.scale);
                    const windY = Math.cos(this.turbulence * 0.5) * (0.002 * this.scale) - 0.001;

                    this.vx += dragX + liftX + windX;
                    this.vy += dragY + liftY + gravY + windY;
                }

                this.x += this.vx;
                this.y += this.vy;

                // Bounds check (viewport only, no scroll)
                let wrapped = false;
                if (this.x > width + 50) {
                    this.x = -50;
                    wrapped = true;
                }
                if (this.x < -50) {
                    this.x = width + 50;
                    wrapped = true;
                }

                // Recycle if below viewport
                if (this.y > height + 100) {
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
                const flutter = Math.sin(Date.now() * 0.003 + this.wobblePhase) * 0.08;

                ctx.save();

                // Draw Trail
                if (this.history.length > 1) {
                    ctx.beginPath();
                    ctx.strokeStyle = 'rgba(68, 64, 60, 0.4)';
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
                ctx.rotate(angle + flutter);

                ctx.beginPath();
                ctx.fillStyle = '#e7e5e4';
                ctx.strokeStyle = '#292524';
                ctx.lineWidth = 1.5;

                ctx.moveTo(10, 0);
                ctx.lineTo(-8, 7);
                ctx.lineTo(-4, 0);
                ctx.lineTo(-8, -7);
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
        const planeCount = 60;

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
