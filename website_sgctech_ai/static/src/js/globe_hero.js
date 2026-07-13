/**
 * SGC TECH AI — Rotating Globe Hero
 * Vanilla JS + D3.js v7  (Promise API, NOT callbacks)
 * Features: orthographic projection, halftone dots, auto-rotate,
 *           drag, scroll-zoom, country hover highlight, country click stats
 */
(function() {
    'use strict';

    /* ─── AI Stats per country ──────────────────────────────────── */
    /* code = ISO 3166-1 alpha-2, used for flagcdn.com image URLs    */
    var countryAIStats = {
        'United Arab Emirates':    { code: 'ae', businesses: '14,200+',    adoption: '38%', successRate: '82%', avgROI: '340%' },
        'Saudi Arabia':            { code: 'sa', businesses: '31,000+',    adoption: '29%', successRate: '78%', avgROI: '290%' },
        'United States of America':{ code: 'us', businesses: '2,100,000+', adoption: '58%', successRate: '74%', avgROI: '410%' },
        'United Kingdom':          { code: 'gb', businesses: '320,000+',   adoption: '52%', successRate: '76%', avgROI: '380%' },
        'Germany':                 { code: 'de', businesses: '410,000+',   adoption: '49%', successRate: '79%', avgROI: '370%' },
        'France':                  { code: 'fr', businesses: '280,000+',   adoption: '44%', successRate: '75%', avgROI: '350%' },
        'Japan':                   { code: 'jp', businesses: '520,000+',   adoption: '47%', successRate: '80%', avgROI: '360%' },
        'Singapore':               { code: 'sg', businesses: '42,000+',    adoption: '61%', successRate: '85%', avgROI: '430%' },
        'Australia':               { code: 'au', businesses: '190,000+',   adoption: '46%', successRate: '77%', avgROI: '355%' },
        'Canada':                  { code: 'ca', businesses: '310,000+',   adoption: '51%', successRate: '75%', avgROI: '375%' },
        'India':                   { code: 'in', businesses: '780,000+',   adoption: '32%', successRate: '71%', avgROI: '265%' },
        'China':                   { code: 'cn', businesses: '1,800,000+', adoption: '41%', successRate: '69%', avgROI: '305%' },
        'Brazil':                  { code: 'br', businesses: '420,000+',   adoption: '27%', successRate: '68%', avgROI: '245%' },
        'South Africa':            { code: 'za', businesses: '58,000+',    adoption: '21%', successRate: '66%', avgROI: '220%' },
        'Nigeria':                 { code: 'ng', businesses: '34,000+',    adoption: '14%', successRate: '62%', avgROI: '195%' },
        'Egypt':                   { code: 'eg', businesses: '29,000+',    adoption: '18%', successRate: '64%', avgROI: '210%' },
        'Kuwait':                  { code: 'kw', businesses: '8,400+',     adoption: '33%', successRate: '77%', avgROI: '315%' },
        'Qatar':                   { code: 'qa', businesses: '11,200+',    adoption: '36%', successRate: '80%', avgROI: '330%' },
        'Bahrain':                 { code: 'bh', businesses: '6,100+',     adoption: '34%', successRate: '79%', avgROI: '320%' },
        'Oman':                    { code: 'om', businesses: '9,800+',     adoption: '28%', successRate: '74%', avgROI: '280%' }
    };

    /* ─── Guard: only run on SGC theme pages ─────────────────────── */
    var wrapwrap = document.getElementById('wrapwrap');
    if (!wrapwrap || !wrapwrap.classList.contains('sgc-theme')) { return; }

    /* ─── Wait for D3 ────────────────────────────────────────────── */
    if (typeof d3 === 'undefined') {
        var check = setInterval(function() {
            if (typeof d3 !== 'undefined') { clearInterval(check); init(); }
        }, 100);
        return;
    }
    init();

    /* ─── Main init ──────────────────────────────────────────────── */
    function init() {
        var canvas = document.getElementById('sgc-globe-canvas');
        if (!canvas) { console.error('[SGC Globe] Canvas not found'); return; }
        var ctx = canvas.getContext('2d');
        if (!ctx) { console.error('[SGC Globe] No 2D context'); return; }

        var dpr = window.devicePixelRatio || 1;

        /* ── Size canvas to fill its CSS container ── */
        var width, height, baseR;
        function sizeCanvas() {
            var w = canvas.offsetWidth  || canvas.parentElement.offsetWidth  || window.innerWidth;
            var h = canvas.offsetHeight || canvas.parentElement.offsetHeight || window.innerHeight;
            width  = w;
            height = h;
            baseR  = Math.min(width, height) * 0.40;
            canvas.width  = width  * dpr;
            canvas.height = height * dpr;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        sizeCanvas();

        /* ── Projection ── */
        var projection = d3.geoOrthographic()
            .scale(baseR)
            .translate([width / 2, height / 2])
            .clipAngle(90);
        var path = d3.geoPath().projection(projection).context(ctx);

        /* ── State ── */
        var rotation     = [30, -20];
        var autoRotate   = true;
        var dots         = [];
        var land         = null;
        var countries    = null;
        var hoveredName  = null;
        var hoveredFeature = null;

        /* ─── Tooltip DOM ────────────────────────────────────────── */
        var tooltip = document.createElement('div');
        tooltip.id = 'sgc-globe-tooltip';
        tooltip.style.cssText = [
            'position:fixed',
            'display:none',
            'z-index:9999',
            'background:rgba(0,10,30,0.92)',
            'border:1px solid #7BD3F6',
            'border-radius:10px',
            'padding:14px 18px',
            'color:#fff',
            'font-family:Inter,sans-serif',
            'font-size:13px',
            'line-height:1.6',
            'min-width:220px',
            'max-width:280px',
            'pointer-events:none',
            'backdrop-filter:blur(8px)',
            'box-shadow:0 0 20px rgba(123,211,246,0.3)'
        ].join(';');
        document.body.appendChild(tooltip);

        function showTooltip(name, x, y) {
            var s = countryAIStats[name];
            var flagImg = (s && s.code)
                ? '<img src="https://flagcdn.com/w40/' + s.code + '.png"'
                + ' width="28" height="20"'
                + ' style="display:inline-block;vertical-align:middle;margin-right:8px;border-radius:2px;object-fit:cover;box-shadow:0 1px 3px rgba(0,0,0,0.4)"'
                + ' alt="' + name + ' flag">'
                : '';
            tooltip.innerHTML =
                '<div style="display:flex;align-items:center;margin-bottom:8px">'
                + flagImg
                + '<strong style="color:#7BD3F6;font-size:14px;line-height:1.2">' + name + '</strong>'
                + '</div>'
                + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 12px">'
                + '<span style="color:#aaa">Companies:</span><span>'    + (s ? s.businesses  : 'N/A') + '</span>'
                + '<span style="color:#aaa">AI Adoption:</span><span>'  + (s ? s.adoption    : 'N/A') + '</span>'
                + '<span style="color:#aaa">Success Rate:</span><span>' + (s ? s.successRate : 'N/A') + '</span>'
                + '<span style="color:#aaa">Avg ROI:</span><span>'      + (s ? s.avgROI      : 'N/A') + '</span>'
                + '</div>';
            tooltip.style.display = 'block';
            positionTooltip(x, y);
        }
        function positionTooltip(x, y) {
            var tw = tooltip.offsetWidth  || 240;
            var th = tooltip.offsetHeight || 120;
            var left = x + 16;
            var top  = y - th / 2;
            if (left + tw > window.innerWidth  - 10) { left = x - tw - 16; }
            if (top  < 10)                           { top  = 10; }
            if (top  + th > window.innerHeight - 10) { top  = window.innerHeight - th - 10; }
            tooltip.style.left = left + 'px';
            tooltip.style.top  = top  + 'px';
        }
        function hideTooltip() { tooltip.style.display = 'none'; }

        /* ─── Render ──────────────────────────────────────────────── */
        function render() {
            ctx.clearRect(0, 0, width, height);
            var s  = projection.scale();
            var sf = s / baseR;

            /* Ocean sphere */
            ctx.beginPath();
            ctx.arc(width / 2, height / 2, s, 0, 2 * Math.PI);
            ctx.fillStyle = 'rgba(0,6,20,0.85)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(123,211,246,0.6)';
            ctx.lineWidth = 1.5 * sf;
            ctx.stroke();

            if (!land) { return; }

            /* Graticule */
            ctx.beginPath();
            path(d3.geoGraticule()());
            ctx.strokeStyle = 'rgba(123,211,246,0.3)';
            ctx.lineWidth   = 0.6 * sf;
            ctx.stroke();

            /* Land outlines */
            ctx.beginPath();
            land.features.forEach(function(f) { path(f); });
            ctx.strokeStyle = 'rgba(180,220,255,0.5)';
            ctx.lineWidth   = 0.7 * sf;
            ctx.stroke();

            /* Hovered country fill */
            if (hoveredFeature) {
                ctx.beginPath();
                path(hoveredFeature);
                ctx.fillStyle   = 'rgba(123,211,246,0.18)';
                ctx.strokeStyle = '#7BD3F6';
                ctx.lineWidth   = 1.5 * sf;
                ctx.fill();
                ctx.stroke();
            }

            /* Halftone dots */
            var cx = width  / 2;
            var cy = height / 2;
            dots.forEach(function(d) {
                var p = projection(d);
                if (!p) { return; }
                var dx = p[0] - cx, dy = p[1] - cy;
                if (dx * dx + dy * dy > s * s) { return; }  // clip to sphere
                var isHovered = hoveredName && d._country === hoveredName;
                ctx.beginPath();
                ctx.arc(p[0], p[1], (isHovered ? 1.8 : 1.3) * sf, 0, 2 * Math.PI);
                ctx.fillStyle = isHovered ? '#7BD3F6' : 'rgba(160,210,255,0.75)';
                ctx.fill();
            });
        }

        /* ─── Data loading (D3 v7 Promise API) ──────────────────── */
        function loadData() {
            var landURL     = 'https://raw.githubusercontent.com/martynafford/natural-earth-geojson/refs/heads/master/110m/physical/ne_110m_land.json';
            var countryURL  = 'https://raw.githubusercontent.com/martynafford/natural-earth-geojson/refs/heads/master/110m/cultural/ne_110m_admin_0_countries.json';

            /* D3 v7: .then()/.catch() Promise API */
            d3.json(landURL)
                .then(function(data) {
                    land = data;
                    land.features.forEach(function(feature) {
                        var b = d3.geoBounds(feature);
                        for (var lng = b[0][0]; lng <= b[1][0]; lng += 1.3) {
                            for (var lat = b[0][1]; lat <= b[1][1]; lat += 1.3) {
                                if (d3.geoContains(feature, [lng, lat])) {
                                    dots.push([lng, lat]);
                                }
                            }
                        }
                    });
                    console.log('[SGC Globe] Land loaded, dots:', dots.length);
                    render();
                })
                .catch(function(err) {
                    console.error('[SGC Globe] Land data failed:', err);
                });

            d3.json(countryURL)
                .then(function(data) {
                    countries = data;
                    console.log('[SGC Globe] Countries loaded:', countries.features.length);
                    if (dots.length > 0) { tagDots(); }
                })
                .catch(function(err) {
                    console.warn('[SGC Globe] Country data failed — click disabled:', err);
                });
        }

        function tagDots() {
            if (!countries) { return; }
            dots.forEach(function(d) {
                for (var i = 0; i < countries.features.length; i++) {
                    if (d3.geoContains(countries.features[i], d)) {
                        d._country = countries.features[i].properties.NAME || countries.features[i].properties.name;
                        break;
                    }
                }
            });
        }

        function getCountryAtPoint(x, y) {
            if (!countries) { return null; }
            var coords = projection.invert([x, y]);
            if (!coords) { return null; }
            for (var i = 0; i < countries.features.length; i++) {
                if (d3.geoContains(countries.features[i], coords)) {
                    return countries.features[i];
                }
            }
            return null;
        }

        /* ─── Mouse events ──────────────────────────────────────────── */
        var dragging = false, lastX = 0, lastY = 0, dragMoved = false;

        canvas.addEventListener('mousedown', function(e) {
            dragging = true; dragMoved = false; autoRotate = false;
            lastX = e.clientX; lastY = e.clientY;
        });

        document.addEventListener('mousemove', function(e) {
            if (dragging) {
                var dx = e.clientX - lastX, dy = e.clientY - lastY;
                if (Math.abs(dx) > 2 || Math.abs(dy) > 2) { dragMoved = true; }
                rotation[0] += dx * 0.5;
                rotation[1] = Math.max(-90, Math.min(90, rotation[1] - dy * 0.5));
                projection.rotate(rotation);
                lastX = e.clientX; lastY = e.clientY;
                render();
            } else {
                var rect = canvas.getBoundingClientRect();
                var cx = e.clientX - rect.left, cy = e.clientY - rect.top;
                var feat = getCountryAtPoint(cx, cy);
                var name = feat ? (feat.properties.NAME || feat.properties.name) : null;
                if (name !== hoveredName) {
                    hoveredName    = name;
                    hoveredFeature = feat || null;
                    canvas.style.cursor = name ? 'pointer' : 'grab';
                    render();
                }
            }
        });

        document.addEventListener('mouseup', function() {
            dragging = false;
            setTimeout(function() { autoRotate = true; }, 3000);
        });

        canvas.addEventListener('click', function(e) {
            if (dragMoved) { return; }
            var rect = canvas.getBoundingClientRect();
            var feat = getCountryAtPoint(e.clientX - rect.left, e.clientY - rect.top);
            if (feat) {
                var name = feat.properties.NAME || feat.properties.name;
                showTooltip(name, e.clientX, e.clientY);
            } else {
                hideTooltip();
            }
        });

        document.addEventListener('click', function(e) {
            if (e.target !== canvas) { hideTooltip(); }
        });

        canvas.addEventListener('wheel', function(e) {
            e.preventDefault();
            var f = e.deltaY > 0 ? 0.9 : 1.1;
            projection.scale(Math.max(baseR * 0.4, Math.min(baseR * 3, projection.scale() * f)));
            render();
        }, { passive: false });

        /* Touch drag */
        var lastTX = 0, lastTY = 0;
        canvas.addEventListener('touchstart', function(e) {
            e.preventDefault(); autoRotate = false;
            lastTX = e.touches[0].clientX; lastTY = e.touches[0].clientY;
        }, { passive: false });
        canvas.addEventListener('touchmove', function(e) {
            e.preventDefault();
            var dx = e.touches[0].clientX - lastTX, dy = e.touches[0].clientY - lastTY;
            rotation[0] += dx * 0.5;
            rotation[1] = Math.max(-90, Math.min(90, rotation[1] - dy * 0.5));
            projection.rotate(rotation); lastTX = e.touches[0].clientX; lastTY = e.touches[0].clientY;
            render();
        }, { passive: false });
        canvas.addEventListener('touchend', function() {
            setTimeout(function() { autoRotate = true; }, 3000);
        });

        /* Resize */
        window.addEventListener('resize', function() {
            sizeCanvas();
            projection.scale(baseR).translate([width / 2, height / 2]);
            render();
        });

        /* ─── Auto-rotate loop ──────────────────────────────────────── */
        setInterval(function() {
            if (autoRotate) {
                rotation[0] += 0.25;
                projection.rotate(rotation);
                render();
            }
        }, 50);

        projection.rotate(rotation);
        loadData();
        console.log('[SGC Globe] Initialized, canvas:', width + 'x' + height, 'radius:', Math.round(baseR));
    }
})();
