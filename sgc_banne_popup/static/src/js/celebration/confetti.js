/** @odoo-module **/

const COLORS = ["#c9a24b", "#e5c782", "#0f1b3d", "#faf7f1", "#ffffff"];

export function burstConfetti(canvas, durationMs = 3500) {
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const resize = () => {
        canvas.width = window.innerWidth * dpr;
        canvas.height = window.innerHeight * dpr;
        canvas.style.width = window.innerWidth + "px";
        canvas.style.height = window.innerHeight + "px";
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const count = 160;
    const pieces = Array.from({ length: count }, () => ({
        x: Math.random() * window.innerWidth,
        y: -20 - Math.random() * window.innerHeight * 0.5,
        w: 6 + Math.random() * 6,
        h: 8 + Math.random() * 10,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        rot: Math.random() * 360,
        rotSpeed: -6 + Math.random() * 12,
        vy: 2 + Math.random() * 3,
        vx: -1.5 + Math.random() * 3,
        tilt: Math.random() * Math.PI,
    }));

    let start = null;
    let rafId = null;

    function frame(ts) {
        if (!start) start = ts;
        const elapsed = ts - start;
        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
        for (const p of pieces) {
            p.y += p.vy;
            p.x += p.vx + Math.sin(p.tilt) * 0.6;
            p.tilt += 0.05;
            p.rot += p.rotSpeed;
            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate((p.rot * Math.PI) / 180);
            ctx.fillStyle = p.color;
            ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
            ctx.restore();
        }
        if (elapsed < durationMs) {
            rafId = requestAnimationFrame(frame);
        } else {
            ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
            window.removeEventListener("resize", resize);
        }
    }
    rafId = requestAnimationFrame(frame);

    return () => {
        if (rafId) cancelAnimationFrame(rafId);
        window.removeEventListener("resize", resize);
    };
}
