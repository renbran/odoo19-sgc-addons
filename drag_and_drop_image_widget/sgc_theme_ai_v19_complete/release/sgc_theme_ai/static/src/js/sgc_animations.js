/** @odoo-module **/
/* ============================================================
   SGC TECH AI — Advanced Animation Controller
   Orchestrates scroll triggers, morph effects, data streams
   ============================================================ */

'use strict';

window.SGC = window.SGC || {};

SGC.Animations = {

  init() {
    this.initHeroOrbs();
    this.initDataStreamEffect();
    this.initScanLine();
    this.initCardTiltEffect();
    this.initGlowTracking();
    // [init];
  },

  // ─── HERO ORBS ────────────────────────────────────────────

  initHeroOrbs() {
    const hero = document.querySelector('.sgc-hero');
    if (!hero) return;

    // Create dynamic orbs
    const orbData = [
      { size: 500, x: '10%',  y: '20%', color: 'rgba(0,255,240,0.08)',   duration: 12 },
      { size: 400, x: '70%',  y: '60%', color: 'rgba(0,255,136,0.06)',   duration: 15 },
      { size: 600, x: '40%',  y: '40%', color: 'rgba(30,58,138,0.15)',   duration: 18 },
    ];

    orbData.forEach(orb => {
      const el = document.createElement('div');
      el.className = 'sgc-orb';
      el.style.cssText = `
        width:${orb.size}px;height:${orb.size}px;
        left:${orb.x};top:${orb.y};
        background:radial-gradient(circle, ${orb.color} 0%, transparent 70%);
        filter:blur(80px);
        animation:sgc-hero-orb ${orb.duration}s ease-in-out infinite;
      `;
      hero.insertBefore(el, hero.firstChild);
    });
  },

  // ─── DATA STREAM EFFECT ───────────────────────────────────

  initDataStreamEffect() {
    const containers = document.querySelectorAll('[data-sgc-stream]');
    containers.forEach(container => {
      this.createDataStream(container);
    });
  },

  createDataStream(container) {
    const chars = '01アイウエオカキクケコABCDEF0123456789░▒▓█';
    const columns = Math.floor(container.offsetWidth / 20);

    for (let i = 0; i < Math.min(columns, 20); i++) {
      const stream = document.createElement('div');
      stream.style.cssText = `
        position:absolute;
        left:${(i / columns) * 100}%;
        top:0;
        font-family:var(--sgc-font-mono);
        font-size:12px;
        color:rgba(0,255,240,0.15);
        line-height:1.4;
        pointer-events:none;
        user-select:none;
        writing-mode:vertical-rl;
        animation:sgc-data-stream ${3 + Math.random() * 5}s linear ${Math.random() * 3}s infinite;
        z-index:0;
      `;

      let content = '';
      for (let j = 0; j < 20; j++) {
        content += chars[Math.floor(Math.random() * chars.length)];
      }
      stream.textContent = content;
      container.appendChild(stream);
    }
  },

  // ─── SCAN LINE ────────────────────────────────────────────

  initScanLine() {
    const panels = document.querySelectorAll('.sgc-scan');
    panels.forEach(panel => {
      panel.style.overflow = 'hidden';
      panel.style.position = 'relative';
    });
  },

  // ─── CARD TILT EFFECT ─────────────────────────────────────

  initCardTiltEffect() {
    const cards = document.querySelectorAll('[data-tilt]');

    cards.forEach(card => {
      card.addEventListener('mousemove', (e) => {
        const rect     = card.getBoundingClientRect();
        const x        = e.clientX - rect.left;
        const y        = e.clientY - rect.top;
        const centerX  = rect.width  / 2;
        const centerY  = rect.height / 2;
        const rotateX  = ((y - centerY) / centerY) * -8;
        const rotateY  = ((x - centerX) / centerX) * 8;

        card.style.transform = `
          perspective(1000px)
          rotateX(${rotateX}deg)
          rotateY(${rotateY}deg)
          translateZ(20px)
          scale(1.02)
        `;
        card.style.transition = 'transform 0.1s ease';

        // Glare effect
        const glare = card.querySelector('.sgc-tilt-glare');
        if (glare) {
          const glareX = (x / rect.width)  * 100;
          const glareY = (y / rect.height) * 100;
          glare.style.background = `
            radial-gradient(circle at ${glareX}% ${glareY}%, 
              rgba(255,255,255,0.1) 0%, 
              transparent 60%)
          `;
        }
      });

      card.addEventListener('mouseleave', () => {
        card.style.transform = '';
        card.style.transition = 'transform 0.4s ease';
      });
    });
  },

  // ─── GLOW TRACKING ────────────────────────────────────────

  initGlowTracking() {
    const glowEls = document.querySelectorAll('[data-glow-track]');

    glowEls.forEach(el => {
      el.addEventListener('mousemove', (e) => {
        const rect = el.getBoundingClientRect();
        const x    = e.clientX - rect.left;
        const y    = e.clientY - rect.top;

        el.style.background = `
          radial-gradient(
            400px circle at ${x}px ${y}px,
            rgba(0, 255, 240, 0.06) 0%,
            transparent 60%
          )
        `;
      });

      el.addEventListener('mouseleave', () => {
        el.style.background = '';
      });
    });
  },
};

document.addEventListener('DOMContentLoaded', () => {
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    SGC.Animations.init();
  }
});

export default SGC.Animations;
