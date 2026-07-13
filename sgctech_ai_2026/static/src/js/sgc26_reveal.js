/** @odoo-module **/
/* SGC Tech AI 2026 — IntersectionObserver scroll-reveal */

(function () {
    'use strict';

    const wrap = document.getElementById('wrapwrap');
    if (!wrap || !wrap.classList.contains('sgc-v26')) return;

    const motionOK = (window.SGC26 || {}).motionOK !== false &&
                     !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function initReveal() {
        const els = document.querySelectorAll('[data-sgc-reveal]');
        if (!els.length) return;

        if (!motionOK) {
            els.forEach(el => el.classList.add('revealed'));
            return;
        }

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('revealed');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

        els.forEach(el => observer.observe(el));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initReveal);
    } else {
        initReveal();
    }

})();
