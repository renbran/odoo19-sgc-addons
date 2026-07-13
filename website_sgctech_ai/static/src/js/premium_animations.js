/** @odoo-module **/

/** ============================================================
 *  SGC TECH AI — Premium Animation Engine
 *  Custom Cursor · Glow Trail · Click Ripple · Smooth Scroll
 *  Parallax Depth · Section Transitions · Progress Indicator
 * ============================================================ */

function initSGCPremiumAnimations() {
    'use strict';

    /* ── Guard: only run on SGC-themed pages ─────────────── */
    const wrapwrap = document.getElementById('wrapwrap');
    if (!wrapwrap || !wrapwrap.classList.contains('sgc-theme')) {
        return;
    }

    /* ── Respect prefers-reduced-motion ─────────────────── */
    const motionOK = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!motionOK) return;

    /* ── Detect touch device ────────────────────────────── */
    const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);

    /* ── Utility ─────────────────────────────────────────── */
    const qs  = (s, ctx = document) => ctx.querySelector(s);
    const qsa = (s, ctx = document) => [...ctx.querySelectorAll(s)];
    const lerp  = (a, b, t) => a + (b - a) * t;
    const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

    /* ═══════════════════════════════════════════════════════
     *  §1  PREMIUM CUSTOM CURSOR
     * ═══════════════════════════════════════════════════════ */
    (function initPremiumCursor() {
        if (isTouch) return;

        /* Create cursor elements */
        const dot  = document.createElement('div');
        dot.className = 'sgc-cursor-dot';
        const ring = document.createElement('div');
        ring.className = 'sgc-cursor-ring';

        document.body.appendChild(dot);
        document.body.appendChild(ring);
        if (wrapwrap) wrapwrap.classList.add('sgc-cursor-active');

        /* State */
        let mx = -100, my = -100;         // actual mouse position
        let dx = -100, dy = -100;         // dot position (instant)
        let rx = -100, ry = -100;         // ring position (smooth)
        let dotState = '';                 // '', 'hovering', 'clicking', 'text'
        let rafId;

        /* Mouse tracking */
        document.addEventListener('mousemove', e => {
            mx = e.clientX;
            my = e.clientY;
        });
        document.addEventListener('mouseleave', () => {
            dot.style.opacity = '0';
            ring.style.opacity = '0';
        });
        document.addEventListener('mouseenter', () => {
            dot.style.opacity = '1';
            ring.style.opacity = '1';
        });

        /* Click ripple */
        document.addEventListener('mousedown', e => {
            dotState = 'clicking';
            updateCursorState();

            const ripple = document.createElement('div');
            ripple.className = 'sgc-cursor-ripple';
            ripple.style.left = e.clientX + 'px';
            ripple.style.top  = e.clientY + 'px';
            document.body.appendChild(ripple);
            ripple.addEventListener('animationend', () => ripple.remove());
        });
        document.addEventListener('mouseup', () => {
            dotState = '';
            updateCursorState();
        });

        /* Hover detection */
        const hoverSelectors = [
            'a:not(.sgc-ind-tab)', 'button', '.sgc-btn',
            '.sgc-industry-card', '.sgc-casebook-card',
            '.sgc-pricing-card', '.sgc-why-card',
            '.sgc-testi-card', '.sgc-mvv-card',
            '.sgc-competency-card', '.sgc-trust-badge',
            '.sgc-timeline-content', '[data-tilt="true"]',
            '.sgc-ind-tab', '.sgc-footer-col a',
            'input', 'select', 'textarea', '.form-control'
        ];
        const textSelectors = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', '.sgc-gradient-text'];

        document.addEventListener('mouseover', e => {
            const t = e.target;
            if (hoverSelectors.some(s => t.closest(s))) {
                dotState = 'hovering';
            } else if (textSelectors.some(s => t.closest(s))) {
                dotState = 'text';
            } else {
                dotState = '';
            }
            updateCursorState();
        });
        document.addEventListener('mouseout', e => {
            if (!e.relatedTarget || !hoverSelectors.concat(textSelectors).some(s => e.relatedTarget.closest(s))) {
                dotState = '';
                updateCursorState();
            }
        });

        function updateCursorState() {
            dot.classList.remove('is-hovering', 'is-clicking', 'is-text');
            ring.classList.remove('is-hovering', 'is-clicking', 'is-text');
            if (dotState) {
                dot.classList.add('is-' + dotState);
                ring.classList.add('is-' + dotState);
            }
        }

        /* Animation loop — ring follows with lerp delay */
        function animateCursor() {
            dx = mx;
            dy = my;
            rx = lerp(rx, mx, 0.12);
            ry = lerp(ry, my, 0.12);

            dot.style.left  = dx + 'px';
            dot.style.top   = dy + 'px';
            ring.style.left = rx + 'px';
            ring.style.top  = ry + 'px';

            rafId = requestAnimationFrame(animateCursor);
        }
        animateCursor();

        window.addEventListener('pagehide', () => cancelAnimationFrame(rafId), { once: true });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §2  CURSOR GLOW TRAIL (Canvas)
     * ═══════════════════════════════════════════════════════ */
    (function initCursorGlow() {
        if (isTouch) return;

        const canvas = document.createElement('canvas');
        canvas.className = 'sgc-cursor-glow';
        document.body.appendChild(canvas);

        const ctx = canvas.getContext('2d');
        let W, H, points = [], rafId;

        const MAX_TRAIL = 25;

        function resize() {
            W = canvas.width  = window.innerWidth;
            H = canvas.height = window.innerHeight;
        }
        resize();
        window.addEventListener('resize', resize, { passive: true });

        let lastMx = 0, lastMy = 0;
        document.addEventListener('mousemove', e => {
            lastMx = e.clientX;
            lastMy = e.clientY;
            points.push({ x: e.clientX, y: e.clientY, age: 1.0 });
            if (points.length > MAX_TRAIL) points.shift();
        });

        function draw() {
            ctx.clearRect(0, 0, W, H);

            for (let i = 0; i < points.length; i++) {
                const p = points[i];
                p.age -= 0.035;
                if (p.age <= 0) { points.splice(i, 1); i--; continue; }

                const alpha = p.age * 0.15;
                const size  = p.age * 30;

                const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, size);
                gradient.addColorStop(0, 'rgba(0, 212, 255, ' + alpha + ')');
                gradient.addColorStop(0.5, 'rgba(123, 47, 190, ' + (alpha * 0.5) + ')');
                gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

                ctx.beginPath();
                ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
                ctx.fillStyle = gradient;
                ctx.fill();
            }

            rafId = requestAnimationFrame(draw);
        }
        draw();
        window.addEventListener('pagehide', () => cancelAnimationFrame(rafId), { once: true });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §3  SCROLL PROGRESS INDICATOR
     * ═══════════════════════════════════════════════════════ */
    (function initScrollProgress() {
        const bar = document.createElement('div');
        bar.className = 'sgc-scroll-progress';
        document.body.appendChild(bar);

        function updateProgress() {
            const scrollTop = window.scrollY;
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            const progress  = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
            bar.style.width = clamp(progress, 0, 100) + '%';
        }
        window.addEventListener('scroll', updateProgress, { passive: true });
        updateProgress();
    })();

    /* ═══════════════════════════════════════════════════════
     *  §4  ENHANCED SCROLL REVEAL
     * ═══════════════════════════════════════════════════════ */
    (function initEnhancedReveal() {
        const revealSelectors = [
            '.sgc-reveal', '.sgc-reveal-left', '.sgc-reveal-right',
            '.sgc-reveal-scale', '.sgc-reveal-clip', '.sgc-reveal-clip-left',
            '.sgc-reveal-clip-right', '.sgc-reveal-blur', '.sgc-reveal-rotate',
            '.sgc-card-stack-enter', '.sgc-counter-item',
            '.sgc-section-header', '.sgc-why-icon', '.sgc-competency-icon',
            '.sgc-icon-box', '.sgc-cta-inner'
        ];

        const els = qsa(revealSelectors.join(','));
        if (!els.length) return;

        const io = new IntersectionObserver((entries) => {
            entries.forEach(e => {
                if (e.isIntersecting) {
                    e.target.classList.add('visible');
                    io.unobserve(e.target);
                }
            });
        }, { threshold: 0.10, rootMargin: '0px 0px -30px 0px' });

        els.forEach(el => io.observe(el));
    })();

    /* ═══════════════════════════════════════════════════════
     *  §5  PARALLAX DEPTH ON SCROLL
     * ═══════════════════════════════════════════════════════ */
    (function initParallaxDepth() {
        /* Slow parallax — decorative elements */
        const slowEls = qsa('.sgc-orb, .sgc-float-card, .sgc-about-glow-ring');
        /* Fast parallax — images that push forward */
        const fastEls = qsa('.sgc-ind-card-bg, .sgc-page-hero-bg');

        if (!slowEls.length && !fastEls.length) return;

        let ticking = false;
        window.addEventListener('scroll', () => {
            if (ticking) return;
            ticking = true;
            requestAnimationFrame(() => {
                const y = window.scrollY;
                slowEls.forEach(el => {
                    const speed = parseFloat(el.dataset.speed || '0.04');
                    const rect = el.getBoundingClientRect();
                    if (rect.bottom > 0 && rect.top < window.innerHeight) {
                        el.style.transform = 'translateY(' + (y * speed) + 'px)';
                    }
                });
                fastEls.forEach(el => {
                    const speed = parseFloat(el.dataset.speed || '-0.02');
                    const rect = el.parentElement ? el.parentElement.getBoundingClientRect() : el.getBoundingClientRect();
                    if (rect.bottom > 0 && rect.top < window.innerHeight) {
                        el.style.transform = (el.style.transform || '').replace(/translateY\([^)]*\)/, '') +
                            ' translateY(' + (y * speed) + 'px)';
                    }
                });
                ticking = false;
            });
        }, { passive: true });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §6  SMOOTH ANCHOR SCROLLING
     * ═══════════════════════════════════════════════════════ */
    (function initSmoothAnchors() {
        document.addEventListener('click', e => {
            const link = e.target.closest('a[href^="#"]');
            if (!link) return;

            const targetId = link.getAttribute('href');
            if (!targetId || targetId === '#') return;

            const target = qs(targetId);
            if (!target) return;

            e.preventDefault();

            const navH = qs('.navbar') ? qs('.navbar').offsetHeight : 0;
            const offset = navH + 20;
            const y = target.getBoundingClientRect().top + window.scrollY - offset;

            window.scrollTo({ top: Math.max(0, y), behavior: 'smooth' });
        });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §7  MAGNETIC HOVER ENHANCEMENT (all interactive cards)
     * ═══════════════════════════════════════════════════════ */
    (function initEnhancedMagnetic() {
        if (isTouch) return;

        const magneticEls = qsa('.sgc-btn, .sgc-chip, .sgc-trust-badge, .sgc-icon-box');
        magneticEls.forEach(el => {
            el.addEventListener('mousemove', function (e) {
                const rect = this.getBoundingClientRect();
                const cx   = rect.left + rect.width  / 2;
                const cy   = rect.top  + rect.height / 2;
                const dx   = (e.clientX - cx) * 0.2;
                const dy   = (e.clientY - cy) * 0.2;
                this.style.transform = 'translate(' + dx + 'px, ' + dy + 'px)';
            });
            el.addEventListener('mouseleave', function () {
                this.style.transform = '';
            });
        });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §8  FLOAT CARD PARALLAX ON MOUSE MOVE
     * ═══════════════════════════════════════════════════════ */
    (function initFloatCardParallax() {
        if (isTouch) return;

        const floatCards = qsa('.sgc-float-card');
        floatCards.forEach(card => {
            card.classList.add('parallax-active');
            const parent = card.closest('.sgc-about-story') || card.parentElement;
            if (!parent) return;

            parent.addEventListener('mousemove', e => {
                const rect = parent.getBoundingClientRect();
                const px = (e.clientX - rect.left) / rect.width;
                const py = (e.clientY - rect.top)  / rect.height;
                const shiftX = (px - 0.5) * 20;
                const shiftY = (py - 0.5) * 20;
                card.style.transform = 'translate(' + shiftX + 'px, ' + shiftY + 'px)';
            });
            parent.addEventListener('mouseleave', () => {
                card.style.transform = '';
            });
        });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §9  SECTION HEADER STAGGER ANIMATION
     * ═══════════════════════════════════════════════════════ */
    (function initSectionHeaderStagger() {
        const headers = qsa('.sgc-section-header');
        if (!headers.length) return;

        const io = new IntersectionObserver((entries) => {
            entries.forEach(e => {
                if (e.isIntersecting) {
                    e.target.classList.add('visible');
                    io.unobserve(e.target);
                }
            });
        }, { threshold: 0.2 });

        headers.forEach(h => io.observe(h));
    })();

}

/* ── Bootstrap ──────────────────────────────────────────────── */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSGCPremiumAnimations, { once: true });
} else {
    initSGCPremiumAnimations();
}
