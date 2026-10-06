/** @odoo-module **/
/* SGC Tech AI 2026 — Core: guard, motionOK, nav, utils */

(function () {
    'use strict';

    /* ── Guard ───────────────────────────────────────────── */
    const wrap = document.getElementById('wrapwrap');
    if (!wrap || !wrap.classList.contains('sgc-v26')) return;

    /* ── Global namespace ────────────────────────────────── */
    window.SGC26 = window.SGC26 || {};
    const SGC26 = window.SGC26;

    SGC26.motionOK = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    SGC26.ready    = false;

    /* ── Utility: debounce ───────────────────────────────── */
    SGC26.debounce = function (fn, ms) {
        let t;
        return function (...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), ms);
        };
    };

    /* ── Utility: raf loop ───────────────────────────────── */
    SGC26.raf = function (fn) {
        if (!SGC26.motionOK) return;
        (function loop() { fn(); requestAnimationFrame(loop); })();
    };

    /* ── Navigation ──────────────────────────────────────── */
    (function initNav() {
        const nav = document.querySelector('.sgc26-nav');
        if (!nav) return;

        let lastY = 0;
        let ticking = false;

        function onScroll() {
            if (ticking) return;
            ticking = true;
            requestAnimationFrame(() => {
                const y = window.scrollY;
                nav.classList.toggle('scrolled', y > 20);
                if (SGC26.motionOK) {
                    nav.classList.toggle('hidden', y > lastY + 8 && y > 120);
                }
                lastY = y;
                ticking = false;
            });
        }

        window.addEventListener('scroll', onScroll, { passive: true });

        /* Mobile menu */
        const burger   = document.querySelector('.sgc26-nav__hamburger');
        const mobile   = document.querySelector('.sgc26-nav__mobile');
        if (burger && mobile) {
            burger.addEventListener('click', () => {
                const open = mobile.classList.toggle('open');
                burger.setAttribute('aria-expanded', open);
                document.body.style.overflow = open ? 'hidden' : '';
            });
            /* Close on link click */
            mobile.querySelectorAll('a').forEach(a => {
                a.addEventListener('click', () => {
                    mobile.classList.remove('open');
                    burger.setAttribute('aria-expanded', 'false');
                    document.body.style.overflow = '';
                });
            });
        }

        /* Active link highlighting */
        const path = window.location.pathname;
        nav.querySelectorAll('a').forEach(a => {
            if (a.getAttribute('href') === path) {
                a.setAttribute('aria-current', 'page');
            }
        });
    })();

    /* ── Footer newsletter form ──────────────────────────── */
    (function initFooterForm() {
        const form  = document.querySelector('.sgc26-footer__email-form');
        const input = form && form.querySelector('.sgc26-footer__email-input');
        const btn   = form && form.querySelector('.sgc26-btn');
        if (!form || !input || !btn) return;

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const email = input.value.trim();
            const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!re.test(email)) {
                input.style.borderColor = '#FF4B4B';
                return;
            }
            input.style.borderColor = '';
            btn.textContent = 'Submitted';
            btn.disabled = true;
        });
    })();

    /* ── Ready flag ──────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', () => { SGC26.ready = true; });

})();
