/** @odoo-module **/

/** ============================================================
 *  SGC TECH AI — Main Theme JavaScript Engine
 *  Canvas Particles · Scroll Reveals · Counters · Magnetic Buttons
 * ============================================================ */

function initSGCTechTheme() {
    'use strict';

    /* ── Guard: only run on SGC-themed pages ─────────────── */
    const wrapwrap = document.getElementById('wrapwrap');
    if (!wrapwrap || !wrapwrap.classList.contains('sgc-theme')) {
        return;
    }

    /* ── Respect prefers-reduced-motion ─────────────────── */
    const motionOK = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* ── Utility ─────────────────────────────────────────── */
    const qs  = (s, ctx = document) => ctx.querySelector(s);
    const qsa = (s, ctx = document) => [...ctx.querySelectorAll(s)];
    const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
    const lerp  = (a, b, t) => a + (b - a) * t;

    /* ═══════════════════════════════════════════════════════
     *  §1  NAVBAR — glassmorphism scroll behaviour
     * ═══════════════════════════════════════════════════════ */
    (function initNavbar() {
        const nav = qs('.navbar');
        if (!nav) return;
        let lastY = 0;
        let hidden = false;
        function showNav() {
            if (!hidden) return;
            hidden = false;
            nav.style.transform = 'translateY(0)';
            nav.style.opacity   = '1';
        }
        function hideNav() {
            if (hidden) return;
            hidden = true;
            nav.style.transform = 'translateY(-120%)';
            nav.style.opacity   = '0';
        }
        window.addEventListener('scroll', () => {
            const y = window.scrollY;
            if (y > 60)  nav.classList.add('scrolled');
            else         nav.classList.remove('scrolled');
            /* hide on scroll down past 200px — show on ANY upward movement */
            if (y > lastY + 8 && y > 200) hideNav();
            else if (y < lastY)            showNav();
            lastY = y;
        }, { passive: true });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §2  CANVAS PARTICLE NETWORK
     * ═══════════════════════════════════════════════════════ */
    (function initParticles() {
        if (!motionOK) return;
        const canvas = qs('#sgc-particles');
        if (!canvas) return;

        const ctx = canvas.getContext('2d', {willReadFrequently: true});
        if (!ctx) return;
        let W, H, particles = [], mouse = { x: -9999, y: -9999 }, rafId;

        const CONFIG = {
            count:        90,
            maxDist:      140,
            speed:        0.35,
            radius:       1.8,
            colorCyan:    'rgba(0, 212, 255, ',
            colorViolet:  'rgba(123, 47, 190, ',
            mouseRepel:   100,
        };

        function resize() {
            W = canvas.width  = canvas.offsetWidth;
            H = canvas.height = canvas.offsetHeight;
        }

        function randomParticle() {
            const hue = Math.random() < 0.6 ? CONFIG.colorCyan : CONFIG.colorViolet;
            return {
                x:   Math.random() * W,
                y:   Math.random() * H,
                vx:  (Math.random() - 0.5) * CONFIG.speed,
                vy:  (Math.random() - 0.5) * CONFIG.speed,
                r:   Math.random() * CONFIG.radius + 0.8,
                color: hue,
                alpha: Math.random() * 0.5 + 0.3,
            };
        }

        function initParticlePool() {
            particles = Array.from({ length: CONFIG.count }, randomParticle);
        }

        function draw() {
            ctx.clearRect(0, 0, W, H);

            /* move & bounce */
            for (const p of particles) {
                /* mouse repulsion */
                const dx = p.x - mouse.x, dy = p.y - mouse.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist > 0 && dist < CONFIG.mouseRepel) {
                    const force = (CONFIG.mouseRepel - dist) / CONFIG.mouseRepel;
                    p.vx += (dx / dist) * force * 0.8;
                    p.vy += (dy / dist) * force * 0.8;
                }
                /* dampen */
                p.vx *= 0.99;
                p.vy *= 0.99;
                /* speed clamp */
                const spd = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
                if (spd > CONFIG.speed * 3) { p.vx *= CONFIG.speed * 3 / spd; p.vy *= CONFIG.speed * 3 / spd; }

                p.x += p.vx;
                p.y += p.vy;
                /* wrap */
                if (p.x < -10) p.x = W + 10;
                if (p.x > W + 10) p.x = -10;
                if (p.y < -10) p.y = H + 10;
                if (p.y > H + 10) p.y = -10;

                /* dot */
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fillStyle = p.color + p.alpha + ')';
                ctx.fill();
            }

            /* connections */
            for (let i = 0; i < particles.length; i++) {
                for (let j = i + 1; j < particles.length; j++) {
                    const a = particles[i], b = particles[j];
                    const dx = a.x - b.x, dy = a.y - b.y;
                    const d = Math.sqrt(dx * dx + dy * dy);
                    if (d < CONFIG.maxDist) {
                        const alpha = (1 - d / CONFIG.maxDist) * 0.25;
                        ctx.beginPath();
                        ctx.moveTo(a.x, a.y);
                        ctx.lineTo(b.x, b.y);
                        ctx.strokeStyle = `rgba(0, 212, 255, ${alpha})`;
                        ctx.lineWidth = 0.8;
                        ctx.stroke();
                    }
                }
            }
            rafId = requestAnimationFrame(draw);
        }

        window.addEventListener('mousemove', e => {
            const rect = canvas.getBoundingClientRect();
            mouse.x = e.clientX - rect.left;
            mouse.y = e.clientY - rect.top;
        });
        document.addEventListener('mouseleave', () => { mouse.x = -9999; mouse.y = -9999; });
        window.addEventListener('pagehide', () => cancelAnimationFrame(rafId), { once: true });

        const resizeTarget = canvas.parentElement || canvas;
        const ro = new ResizeObserver(() => { resize(); });
        ro.observe(resizeTarget);
        window.addEventListener('pagehide', () => ro.disconnect(), { once: true });
        resize();
        initParticlePool();
        draw();
    })();

    /* ═══════════════════════════════════════════════════════
     *  §3  TYPEWRITER EFFECT
     * ═══════════════════════════════════════════════════════ */
    (function initTypewriter() {
        const el = qs('[data-typewriter]');
        if (!el) return;
        let phrases = [];
        try {
            phrases = JSON.parse(el.dataset.typewriter || '[]');
        } catch (error) {
            console.warn('SGC typewriter payload is invalid JSON.', error);
            return;
        }
        if (!phrases.length) return;

        const cursor = document.createElement('span');
        cursor.className = 'sgc-cursor';
        el.after(cursor);

        let pi = 0, ci = 0, deleting = false;
        function tick() {
            const phrase = phrases[pi % phrases.length];
            if (!deleting) {
                el.textContent = phrase.slice(0, ++ci);
                if (ci === phrase.length) { deleting = true; setTimeout(tick, 1800); return; }
                setTimeout(tick, 65);
            } else {
                el.textContent = phrase.slice(0, --ci);
                if (ci === 0) { deleting = false; pi++; setTimeout(tick, 400); return; }
                setTimeout(tick, 35);
            }
        }
        tick();
    })();

    /* ═══════════════════════════════════════════════════════
     *  §4  SCROLL REVEAL  (IntersectionObserver)
     * ═══════════════════════════════════════════════════════ */
    (function initReveal() {
        const els = qsa('.sgc-reveal, .sgc-reveal-left, .sgc-reveal-right, .sgc-reveal-scale');
        if (!els.length) return;

        const io = new IntersectionObserver((entries) => {
            entries.forEach(e => {
                if (e.isIntersecting) {
                    e.target.classList.add('visible');
                    io.unobserve(e.target);
                }
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

        els.forEach(el => io.observe(el));
    })();

    /* ═══════════════════════════════════════════════════════
     *  §5  ANIMATED COUNTERS
     * ═══════════════════════════════════════════════════════ */
    (function initCounters() {
        const counters = qsa('[data-count]');
        if (!counters.length) return;

        function easeOutQuart(t) { return 1 - Math.pow(1 - t, 4); }

        function animateCounter(el) {
            const target   = parseFloat(el.dataset.count);
            const suffix   = el.dataset.suffix || '';
            const prefix   = el.dataset.prefix || '';
            const decimals = el.dataset.decimals ? parseInt(el.dataset.decimals) : 0;
            const duration = 2000;
            const start    = performance.now();

            function step(now) {
                const t   = clamp((now - start) / duration, 0, 1);
                const val = easeOutQuart(t) * target;
                el.textContent = prefix + val.toFixed(decimals) + suffix;
                if (t < 1) requestAnimationFrame(step);
                else el.textContent = prefix + target.toFixed(decimals) + suffix;
            }
            requestAnimationFrame(step);
        }

        const io = new IntersectionObserver((entries) => {
            entries.forEach(e => {
                if (e.isIntersecting && !e.target.dataset.counted) {
                    e.target.dataset.counted = '1';
                    animateCounter(e.target);
                    io.unobserve(e.target);
                }
            });
        }, { threshold: 0.5 });

        counters.forEach(el => io.observe(el));
    })();

    /* ═══════════════════════════════════════════════════════
     *  §6  MAGNETIC BUTTON EFFECT
     * ═══════════════════════════════════════════════════════ */
    (function initMagneticButtons() {
        const btns = qsa('.sgc-btn-primary, .sgc-btn-secondary');
        btns.forEach(btn => {
            btn.addEventListener('mousemove', function (e) {
                const rect = this.getBoundingClientRect();
                const cx   = rect.left + rect.width  / 2;
                const cy   = rect.top  + rect.height / 2;
                const dx   = (e.clientX - cx) * 0.28;
                const dy   = (e.clientY - cy) * 0.28;
                this.style.transform = `translate(${dx}px, ${dy}px) translateY(-3px)`;
            });
            btn.addEventListener('mouseleave', function () {
                this.style.transform = '';
            });
        });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §7  SMOOTH ACTIVE NAV HIGHLIGHT
     * ═══════════════════════════════════════════════════════ */
    (function initScrollSpy() {
        const sections = qsa('section[id]');
        const navLinks = qsa('.nav-link[href^="#"]');
        if (!sections.length || !navLinks.length) return;

        const io = new IntersectionObserver((entries) => {
            entries.forEach(e => {
                if (e.isIntersecting) {
                    navLinks.forEach(l => l.classList.remove('active'));
                    const active = qs(`.nav-link[href="#${e.target.id}"]`);
                    if (active) active.classList.add('active');
                }
            });
        }, { rootMargin: '-40% 0px -55% 0px' });

        sections.forEach(s => io.observe(s));
    })();

    /* ═══════════════════════════════════════════════════════
     *  §8  PARALLAX ORBS
     * ═══════════════════════════════════════════════════════ */
    (function initParallax() {
        if (!motionOK) return;
        const orbs = qsa('.sgc-parallax-orb');
        if (!orbs.length) return;
        window.addEventListener('scroll', () => {
            const y = window.scrollY;
            orbs.forEach(orb => {
                const speed = parseFloat(orb.dataset.speed || '0.3');
                orb.style.transform = `translateY(${y * speed}px)`;
            });
        }, { passive: true });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §9  FLOATING TECH TICKER (pause on hover)
     * ═══════════════════════════════════════════════════════ */
    (function initTicker() {
        const track = qs('.sgc-tech-scroll-track');
        if (!track) return;
        track.addEventListener('mouseenter', () => { track.style.animationPlayState = 'paused'; });
        track.addEventListener('mouseleave', () => { track.style.animationPlayState = 'running'; });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §10  PRICING TOGGLE (monthly/annual)
     * ═══════════════════════════════════════════════════════ */
    (function initPricingToggle() {
        const toggle  = qs('#sgc-pricing-toggle');
        const prices  = qsa('[data-price-monthly]');
        if (!toggle || !prices.length) return;

        toggle.addEventListener('change', function () {
            prices.forEach(el => {
                el.textContent = this.checked
                    ? el.dataset.priceAnnual
                    : el.dataset.priceMonthly;
            });
        });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §11  CASEBOOK OPEN TRANSITION (Industries page)
     * ═══════════════════════════════════════════════════════ */
    (function initCasebookOpenTransition() {
        var links = qsa('.sgc-casebook-card[href^="#"]');
        if (!links.length) return;

        function scrollToTarget(targetId) {
            var target = qs(targetId);
            if (!target) return;

            var navbar = qs('.navbar');
            var indFilter = qs('.sgc-ind-filter');
            var navH = navbar ? navbar.offsetHeight : 0;
            var filterH = indFilter ? indFilter.offsetHeight : 0;
            var offset = navH + filterH + 20;
            var y = target.getBoundingClientRect().top + window.scrollY - offset;

            window.scrollTo({
                top: Math.max(0, y),
                behavior: motionOK ? 'smooth' : 'auto',
            });
        }

        links.forEach(function (link) {
            link.addEventListener('click', function (e) {
                var targetId = link.getAttribute('href');
                if (!targetId || targetId.charAt(0) !== '#') return;

                e.preventDefault();

                if (!motionOK) {
                    scrollToTarget(targetId);
                    return;
                }

                if (link.classList.contains('is-opening')) return;
                link.classList.add('is-opening');

                window.setTimeout(function () {
                    scrollToTarget(targetId);
                    link.classList.remove('is-opening');
                }, 320);
            });
        });
    })();

    /* ═══════════════════════════════════════════════════════
     *  §9  3D TILT CARDS — Interactive perspective effect
     *      Vanilla JS port of React InteractiveProductCard
     * ═══════════════════════════════════════════════════════ */
    (function initTiltCards() {
        if (!motionOK) return;

        var cards = qsa('[data-tilt="true"]');
        if (!cards.length) return;

        var MAX_ROT = 10;   // degrees
        var SCALE   = 1.04; // hover scale

        cards.forEach(function (card) {
            var bg    = qs('.sgc-ind-card-bg', card);
            var glare = qs('.sgc-card-glare', card);
            var raf   = null;

            card.addEventListener('mousemove', function (e) {
                if (raf) return; // throttle to rAF
                raf = requestAnimationFrame(function () {
                    var rect = card.getBoundingClientRect();
                    var x = e.clientX - rect.left;
                    var y = e.clientY - rect.top;
                    var px = x / rect.width;
                    var py = y / rect.height;

                    var rotX = (py - 0.5) * -MAX_ROT;
                    var rotY = (px - 0.5) *  MAX_ROT;

                    card.style.transform =
                        'perspective(1000px) rotateX(' + rotX + 'deg) rotateY(' + rotY + 'deg) scale3d(' + SCALE + ',' + SCALE + ',' + SCALE + ')';
                    card.style.transition = 'transform 0.08s ease-out';

                    // Parallax shift on background
                    if (bg) {
                        var shiftX = (px - 0.5) * -15;
                        var shiftY = (py - 0.5) * -15;
                        bg.style.transform =
                            'translateZ(-30px) scale(1.15) translate(' + shiftX + 'px,' + shiftY + 'px)';
                    }

                    // Glare follows cursor
                    if (glare) {
                        glare.style.setProperty('--glare-x', (px * 100) + '%');
                        glare.style.setProperty('--glare-y', (py * 100) + '%');
                    }

                    raf = null;
                });
            });

            card.addEventListener('mouseleave', function () {
                if (raf) { cancelAnimationFrame(raf); raf = null; }
                card.style.transform  = 'perspective(1000px) rotateX(0) rotateY(0) scale3d(1,1,1)';
                card.style.transition = 'transform 0.45s cubic-bezier(.03,.98,.52,.99)';
                if (bg) {
                    bg.style.transform  = 'translateZ(-30px) scale(1.15)';
                    bg.style.transition = 'transform 0.45s ease';
                }
            });
        });
    })();

}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSGCTechTheme, {
        once: true,
    });
} else {
    initSGCTechTheme();
}
