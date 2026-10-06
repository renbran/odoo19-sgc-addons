/* ============================================================
   SGC TECH AI — Animated Circuit Backdrop
   Runs an infinite looping canvas animation of electric pulses
   travelling along circuit board traces.  Replaces the static
   SVG body::before pattern with a live GPU-composited layer.
   ============================================================ */
(function () {
  'use strict';

  /* ── Bail on prefers-reduced-motion ─────────────────────── */
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  /* ── Colour palette ──────────────────────────────────────── */
  const C = {
    bg:     '#030f1c',
    trace:  'rgba(13,36,60,0.95)',
    traceB: 'rgba(0,180,175,0.18)',  // faint glow on board traces
    p1:     '#00FFF0',               // electric cyan pulse
    p2:     '#00FF88',               // neon green pulse
    node:   '#00FFF0',
  };

  /* ── Circuit path definitions (relative 0-1 coords) ─────── */
  /* Designed to match the photo-reference circuit board image  */
  const PATH_DEFS = [
    // Top-left backbone → centre
    [[0,0.21],[0.11,0.21],[0.155,0.265],[0.285,0.265],[0.335,0.315],[0.445,0.315],[0.445,0.39],[0.53,0.39]],
    // Top-left vertical spur
    [[0.19,0.10],[0.19,0.21],[0.275,0.21],[0.275,0.33],[0.215,0.33],[0.215,0.455]],
    // Centre vertical left → highlight path (bright cyan)
    [[0.285,0.265],[0.285,0.155],[0.44,0.155],[0.44,0.09],[0.61,0.09],[0.61,0.11],[0.61,0.32]],
    // Main highlighted trace (matches glowing centre path in image)
    [[0.325,0.366],[0.325,0.484],[0.37,0.484],[0.37,0.42],[0.42,0.42],[0.42,0.546],[0.50,0.546],[0.61,0.546],[0.61,0.57]],
    // Right-side vertical
    [[0.61,0.11],[0.61,0.32],[0.55,0.38],[0.55,0.51],[0.61,0.57],[0.785,0.57]],
    // Top-right horizontal
    [[0.84,0.26],[1.0,0.26]],
    // Mid-right connector
    [[0.61,0.51],[0.725,0.51],[0.725,0.562],[0.785,0.562]],
    // Bottom horizontal backbone
    [[0,0.69],[0.16,0.69],[0.16,0.60],[0.29,0.60],[0.29,0.73],[0.48,0.73],[0.48,0.67],[0.66,0.67]],
    // Bottom-right loop
    [[0.785,0.57],[0.90,0.57],[0.90,0.78],[0.74,0.78],[0.74,0.95]],
    // Bottom-centre dropper
    [[0.46,0.824],[0.46,0.918],[0.51,0.968],[0.60,0.968]],
    // Far-right tail
    [[0.785,0.57],[1.0,0.57]],
    // Second bottom horizontal
    [[0,0.42],[0.10,0.42],[0.10,0.50],[0.215,0.50],[0.215,0.455]],
  ];

  /* ── Junction node positions (relative) ─────────────────── */
  const NODE_DEFS = [
    [0.61, 0.11], [0.61, 0.39], [0.785, 0.57], [0.61, 0.57],
    [0.325, 0.366], [0.46, 0.824], [0.285, 0.265], [0.44, 0.09],
  ];

  /* ── Component block definitions (IC chips / resistors) ──── */
  /* Each: [rx, ry, w, h, type] — type 'chip'|'res'|'cap' */
  const COMP_DEFS = [
    [0.193, 0.118, 0.034, 0.092, 'chip'],
    [0.44,  0.060, 0.011, 0.152, 'cap'],
    [0.463, 0.060, 0.011, 0.152, 'cap'],
    [0.617, 0.548, 0.011, 0.126, 'cap'],
    [0.645, 0.548, 0.011, 0.126, 'cap'],
    [0.068, 0.326, 0.053, 0.038, 'res'],
    [0.759, 0.222, 0.085, 0.036, 'res'],
    [0.768, 0.744, 0.078, 0.044, 'res'],
    [0.334, 0.706, 0.043, 0.058, 'res'],
  ];

  /* ================================================================
     CircuitBackdrop class
  ================================================================ */
  class CircuitBackdrop {
    constructor() {
      this.canvas    = null;
      this.ctx       = null;
      this.offscreen = null;   // pre-rendered static board
      this.offCtx    = null;
      this.paths     = [];     // computed absolute paths
      this.pulses    = [];
      this.rafId     = null;
      this.tick      = 0;
      this.W         = 0;
      this.H         = 0;
      this.paused    = false;
    }

    /* ── Lifecycle ─────────────────────────────────────────── */
    init() {
      this.canvas = document.createElement('canvas');
      this.canvas.id = 'sgc-circuit-canvas';
      Object.assign(this.canvas.style, {
        position:      'fixed',
        top:           '0',
        left:          '0',
        width:         '100%',
        height:        '100%',
        zIndex:        '-2',
        pointerEvents: 'none',
        willChange:    'contents',
        display:       'block',
      });
      this.canvas.setAttribute('aria-hidden', 'true');
      document.body.insertBefore(this.canvas, document.body.firstChild);
      this.ctx = this.canvas.getContext('2d');

      this._resize();

      /* ResizeObserver for smooth canvas resize */
      if (typeof ResizeObserver !== 'undefined') {
        new ResizeObserver(() => this._resize()).observe(document.documentElement);
      } else {
        window.addEventListener('resize', () => this._resize());
      }

      /* Pause when tab is hidden (battery / CPU saving) */
      document.addEventListener('visibilitychange', () => {
        this.paused = document.hidden;
        if (!this.paused && !this.rafId) this._loop();
      });

      this.rafId = requestAnimationFrame(() => this._loop());
    }

    /* ── Layout ────────────────────────────────────────────── */
    _resize() {
      this.W = window.innerWidth;
      this.H = window.innerHeight;
      this.canvas.width  = this.W;
      this.canvas.height = this.H;
      this._buildPaths();
      this._initPulses();
      this._renderOffscreen();
    }

    _buildPaths() {
      const W = this.W, H = this.H;
      this.paths = PATH_DEFS.map(pts => {
        const abs = pts.map(([x, y]) => [x * W, y * H]);
        let total = 0;
        const segs = [];
        for (let i = 1; i < abs.length; i++) {
          const [ax, ay] = abs[i - 1];
          const [bx, by] = abs[i];
          const dx = bx - ax, dy = by - ay;
          const len = Math.hypot(dx, dy);
          segs.push({ s: total, e: total + len, len, dx, dy, ax, ay });
          total += len;
        }
        return { pts: abs, segs, total };
      });
    }

    /* ── Offscreen: pre-render static circuit board ──────────── */
    _renderOffscreen() {
      const W = this.W, H = this.H;
      this.offscreen        = document.createElement('canvas');
      this.offscreen.width  = W;
      this.offscreen.height = H;
      const c = this.offscreen.getContext('2d');

      /* Dark background gradient */
      const bg = c.createLinearGradient(0, 0, 0, H);
      bg.addColorStop(0, '#030f1c');
      bg.addColorStop(1, '#071826');
      c.fillStyle = bg;
      c.fillRect(0, 0, W, H);

      /* Subtle radial glows (match board light sources) */
      const glow = (cx, cy, r, col) => {
        const g = c.createRadialGradient(cx * W, cy * H, 0, cx * W, cy * H, r * W);
        g.addColorStop(0, col);
        g.addColorStop(1, 'transparent');
        c.fillStyle = g;
        c.fillRect(0, 0, W, H);
      };
      glow(0.18, 0.14, 0.20, 'rgba(148,191,214,0.07)');
      glow(0.55, 0.42, 0.16, 'rgba(0,255,240,0.05)');
      glow(0.88, 0.80, 0.18, 'rgba(0,255,240,0.04)');

      /* Faint board-trace halos */
      c.save();
      c.lineCap  = 'round';
      c.lineJoin = 'round';
      this.paths.forEach((path, i) => {
        c.beginPath();
        path.pts.forEach(([x, y], j) => j ? c.lineTo(x, y) : c.moveTo(x, y));
        c.strokeStyle  = C.traceB;
        c.lineWidth    = (i === 3) ? 5 : 2.5;
        c.filter       = 'blur(2px)';
        c.stroke();
        c.filter       = 'none';
      });
      c.restore();

      /* Main dark circuit traces */
      c.save();
      c.lineCap  = 'round';
      c.lineJoin = 'round';
      this.paths.forEach((path, i) => {
        c.beginPath();
        path.pts.forEach(([x, y], j) => j ? c.lineTo(x, y) : c.moveTo(x, y));
        c.strokeStyle = C.trace;
        c.lineWidth   = (i === 3) ? 2.8 : (i === 2 ? 2 : 1.4);
        c.stroke();
      });
      c.restore();

      /* Component blocks */
      c.save();
      COMP_DEFS.forEach(([rx, ry, rw, rh, type]) => {
        const x = rx * W, y = ry * H, w = rw * W, h = rh * H;
        if (type === 'chip') {
          c.fillStyle   = 'rgba(207,232,241,0.45)';
          c.strokeStyle = 'rgba(126,168,187,0.55)';
          c.lineWidth   = 1;
          c.beginPath();
          c.roundRect ? c.roundRect(x, y, w, h, 3) : c.rect(x, y, w, h);
          c.fill(); c.stroke();
        } else if (type === 'cap') {
          /* Electrolytic capacitor — tall thin stripe */
          c.fillStyle = 'rgba(207,232,241,0.42)';
          c.fillRect(x, y, w, h);
        } else {
          /* Resistor — wide short block */
          c.fillStyle   = 'rgba(130,160,180,0.35)';
          c.strokeStyle = 'rgba(126,168,187,0.4)';
          c.lineWidth   = 0.8;
          c.beginPath();
          c.roundRect ? c.roundRect(x, y, w, h, 2) : c.rect(x, y, w, h);
          c.fill(); c.stroke();
        }
      });
      c.restore();
    }

    /* ── Pulses ──────────────────────────────────────────────── */
    _initPulses() {
      /* One pulse per path; stagger start positions so they're spread */
      this.pulses = this.paths.map((path, i) => {
        const isHighlight = (i === 3 || i === 2);
        return {
          pathIdx: i,
          pos:     -(Math.random() * path.total),   /* staggered */
          speed:   isHighlight ? 2.6 + Math.random() * 1.2
                               : 1.1 + Math.random() * 2.0,
          trail:   isHighlight ? 120 + Math.random() * 60
                               : 55  + Math.random() * 60,
          color:   (i % 4 === 0) ? C.p2 : C.p1,
          width:   isHighlight ? 3 : 1.8,
        };
      });
    }

    /* ── Path interpolation ──────────────────────────────────── */
    _ptAt(path, dist) {
      if (dist <= 0) return path.pts[0];
      if (dist >= path.total) return path.pts[path.pts.length - 1];
      for (const s of path.segs) {
        if (dist <= s.e) {
          const t = (dist - s.s) / s.len;
          return [s.ax + s.dx * t, s.ay + s.dy * t];
        }
      }
      return path.pts[path.pts.length - 1];
    }

    /* ── Draw animated elements on live canvas ───────────────── */
    _drawPulse(pulse) {
      const ctx  = this.ctx;
      const path = this.paths[pulse.pathIdx];
      if (!path || path.total === 0) return;

      const STEPS = 32;
      ctx.save();
      ctx.lineCap = 'round';

      /* Trail: series of shrinking glowing dots */
      for (let i = STEPS; i >= 0; i--) {
        const d   = pulse.pos - pulse.trail * (i / STEPS);
        if (d < 0) continue;
        const pt  = this._ptAt(path, d);
        const t   = 1 - i / STEPS;      /* 0 (tail) → 1 (head) */
        const a   = t * 0.88;
        const r   = t * pulse.width * 2.2 + 0.4;
        const hex = Math.round(a * 255).toString(16).padStart(2, '0');
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], r, 0, Math.PI * 2);
        ctx.fillStyle = pulse.color + hex;
        ctx.fill();
      }

      /* Leading glow dot */
      if (pulse.pos >= 0 && pulse.pos <= path.total) {
        const lp = this._ptAt(path, pulse.pos);
        ctx.shadowBlur  = 18;
        ctx.shadowColor = pulse.color;
        ctx.beginPath();
        ctx.arc(lp[0], lp[1], pulse.width + 1, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.shadowBlur  = 0;
      }
      ctx.restore();
    }

    _drawNodes() {
      const { ctx, W, H, tick } = this;
      const glow = 0.5 + 0.5 * Math.sin(tick * 0.025);

      ctx.save();
      NODE_DEFS.forEach(([rx, ry]) => {
        const x = rx * W, y = ry * H;
        /* Outer glow ring */
        const g = ctx.createRadialGradient(x, y, 0, x, y, 18);
        g.addColorStop(0,   `rgba(0,255,240,${0.55 + glow * 0.35})`);
        g.addColorStop(0.4, `rgba(0,255,240,${0.12 + glow * 0.08})`);
        g.addColorStop(1,   'transparent');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(x, y, 18, 0, Math.PI * 2);
        ctx.fill();
        /* Solid centre dot */
        ctx.fillStyle = C.node;
        ctx.shadowBlur  = 8;
        ctx.shadowColor = C.node;
        ctx.beginPath();
        ctx.arc(x, y, 2.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      });
      ctx.restore();
    }

    /* ── Main animation loop ─────────────────────────────────── */
    _loop() {
      if (this.paused) { this.rafId = null; return; }

      this.tick++;
      const { ctx, W, H } = this;

      /* Composite static board from offscreen (cheap blit) */
      ctx.drawImage(this.offscreen, 0, 0, W, H);

      /* Animated: glowing junction nodes */
      this._drawNodes();

      /* Animated: electric pulse particles */
      this.pulses.forEach(pulse => {
        pulse.pos += pulse.speed;
        const path = this.paths[pulse.pathIdx];
        if (path && pulse.pos > path.total + pulse.trail) {
          /* Loop: reset with slight random re-roll */
          pulse.pos   = -(20 + Math.random() * 60);
          pulse.speed = (pulse.pathIdx === 3 || pulse.pathIdx === 2)
            ? 2.6 + Math.random() * 1.2
            : 1.1 + Math.random() * 2.0;
        }
        this._drawPulse(pulse);
      });

      this.rafId = requestAnimationFrame(() => this._loop());
    }
  }

  /* ── Boot ──────────────────────────────────────────────────── */
  function boot() {
    /* Only run on website frontend, not backend */
    if (document.body.classList.contains('o_web_client')) return;
    const bd = new CircuitBackdrop();
    bd.init();
    window._sgcCircuitBackdrop = bd;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
}());
