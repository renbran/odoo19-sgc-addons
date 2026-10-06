/** @odoo-module **/
/* ============================================================
   SGC TECH AI — Login Page Enhancements
   ============================================================ */

'use strict';

document.addEventListener('DOMContentLoaded', () => {
  const body = document.body;

  // Apply SGC auth theme
  if (body.classList.contains('o_login_page')) {
    body.classList.add('sgc-auth-page');

    // Inject particle canvas
    const canvas = document.createElement('canvas');
    canvas.style.cssText = `
      position:fixed;inset:0;width:100%;height:100%;
      pointer-events:none;z-index:0;opacity:0.4;
    `;
    body.insertBefore(canvas, body.firstChild);

    const ctx = canvas.getContext('2d');
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;

    // Simple auth particle system
    const particles = Array.from({ length: 40 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4 - 0.1,
      r:  Math.random() * 2 + 1,
      o:  Math.random() * 0.4 + 0.1,
    }));

    const tick = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0, 255, 240, ${p.o})`;
        ctx.fill();
      });
      requestAnimationFrame(tick);
    };
    tick();

    window.addEventListener('resize', () => {
      canvas.width  = window.innerWidth;
      canvas.height = window.innerHeight;
    }, { passive: true });
  }

  // Enhance form inputs
  document.querySelectorAll('.o_login_page input[type="text"], .o_login_page input[type="email"], .o_login_page input[type="password"]').forEach(input => {
    input.addEventListener('focus', () => {
      input.closest('.form-group, .mb-3')?.classList.add('focused');
    });
    input.addEventListener('blur', () => {
      input.closest('.form-group, .mb-3')?.classList.remove('focused');
    });
  });
});
