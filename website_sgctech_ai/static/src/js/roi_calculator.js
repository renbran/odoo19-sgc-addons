(function () {
    'use strict';

    var calculateBtn = document.getElementById('roi_calculate_btn');
    if (!calculateBtn) {
        return;
    }

    var leadBtn = document.getElementById('roi_lead_btn');
    var lastPayload = null;

    function formatAed(amount) {
        return new Intl.NumberFormat('en-AE', {
            style: 'currency',
            currency: 'AED',
            maximumFractionDigits: 0
        }).format(amount || 0);
    }

    function readPainPoints() {
        var checks = document.querySelectorAll('.sgc-roi-checks input[type="checkbox"]:checked');
        return Array.prototype.map.call(checks, function (el) { return el.value; });
    }

    function post(url, payload) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(function (res) {
            return res.json();
        });
    }

    function renderResult(result) {
        document.getElementById('roi_results_empty').classList.add('d-none');
        document.getElementById('roi_results').classList.remove('d-none');
        document.getElementById('roi_lead_card').classList.remove('d-none');

        document.getElementById('roi_annual_savings').textContent = formatAed(result.annual_savings);
        document.getElementById('roi_year1_cost').textContent = formatAed(result.year_1_total_cost);
        document.getElementById('roi_year1_net').textContent = formatAed(result.year_1_net_benefit);
        document.getElementById('roi_year1_percent').textContent = result.roi_year_1_percent + '%';
        document.getElementById('roi_payback').textContent = result.payback_months + ' months';
        document.getElementById('roi_3y_benefit').textContent = formatAed(result.three_year_net_benefit);
    }

    calculateBtn.addEventListener('click', function () {
        var annualRevenue = Number(document.getElementById('roi_annual_revenue').value || 0);
        var employees = Number(document.getElementById('roi_employees').value || 0);
        var painPoints = readPainPoints();

        if (annualRevenue <= 0 || employees <= 0) {
            alert('Please enter annual revenue and employee count.');
            return;
        }

        lastPayload = {
            annual_revenue: annualRevenue,
            employees: employees,
            pain_points: painPoints
        };

        post('/tools/odoo-roi-calculator/calculate', lastPayload)
            .then(function (data) {
                if (!data.success) {
                    alert(data.error || 'Unable to calculate ROI right now.');
                    return;
                }
                renderResult(data.result || {});
            })
            .catch(function () {
                alert('Calculation request failed. Please try again.');
            });
    });

    leadBtn.addEventListener('click', function () {
        if (!lastPayload) {
            alert('Please calculate your ROI first.');
            return;
        }

        var name = (document.getElementById('roi_name').value || '').trim();
        var company = (document.getElementById('roi_company').value || '').trim();
        var email = (document.getElementById('roi_email').value || '').trim();

        if (!name || !company || !email) {
            alert('Please fill your name, company, and email.');
            return;
        }

        var payload = Object.assign({}, lastPayload, {
            name: name,
            company: company,
            email: email
        });

        post('/tools/odoo-roi-calculator/lead', payload)
            .then(function (data) {
                var msg = document.getElementById('roi_lead_message');
                if (!data.success) {
                    msg.textContent = data.error || 'Unable to save your request right now.';
                    msg.className = 'mt-3 mb-0 text-danger';
                    return;
                }
                msg.textContent = data.message || 'Report request received.';
                msg.className = 'mt-3 mb-0 text-success';
            })
            .catch(function () {
                alert('Lead request failed. Please try again.');
            });
    });
})();
