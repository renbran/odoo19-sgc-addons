/** @odoo-module **/
/* ============================================================
   SGC TECH AI — Particle System
   Canvas-based floating particles for hero & CTA sections
   ============================================================ */

'use strict';

window.SGC = window.SGC || {};

SGC.Particles = {

  instances: [],

  init() {
    const canvases = document.querySelectorAll('[data-sgc-particles]');
    canvases.forEach(el => this.create(el));
  },

  create(container) {
    const canvas = document.createElement('canvas');
    canvas.style.cssText = `
      position:absolute;inset:0;width:100%;height:100%;
      pointer-events:none;z-index:0;opacity:0.6;
    `;
    container.style.position = 'relative';
    container.insertBefore(canvas, container.firstChild);

    const ctx   = canvas.getContext('2d');
    const config = this.parseConfig(container.dataset.sgcParticles);
    // Mobile optimization: reduce visual complexity to protect FPS and battery
    if (window.matchMedia('(max-width: 767px)').matches) {
      config.count = Math.max(20, Math.floor(config.count * 0.5));
      config.connections = false;
    }
    const state  = { particles: [], frame: null, width: 0, height: 0 };

    const resize = () => {
      const rect = container.getBoundingClientRect();
      canvas.width  = rect.width;
      canvas.height = rect.height;
      state.width   = canvas.width;
      state.height  = canvas.height;
    };

    resize();

    // Particle factory
    const createParticle = () => ({
      x: Math.random() * state.width,
      y: Math.random() * state.height,
      vx: (Math.random() - 0.5) * config.speed,
      vy: (Math.random() - 0.5) * config.speed - config.rise,
      r:  Math.random() * config.maxRadius + config.minRadius,
      opacity: Math.random() * 0.6 + 0.1,
      color: config.colors[Math.floor(Math.random() * config.colors.length)],
      pulse: Math.random() * Math.PI * 2,
      pulseSpeed: (Math.random() * 0.02 + 0.005),
    });

    // Init particles
    for (let i = 0; i < config.count; i++) {
      state.particles.push(createParticle());
    }

    // Animation loop
    const tick = () => {
      ctx.clearRect(0, 0, state.width, state.height);

      state.particles.forEach((p, i) => {
        // Update
        p.x += p.vx;
        p.y += p.vy;
        p.pulse += p.pulseSpeed;
        const pulsedOpacity = p.opacity * (0.7 + Math.sin(p.pulse) * 0.3);

        // Wrap around
        if (p.x < -10) p.x = state.width + 10;
        if (p.x > state.width + 10) p.x = -10;
        if (p.y < -10) p.y = state.height + 10;
        if (p.y > state.height + 10) p.y = -10;

        // Draw particle
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = p.color.replace(')', `, ${pulsedOpacity})`).replace('rgb', 'rgba');
        ctx.fill();

        // Draw connections
        if (config.connections) {
          for (let j = i + 1; j < state.particles.length; j++) {
            const p2   = state.particles[j];
            const dist = Math.hypot(p2.x - p.x, p2.y - p.y);

            if (dist < config.connectionDistance) {
              const alpha = (1 - dist / config.connectionDistance) * 0.15;
              ctx.beginPath();
              ctx.moveTo(p.x, p.y);
              ctx.lineTo(p2.x, p2.y);
              ctx.strokeStyle = `rgba(0, 255, 240, ${alpha})`;
              ctx.lineWidth = 0.5;
              ctx.stroke();
            }
          }
        }
      });

      state.frame = requestAnimationFrame(tick);
    };

    tick();
    window.addEventListener('resize', resize, { passive: true });
    this.instances.push(state);
  },

  parseConfig(str) {
    const defaults = {
      count: 60,
      speed: 0.3,
      rise: 0.05,
      minRadius: 1,
      maxRadius: 3,
      connections: true,
      connectionDistance: 120,
      colors: ['rgb(0, 255, 240)', 'rgb(0, 255, 136)', 'rgb(79, 195, 247)'],
    };

    try {
      return { ...defaults, ...JSON.parse(str || '{}') };
    } catch (e) {
      return defaults;
    }
  },

  destroy() {
    this.instances.forEach(state => {
      if (state.frame) cancelAnimationFrame(state.frame);
    });
    this.instances = [];
  },
};

// ─── HEXAGONAL GRID EFFECT ──────────────────────────────────
SGC.HexGrid = {
  init() {
    const containers = document.querySelectorAll('[data-sgc-hex]');
    containers.forEach(el => this.create(el));
  },

  create(container) {
    const canvas = document.createElement('canvas');
    canvas.style.cssText = `
      position:absolute;inset:0;width:100%;height:100%;
      pointer-events:none;z-index:0;opacity:0.12;
    `;
    container.style.position = 'relative';
    container.insertBefore(canvas, container.firstChild);

    const ctx = canvas.getContext('2d');
    const hexSize = 40;
    let activeHexes = [];

    const resize = () => {
      const rect = container.getBoundingClientRect();
      canvas.width  = rect.width;
      canvas.height = rect.height;
      draw();
    };

    const hexPath = (x, y, size) => {
      ctx.beginPath();
      for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 6;
        const px = x + size * Math.cos(angle);
        const py = y + size * Math.sin(angle);
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      }
      ctx.closePath();
    };

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const cols = Math.ceil(canvas.width / (hexSize * 1.75)) + 2;
      const rows = Math.ceil(canvas.height / (hexSize * 1.5)) + 2;

      for (let row = -1; row < rows; row++) {
        for (let col = -1; col < cols; col++) {
          const x = col * hexSize * 1.75 + (row % 2 === 0 ? 0 : hexSize * 0.875);
          const y = row * hexSize * 1.5;

          hexPath(x, y, hexSize - 3);

          const isActive = activeHexes.some(h => h.col === col && h.row === row);

          if (isActive) {
            const alpha = activeHexes.find(h => h.col === col && h.row === row).alpha;
            ctx.fillStyle = `rgba(0, 255, 240, ${alpha * 0.08})`;
            ctx.fill();
            ctx.strokeStyle = `rgba(0, 255, 240, ${alpha * 0.4})`;
          } else {
            ctx.strokeStyle = 'rgba(0, 255, 240, 0.1)';
          }

          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }
    };

    // Random hex activation
    const animateHex = () => {
      const cols = Math.ceil(canvas.width / (hexSize * 1.75));
      const rows = Math.ceil(canvas.height / (hexSize * 1.5));

      if (activeHexes.length < 8 && Math.random() > 0.7) {
        activeHexes.push({
          col: Math.floor(Math.random() * cols),
          row: Math.floor(Math.random() * rows),
          alpha: 0,
          dir: 1,
        });
      }

      activeHexes = activeHexes.filter(h => {
        h.alpha += h.dir * 0.04;
        if (h.alpha >= 1) h.dir = -1;
        return h.alpha > 0;
      });

      draw();
      requestAnimationFrame(animateHex);
    };

    resize();
    animateHex();
    window.addEventListener('resize', resize, { passive: true });
  },
};

document.addEventListener('DOMContentLoaded', () => {
  // CHECKPOINT C3: defer non-critical visuals until idle so conversion UI and
  // first meaningful paint stay fast on mobile/slow networks.
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const hasParticleTargets = document.querySelector('[data-sgc-particles], [data-sgc-hex]');
  if (!hasParticleTargets) return;

  const startEffects = () => {
    SGC.Particles.init();
    SGC.HexGrid.init();
  };

  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(startEffects, { timeout: 1200 });
  } else {
    setTimeout(startEffects, 250);
  }
});

export { SGC };
