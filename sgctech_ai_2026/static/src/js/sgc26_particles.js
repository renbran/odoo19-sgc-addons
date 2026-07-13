/** @odoo-module **/
/* SGC Tech AI 2026 — Hero particle canvas engine */

(function () {
    'use strict';

    const wrap = document.getElementById('wrapwrap');
    if (!wrap || !wrap.classList.contains('sgc-v26')) return;

    const SGC26 = window.SGC26 || {};
    if (!SGC26.motionOK) return;

    const canvas = document.getElementById('sgc26-particles');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const COUNT   = 120;
    const MAX_DIST = 130;

    let W, H, particles = [], mouse = { x: -9999, y: -9999 };

    /* ── Particle constructor ────────────────────────────── */
    function Particle() { this.reset(true); }
    Particle.prototype.reset = function (init) {
        this.x  = Math.random() * W;
        this.y  = init ? Math.random() * H : -10;
        this.z  = 0.2 + Math.random() * 0.8;          /* depth */
        const spd = (0.15 + Math.random() * 0.35) * this.z;
        const ang = Math.random() * Math.PI * 2;
        this.vx = Math.cos(ang) * spd;
        this.vy = Math.sin(ang) * spd * 0.5 + 0.08 * this.z;
        this.r  = 1.2 + this.z * 1.8;
        this.alpha = 0.25 + this.z * 0.55;
    };

    /* ── Colour by velocity magnitude ────────────────────── */
    function particleColour(p) {
        const spd = Math.hypot(p.vx, p.vy);
        const t   = Math.min(spd / 0.6, 1);
        /* cyan (0,212,255) → violet (123,47,190) */
        const r = Math.round(0   + t * 123);
        const g = Math.round(212 - t * 165);
        const b = Math.round(255 - t * 65);
        return `rgba(${r},${g},${b},${p.alpha})`;
    }

    function resize() {
        W = canvas.offsetWidth;
        H = canvas.offsetHeight;
        canvas.width  = W;
        canvas.height = H;
    }

    function init() {
        resize();
        particles = Array.from({ length: COUNT }, () => new Particle());
    }

    function draw() {
        ctx.clearRect(0, 0, W, H);

        /* Update & draw particles */
        for (let i = 0; i < COUNT; i++) {
            const p = particles[i];

            /* Mouse repel */
            const dx = p.x - mouse.x;
            const dy = p.y - mouse.y;
            const dist = Math.hypot(dx, dy);
            if (dist < 100) {
                const force = (100 - dist) / 100 * 0.6;
                p.vx += (dx / dist) * force;
                p.vy += (dy / dist) * force;
            }

            /* Damping */
            p.vx *= 0.97;
            p.vy *= 0.97;

            p.x += p.vx;
            p.y += p.vy;

            /* Wrap edges */
            if (p.x < -10) p.x = W + 10;
            if (p.x > W + 10) p.x = -10;
            if (p.y < -10) p.y = H + 10;
            if (p.y > H + 10) p.y = -10;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = particleColour(p);
            ctx.fill();
        }

        /* Draw connection lines */
        for (let i = 0; i < COUNT; i++) {
            for (let j = i + 1; j < COUNT; j++) {
                const a = particles[i];
                const b = particles[j];
                const dx = a.x - b.x;
                const dy = a.y - b.y;
                const d  = Math.hypot(dx, dy);
                if (d > MAX_DIST) continue;
                const alpha = (1 - d / MAX_DIST) * 0.18 * Math.min(a.z, b.z);
                /* Gradient line cyan → violet */
                const grad = ctx.createLinearGradient(a.x, a.y, b.x, b.y);
                grad.addColorStop(0, `rgba(0,212,255,${alpha})`);
                grad.addColorStop(1, `rgba(123,47,190,${alpha})`);
                ctx.beginPath();
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);
                ctx.strokeStyle = grad;
                ctx.lineWidth   = Math.min(a.z, b.z) * 0.8;
                ctx.stroke();
            }
        }

        requestAnimationFrame(draw);
    }

    /* ── Events ──────────────────────────────────────────── */
    canvas.addEventListener('mousemove', e => {
        const rect = canvas.getBoundingClientRect();
        mouse.x = e.clientX - rect.left;
        mouse.y = e.clientY - rect.top;
    });
    canvas.addEventListener('mouseleave', () => { mouse.x = -9999; mouse.y = -9999; });

    window.addEventListener('resize', SGC26.debounce ? SGC26.debounce(init, 200) : init);

    init();
    requestAnimationFrame(draw);

})();
