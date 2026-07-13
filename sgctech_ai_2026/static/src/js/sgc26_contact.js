/** @odoo-module **/
/* SGC Tech AI 2026 — Contact form client-side validation */

(function () {
    'use strict';

    const wrap = document.getElementById('wrapwrap');
    if (!wrap || !wrap.classList.contains('sgc-v26')) return;

    function initContact() {
        const form = document.getElementById('sgc26-contact-form');
        if (!form) return;

        const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        function setError(field, msg) {
            field.classList.add('is-invalid');
            let hint = field.nextElementSibling;
            if (!hint || !hint.classList.contains('sgc26-field-hint')) {
                hint = document.createElement('span');
                hint.className = 'sgc26-field-hint sgc26-field-hint--error';
                field.parentNode.insertBefore(hint, field.nextSibling);
            }
            hint.textContent = msg;
        }

        function clearError(field) {
            field.classList.remove('is-invalid');
            const hint = field.nextElementSibling;
            if (hint && hint.classList.contains('sgc26-field-hint')) {
                hint.textContent = '';
            }
        }

        /* Inline validation on blur */
        form.querySelectorAll('[data-sgc-required]').forEach(field => {
            field.addEventListener('blur', () => {
                if (!field.value.trim()) {
                    setError(field, 'This field is required.');
                } else if (field.type === 'email' && !emailRe.test(field.value.trim())) {
                    setError(field, 'Please enter a valid email address.');
                } else {
                    clearError(field);
                }
            });
            field.addEventListener('input', () => clearError(field));
        });

        form.addEventListener('submit', function (e) {
            let valid = true;

            form.querySelectorAll('[data-sgc-required]').forEach(field => {
                if (!field.value.trim()) {
                    setError(field, 'This field is required.');
                    valid = false;
                } else if (field.type === 'email' && !emailRe.test(field.value.trim())) {
                    setError(field, 'Please enter a valid email address.');
                    valid = false;
                }
            });

            if (!valid) {
                e.preventDefault();
                const firstErr = form.querySelector('.is-invalid');
                if (firstErr) firstErr.focus();
            }
        });

        /* Pricing toggle (annual / monthly) on pricing page */
        const toggle = document.querySelector('.sgc26-pricing-toggle__track');
        if (toggle) {
            toggle.addEventListener('click', () => {
                const active = toggle.classList.toggle('active');
                const monthly = document.querySelectorAll('[data-price-monthly]');
                const annual  = document.querySelectorAll('[data-price-annual]');
                monthly.forEach(el => { el.style.display = active ? 'none' : ''; });
                annual.forEach(el  => { el.style.display = active ? '' : 'none'; });
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initContact);
    } else {
        initContact();
    }

})();
