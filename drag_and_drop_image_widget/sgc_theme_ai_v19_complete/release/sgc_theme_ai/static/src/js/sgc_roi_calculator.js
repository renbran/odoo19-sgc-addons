/** @odoo-module **/
/**
 * SGC TECH AI — ROI Calculator (Client)
 *
 * FIX P2 / P3: ROI math moved to server (controllers/main.py calculate_roi()).
 *              This file now handles UI only — sliders, inputs, result display.
 *              No multiplier duplication between Python and JS.
 * FIX P2:      console.log removed.
 */

'use strict';

window.SGC = window.SGC || {};

SGC.ROICalc = {

  _debounceTimer: null,

  init() {
    const calc = document.getElementById('sgc-roi-calculator');
    if (!calc) return;
    this.bindEvents();
    this.calculate();  // Initial render on page load
  },

  bindEvents() {
    const inputs = document.querySelectorAll('.sgc-roi-input, [data-roi-input]');
    inputs.forEach(input => {
      input.addEventListener('input', () => this._debouncedCalc());
      input.addEventListener('change', () => this._debouncedCalc());
    });
  },

  _debouncedCalc() {
    clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(() => this.calculate(), 300);
  },

  getInputs() {
    return {
      employees:    parseInt(document.getElementById('roi-employees')?.value)    || 10,
      monthly_cost: parseFloat(document.getElementById('roi-monthly-cost')?.value) || 100000,
      industry:     document.getElementById('roi-industry')?.value                 || 'real_estate',
      hours_per_week: parseFloat(document.getElementById('roi-hours')?.value)     || 40,
    };
  },

  async calculate() {
    const inputs = this.getInputs();

    // Update slider display value
    const empDisplay = document.getElementById('employees-display');
    if (empDisplay) empDisplay.textContent = inputs.employees;

    try {
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content
                     || (typeof odoo !== 'undefined' ? odoo.csrf_token : '') || '';

      const response = await fetch('/sgc/roi/calculate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
          jsonrpc: '2.0', method: 'call', id: 1,
          params: inputs,
        }),
      });

      const data    = await response.json();
      const results = data.result || data;

      if (results && results.roi !== undefined) {
        this.updateUI(results);
      }

    } catch (_err) {
      // Silent fail — show last known values, don't crash the page
    }
  },

  updateUI(results) {
    this.setElement('roi-result',        `${results.roi}%`);
    this.setElement('roi-percent',       `${results.roi}%`);
    this.setElement('roi-annual-savings', this.formatAED(results.annual_savings));
    this.setElement('roi-labor-savings',  this.formatAED(results.labor_savings));
    this.setElement('roi-error-savings',  this.formatAED(results.error_savings));
    this.setElement('roi-efficiency',     this.formatAED(results.efficiency_gains));
    this.setElement('roi-net-benefit',    this.formatAED(results.net_benefit));
    this.setElement('roi-payback',        `${results.payback} months`);
    this.setElement('roi-hours',          `${results.saved_hours} hrs/mo`);
    this.setElement('roi-package',        results.package);
    this.setElement('roi-investment',     this.formatAED(results.investment));

    this.animateROI(results.roi);

    // Show CTA
    const cta = document.getElementById('roi-cta');
    if (cta) { cta.style.opacity = '1'; cta.style.transform = 'translateY(0)'; }
  },

  animateROI(targetROI) {
    const el = document.getElementById('roi-animated-number');
    if (!el) return;
    // FIX F4: Use explicit radix 10 and strip non-numeric characters so that
    // values like '150%' parse correctly without relying on parseInt’s partial-
    // parse behaviour (which happens to work but is fragile and misleading).
    const start    = parseInt(el.textContent.replace(/[^0-9]/g, ''), 10) || 0;
    const duration = 1000;
    const startTs  = performance.now();
    const easeOut  = t => 1 - Math.pow(1 - t, 3);
    const tick     = (now) => {
      const progress = Math.min((now - startTs) / duration, 1);
      el.textContent = `${Math.round(start + (targetROI - start) * easeOut(progress))}%`;
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  },

  setElement(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  },

  formatAED(amount) {
    if (!amount || isNaN(amount)) return 'AED --';
    if (amount >= 1000000) return `AED ${(amount / 1000000).toFixed(1)}M`;
    if (amount >= 1000)    return `AED ${Math.round(amount / 1000)}K`;
    return `AED ${Math.round(amount).toLocaleString('en-AE')}`;
  },
};

document.addEventListener('DOMContentLoaded', () => {
  SGC.ROICalc.init();
});

export default SGC.ROICalc;
