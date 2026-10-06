/** @odoo-module **/
/* SGC Tech AI 2026 — Vanilla 3D tilt for glass cards */

(function () {
    'use strict';

    const wrap = document.getElementById('wrapwrap');
    if (!wrap || !wrap.classList.contains('sgc-v26')) return;

    const motionOK = (window.SGC26 || {}).motionOK !== false &&
                     !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!motionOK) return;

    function initTilt() {
        const cards = document.querySelectorAll('[data-sgc-tilt]');
        if (!cards.length) return;

        cards.forEach(card => {
            const maxDeg = parseFloat(card.dataset.sgcTiltMax || 6);
            const perspective = parseInt(card.dataset.sgcTiltPerspective || 1000, 10);

            card.style.transformStyle = 'preserve-3d';
            card.style.perspective = perspective + 'px';

            card.addEventListener('mousemove', (e) => {
                const rect  = card.getBoundingClientRect();
                const cx    = rect.left + rect.width / 2;
                const cy    = rect.top  + rect.height / 2;
                const dx    = (e.clientX - cx) / (rect.width  / 2);
                const dy    = (e.clientY - cy) / (rect.height / 2);
                const rotX  = -dy * maxDeg;
                const rotY  =  dx * maxDeg;
                card.style.transform = `perspective(${perspective}px) rotateX(${rotX}deg) rotateY(${rotY}deg) scale3d(1.02,1.02,1.02)`;
            });

            card.addEventListener('mouseleave', () => {
                card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1,1,1)';
                card.style.transition = 'transform 0.4s cubic-bezier(0.34,1.56,0.64,1)';
                setTimeout(() => { card.style.transition = ''; }, 400);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTilt);
    } else {
        initTilt();
    }

})();
