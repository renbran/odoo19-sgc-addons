/** @odoo-module **/
/* ============================================================
   SGC TECH AI — Website Interactions
   ============================================================ */

'use strict';

window.SGC = window.SGC || {};

SGC.Website = {

  init() {
    this.initIndustryFilter();
    this.initGallery();
    this.initTypewriter();
    this.initLogoTicker();
    this.initMetricBars();
    this.initWhatsApp();
    this.initNavActive();
  },

  // ─── INDUSTRY FILTER (Case Studies) ──────────────────────

  initIndustryFilter() {
    const btns  = document.querySelectorAll('.sgc-industry-btn');
    const cards = document.querySelectorAll('[data-industry]');

    if (!btns.length) return;

    // CHECKPOINT C3: guard timeout callbacks from stale filter values
    // when users tap filters rapidly on mobile.
    let activeFilter = 'all';

    btns.forEach(btn => {
      btn.addEventListener('click', () => {
        const filter = btn.dataset.filter;
        activeFilter = filter;

        // Update active state
        btns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Filter cards
        cards.forEach(card => {
          const show = filter === 'all' || card.dataset.industry === filter;
          card.style.transition = 'opacity 0.3s, transform 0.3s';

          if (show) {
            card.style.opacity = '1';
            card.style.transform = 'scale(1)';
            card.style.display = '';
          } else {
            card.style.opacity = '0';
            card.style.transform = 'scale(0.95)';
            const scheduledFilter = filter;
            setTimeout(() => {
              if (activeFilter !== 'all' && activeFilter === scheduledFilter) {
                card.style.display = 'none';
              }
            }, 300);
          }
        });
      });
    });
  },

  // ─── IMAGE GALLERY ───────────────────────────────────────

  initGallery() {
    const thumbs = document.querySelectorAll('.sgc-gallery-thumb');
    const main   = document.querySelector('.sgc-gallery-main img');

    if (!thumbs.length || !main) return;

    thumbs.forEach(thumb => {
      thumb.addEventListener('click', () => {
        const src = thumb.querySelector('img')?.src;
        if (!src) return;

        thumbs.forEach(t => t.classList.remove('active'));
        thumb.classList.add('active');

        main.style.opacity = '0';
        main.style.transform = 'scale(0.98)';

        setTimeout(() => {
          main.src = src;
          main.style.opacity = '1';
          main.style.transform = 'scale(1)';
        }, 200);
      });
    });

    // Keyboard gallery navigation
    document.addEventListener('keydown', (e) => {
      const active = document.querySelector('.sgc-gallery-thumb.active');
      if (!active) return;

      const all = [...thumbs];
      const idx = all.indexOf(active);

      if (e.key === 'ArrowRight' && idx < all.length - 1) {
        all[idx + 1].click();
      } else if (e.key === 'ArrowLeft' && idx > 0) {
        all[idx - 1].click();
      }
    });
  },

  // ─── TYPEWRITER EFFECT ───────────────────────────────────

  initTypewriter() {
    const el = document.querySelector('[data-typewriter]');
    if (!el) return;

    const words = el.dataset.typewriter.split('|');
    let wordIdx = 0;
    let charIdx = 0;
    let deleting = false;

    el.style.borderRight = '3px solid var(--sgc-electric-cyan)';
    el.style.animation = 'sgc-blink 0.75s step-end infinite';

    const type = () => {
      const word = words[wordIdx];

      if (deleting) {
        charIdx--;
        el.textContent = word.substring(0, charIdx);
      } else {
        charIdx++;
        el.textContent = word.substring(0, charIdx);
      }

      let delay = deleting ? 60 : 100;

      if (!deleting && charIdx === word.length) {
        delay = 2000;
        deleting = true;
      } else if (deleting && charIdx === 0) {
        deleting = false;
        wordIdx = (wordIdx + 1) % words.length;
        delay = 300;
      }

      setTimeout(type, delay);
    };

    setTimeout(type, 500);
  },

  // ─── LOGO TICKER ─────────────────────────────────────────

  initLogoTicker() {
    const track = document.querySelector('.sgc-ticker-track');
    if (!track) return;

    // Duplicate for seamless loop
    const clone = track.cloneNode(true);
    track.parentElement.appendChild(clone);
  },

  // ─── METRIC PROGRESS BARS ────────────────────────────────

  initMetricBars() {
    const bars = document.querySelectorAll('.sgc-metric-fill');
    if (!bars.length) return;

    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          setTimeout(() => {
            entry.target.classList.add('animate');
          }, 200);
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.5 });

    bars.forEach(bar => io.observe(bar));
  },

  // ─── WHATSAPP BUTTON ─────────────────────────────────────

  initWhatsApp() {
    const btn = document.querySelector('.sgc-whatsapp-btn');
    if (!btn) return;

    const phone = '971521985231';
    const defaultMsg = encodeURIComponent(
      'Hello SGC TECH AI! I\'m interested in learning more about your Odoo ERP implementation services for my business in the UAE.'
    );

    btn.href = `https://wa.me/${phone}?text=${defaultMsg}`;
    btn.target = '_blank';
    btn.rel = 'noopener noreferrer';
  },

  // ─── ACTIVE NAV LINKS ────────────────────────────────────

  initNavActive() {
    const current = window.location.pathname;
    const links = document.querySelectorAll('.sgc-nav-links a');

    links.forEach(link => {
      const href = link.getAttribute('href');
      if (href && current.startsWith(href) && href !== '/') {
        link.classList.add('active');
      } else if (href === '/' && current === '/') {
        link.classList.add('active');
      }
    });
  },
};

// ─── SGC ANIMATIONS ENGINE ──────────────────────────────────
SGC.Animations = {

  init() {
    this.initHeroOrbs();
    this.initFloatingCards();
    this.initGlowOnHover();
    this.initParallax();
  },

  initHeroOrbs() {
    const hero = document.querySelector('.sgc-hero');
    if (!hero) return;

    const orbs = [
      { class: 'sgc-orb sgc-orb-cyan',  width: '600px', height: '600px', top: '-10%',  left: '-10%' },
      { class: 'sgc-orb sgc-orb-green', width: '400px', height: '400px', top: '20%',   right: '-5%', left: 'auto' },
      { class: 'sgc-orb sgc-orb-blue',  width: '800px', height: '800px', top: '10%',   left: '20%' },
    ];

    orbs.forEach(orb => {
      const el = document.createElement('div');
      el.className = orb.class;
      el.style.cssText = `
        width:${orb.width};height:${orb.height};
        top:${orb.top};left:${orb.left || 'auto'};
        ${orb.right ? `right:${orb.right};` : ''}
      `;
      hero.appendChild(el);
    });
  },

  initFloatingCards() {
    document.querySelectorAll('.sgc-float-card').forEach((card, i) => {
      card.style.animationDelay = `${i * 0.8}s`;
      card.classList.add('sgc-float');
    });
  },

  initGlowOnHover() {
    document.querySelectorAll('.sgc-card, .sgc-card-feature, .sgc-card-pricing').forEach(card => {
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 100;
        const y = ((e.clientY - rect.top) / rect.height) * 100;
        card.style.background = `radial-gradient(circle at ${x}% ${y}%, rgba(0,255,240,0.06), transparent 60%), var(--sgc-glass-bg)`;
      });

      card.addEventListener('mouseleave', () => {
        card.style.background = '';
      });
    });
  },

  initParallax() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const parallaxEls = document.querySelectorAll('[data-parallax]');
    if (!parallaxEls.length) return;

    window.addEventListener('scroll', () => {
      const scrollY = window.scrollY;
      parallaxEls.forEach(el => {
        const speed = parseFloat(el.dataset.parallax) || 0.3;
        const offset = scrollY * speed;
        el.style.transform = `translateY(${offset}px)`;
      });
    }, { passive: true });
  },
};

document.addEventListener('DOMContentLoaded', () => {
  SGC.Website.init();
  SGC.Animations.init();
});

export default SGC.Website;
