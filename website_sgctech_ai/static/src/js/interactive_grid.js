(function () {
    'use strict';

    var wrapwrap = document.getElementById('wrapwrap');
    if (!wrapwrap || !wrapwrap.classList.contains('sgc-theme')) return;

    var hero   = document.querySelector('.sgc-about-trust-hero');
    var canvas = document.getElementById('sgc-grid-canvas');
    if (!hero || !canvas) return;

    var ctx  = canvas.getContext('2d');
    var dots = [];
    var mouse = { x: -9999, y: -9999 };

    var SPACING   = 30;
    var PROXIMITY = 120;
    var PROX_SQ   = PROXIMITY * PROXIMITY;
    var HUE       = 192;

    function buildDots() {
        dots = [];
        var w = canvas.width;
        var h = canvas.height;
        for (var y = 0; y <= h; y += SPACING) {
            for (var x = 0; x <= w; x += SPACING) {
                dots.push({ x: x, y: y });
            }
        }
    }

    function resize() {
        var rect    = hero.getBoundingClientRect();
        canvas.width  = rect.width;
        canvas.height = rect.height;
        buildDots();
    }

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (var i = 0; i < dots.length; i++) {
            var d    = dots[i];
            var dx   = d.x - mouse.x;
            var dy   = d.y - mouse.y;
            var dSq  = dx * dx + dy * dy;

            if (dSq < PROX_SQ) {
                var t   = dSq / PROX_SQ;              // 0 (at cursor) → 1 (at edge)
                var lum = Math.round(55 - t * 45);    // 55 % at cursor, 10 % at edge
                var col = 'hsl(' + HUE + ',100%,' + lum + '%)';
                var r   = 1.2 + (2.0 - 1.2) * (1 - t);

                ctx.beginPath();
                ctx.moveTo(d.x, d.y);
                ctx.lineTo(mouse.x, mouse.y);
                ctx.strokeStyle = 'hsla(' + HUE + ',100%,' + lum + '%,0.22)';
                ctx.lineWidth   = 0.6;
                ctx.stroke();

                ctx.beginPath();
                ctx.arc(d.x, d.y, r, 0, 6.2832);
                ctx.fillStyle = col;
                ctx.fill();
            } else {
                ctx.beginPath();
                ctx.arc(d.x, d.y, 1.2, 0, 6.2832);
                ctx.fillStyle = 'rgba(0,212,255,0.10)';
                ctx.fill();
            }
        }

        requestAnimationFrame(draw);
    }

    function onMouseMove(e) {
        var rect  = hero.getBoundingClientRect();
        mouse.x   = e.clientX - rect.left;
        mouse.y   = e.clientY - rect.top;
    }

    function onMouseLeave() {
        mouse.x = -9999;
        mouse.y = -9999;
    }

    hero.addEventListener('mousemove',  onMouseMove,  { passive: true });
    hero.addEventListener('mouseleave', onMouseLeave, { passive: true });
    window.addEventListener('resize',   resize,       { passive: true });

    resize();
    draw();
})();
