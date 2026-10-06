/** @odoo-module **/
/* ============================================================
   SGC TECH AI — Backend Overrides
   Odoo 19 backend customizations for brand consistency
   ============================================================ */

'use strict';

import { Component, onMounted } from "@odoo/owl";

// Inject SGC branding into backend on mount
document.addEventListener('DOMContentLoaded', () => {
  // Update page title
  if (window.location.pathname.startsWith('/web')) {
    const link = document.querySelector("link[rel*='icon']") || document.createElement('link');
    link.rel  = 'icon';
    link.type = 'image/svg+xml';
    link.href = '/sgc_theme_ai/static/src/img/favicon.svg';
    document.head.appendChild(link);
  }
});
