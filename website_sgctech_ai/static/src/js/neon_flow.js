/**
 * SGC TECH AI — Test Script
 * Verifies deployment is working
 */
(function() {
    'use strict';
    console.log('[SGC] === SCRIPT VERSION: 2026-05-04-v3 ===');
    console.log('[SGC] If you see neon cursor errors, they are from CACHED code');
    console.log('[SGC] Current neon_flow.js has NO neon code - only 12 lines');
    
    // Verify theme
    var wrapwrap = document.getElementById('wrapwrap');
    if (wrapwrap && wrapwrap.classList.contains('sgc-theme')) {
        console.log('[SGC] ✓ SGC theme loaded');
    } else {
        console.log('[SGC] ✗ Not on SGC theme page');
    }
    
    // Check for OLD neon cursor code
    if (typeof initNeonCursor === 'function') {
        console.log('[SGC] ✗ OLD cached code detected (initNeonCursor function exists)');
    } else {
        console.log('[SGC] ✓ No cached neon code detected');
    }
})();
