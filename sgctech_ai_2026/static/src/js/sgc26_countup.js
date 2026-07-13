/** @odoo-module **/
/* SGC Tech AI 2026 — Animated count-up for KPI tiles */

(function () {
    'use strict';

    const wrap = document.getElementById('wrapwrap');
    if (!wrap || !wrap.classList.contains('sgc-v26')) return;

    const motionOK = (window.SGC26 || {}).motionOK !== false &&
                     !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function easeOutQuart(t) { return 1 - Math.pow(1 - t, 4); }

    function animateCount(el) {
        const target   = parseFloat(el.dataset.sgcCount || 0);
        const prefix   = el.dataset.sgcPrefix  || '';
        const suffix   = el.dataset.sgcSuffix  || '';
        const decimals = parseInt(el.dataset.sgcDecimals || 0, 10);
        const duration = parseInt(el.dataset.sgcDuration || 1800, 10);

        if (!motionOK) {
            el.textContent = prefix + target.toFixed(decimals) + suffix;
            return;
        }

        const start = performance.now();
        function step(now) {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const value = target * easeOutQuart(progress);
            el.textContent = prefix + value.toFixed(decimals) + suffix;
            if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    function initCountup() {
        const els = document.querySelectorAll('[data-sgc-count]');
        if (!els.length) return;

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCount(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });

        els.forEach(el => observer.observe(el));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCountup);
    } else {
        initCountup();
    }

})();
