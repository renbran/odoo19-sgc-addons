/** @odoo-module **/
/* ============================================================
   SGC TECH AI — Core JavaScript Engine
   Foundation utilities, scroll behaviors, theme management
   ============================================================ */

'use strict';

// ─── SGC NAMESPACE ──────────────────────────────────────────
window.SGC = window.SGC || {};

// ─── CORE ENGINE ────────────────────────────────────────────
SGC.Core = {

  // Cache
  _scrollY: 0,
  _observers: new Map(),

  /**
   * Initialize all core features
   */
  init() {
    this.initScrollBehaviors();
    this.initRevealAnimations();
    this.initCounters();
    this.initStickyHeader();
    this.initProgressBar();
    this.initSmoothScroll();
    this.initMobileMenu();
    this.initAccordions();
    this.initTabs();
    this.initRangeSliders();
  },

  // ─── SCROLL ──────────────────────────────────────────────

  initStickyHeader() {
    const header = document.getElementById('sgc-header');
    if (!header) return;

    let lastScroll = 0;
    let ticking = false;

    window.addEventListener('scroll', () => {
      this._scrollY = window.scrollY;
      if (!ticking) {
        requestAnimationFrame(() => {
          // Scrolled state
          if (this._scrollY > 40) {
            header.classList.add('scrolled');
          } else {
            header.classList.remove('scrolled');
          }

          // Hide on scroll down (smart hide)
          if (this._scrollY > lastScroll && this._scrollY > 200) {
            header.style.transform = 'translateY(-100%)';
          } else {
            header.style.transform = 'translateY(0)';
          }

          lastScroll = this._scrollY;
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });
  },

  initProgressBar() {
    const bar = document.querySelector('.sgc-progress-bar');
    if (!bar) return;

    window.addEventListener('scroll', () => {
      const winHeight = document.documentElement.scrollHeight - window.innerHeight;
      const progress = (window.scrollY / winHeight) * 100;
      bar.style.width = `${Math.min(100, progress)}%`;
    }, { passive: true });
  },

  initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', (e) => {
        const target = document.querySelector(anchor.getAttribute('href'));
        if (!target) return;
        e.preventDefault();
        const headerH = document.getElementById('sgc-header')?.offsetHeight || 80;
        window.scrollTo({
          top: target.offsetTop - headerH - 20,
          behavior: 'smooth'
        });
      });
    });
  },

  // ─── INTERSECTION OBSERVER ───────────────────────────────

  initRevealAnimations() {
    const elements = document.querySelectorAll(
      '.sgc-reveal, .sgc-reveal-left, .sgc-reveal-right, .sgc-reveal-scale, .sgc-stagger'
    );

    if (!elements.length) return;

    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -60px 0px' });

    elements.forEach(el => io.observe(el));
    this._observers.set('reveal', io);
  },

  // ─── COUNTERS ────────────────────────────────────────────

  initCounters() {
    const counters = document.querySelectorAll('[data-sgc-counter]');
    if (!counters.length) return;

    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          this.animateCounter(entry.target);
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.5 });

    counters.forEach(el => io.observe(el));
  },

  animateCounter(el) {
    const target = parseFloat(el.dataset.sgcCounter);
    const prefix  = el.dataset.prefix  || '';
    const suffix  = el.dataset.suffix  || '';
    const decimals= parseInt(el.dataset.decimals) || 0;
    const duration= parseInt(el.dataset.duration) || 2000;

    const start = performance.now();
    const easeOut = t => 1 - Math.pow(1 - t, 3);

    const tick = (now) => {
      const elapsed  = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const value    = easeOut(progress) * target;

      el.textContent = prefix + value.toFixed(decimals) + suffix;

      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        el.textContent = prefix + target.toFixed(decimals) + suffix;
      }
    };

    requestAnimationFrame(tick);
  },

  // ─── MOBILE MENU ─────────────────────────────────────────

  initMobileMenu() {
    const toggle = document.querySelector('.sgc-hamburger');
    const menu   = document.querySelector('.sgc-mobile-menu');
    const body   = document.body;

    if (!toggle || !menu) return;

    toggle.addEventListener('click', () => {
      const open = menu.classList.toggle('open');
      toggle.classList.toggle('open', open);
      body.style.overflow = open ? 'hidden' : '';
    });

    // Close on overlay click
    menu.addEventListener('click', (e) => {
      if (e.target === menu) {
        menu.classList.remove('open');
        toggle.classList.remove('open');
        body.style.overflow = '';
      }
    });

    // Close on ESC
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        menu.classList.remove('open');
        toggle.classList.remove('open');
        body.style.overflow = '';
      }
    });
  },

  // ─── ACCORDIONS ──────────────────────────────────────────

  initAccordions() {
    const triggers = document.querySelectorAll('.sgc-accordion-trigger');

    triggers.forEach(trigger => {
      trigger.addEventListener('click', () => {
        const item = trigger.closest('.sgc-accordion-item');
        const accordion = trigger.closest('.sgc-accordion');
        const isOpen = item.classList.contains('open');

        // Close all in same accordion
        if (accordion) {
          accordion.querySelectorAll('.sgc-accordion-item.open').forEach(openItem => {
            if (openItem !== item) {
              openItem.classList.remove('open');
            }
          });
        }

        item.classList.toggle('open', !isOpen);
      });
    });
  },

  // ─── TABS ────────────────────────────────────────────────

  initTabs() {
    const tabBtns = document.querySelectorAll('.sgc-tab-btn');

    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.tab;
        const container = btn.closest('[data-tabs-container]') || document;

        // Deactivate all
        btn.closest('.sgc-tabs-nav').querySelectorAll('.sgc-tab-btn').forEach(b => {
          b.classList.remove('active');
        });

        container.querySelectorAll('.sgc-tab-content').forEach(c => {
          c.classList.remove('active');
        });

        // Activate selected
        btn.classList.add('active');
        const content = container.querySelector(`[data-tab-content="${target}"]`);
        if (content) content.classList.add('active');
      });
    });
  },

  // ─── RANGE SLIDERS ───────────────────────────────────────

  initRangeSliders() {
    const ranges = document.querySelectorAll('.sgc-range');

    ranges.forEach(range => {
      const updateProgress = () => {
        const val = ((range.value - range.min) / (range.max - range.min)) * 100;
        range.style.setProperty('--range-progress', `${val}%`);
      };

      range.addEventListener('input', updateProgress);
      updateProgress();
    });
  },

  // ─── TOAST NOTIFICATIONS ─────────────────────────────────

  showToast(message, type = 'info', duration = 4000) {
    const existing = document.querySelector('.sgc-toast');
    if (existing) existing.remove();

    const icons = {
      success: '✦',
      error: '✕',
      info: '◎',
      warning: '⚠'
    };

    const toast = document.createElement('div');
    toast.className = 'sgc-toast';
    toast.innerHTML = `
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="font-size:1.1rem;color:var(--sgc-electric-cyan)">${icons[type]}</span>
        <span style="font-size:0.875rem;font-weight:500">${message}</span>
      </div>
    `;
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
      requestAnimationFrame(() => toast.classList.add('show'));
    });

    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 400);
    }, duration);
  },

};

// ─── INIT ON DOM READY ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  SGC.Core.init();
});

// Export for Odoo module system
export default SGC.Core;
