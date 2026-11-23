(function () {
    'use strict';

    var searchBtn = document.getElementById('aml_search_btn');
    if (!searchBtn) return;

    var lastResult = null;
    var emailVerified = false;
    var verifiedEmail = '';

    // ─── Loader overlay ──────────────────────────────────────────────────────────

    var loaderOverlay = document.getElementById('aml_loader_overlay');

    function showLoader(subText) {
        if (loaderOverlay) {
            var sub = document.getElementById('aml_loader_sub');
            if (sub && subText) sub.textContent = subText;
            loaderOverlay.classList.add('is-visible');
        }
    }

    function hideLoader() {
        if (loaderOverlay) loaderOverlay.classList.remove('is-visible');
    }

    // ─── Cursor sparkle ──────────────────────────────────────────────────────────

    var _lastSpark = 0;
    document.addEventListener('mousemove', function (e) {
        var now = Date.now();
        if (now - _lastSpark < 55) return;
        _lastSpark = now;
        var spark = document.createElement('span');
        spark.className = 'aml-cursor-spark';
        spark.style.left = e.clientX + 'px';
        spark.style.top = e.clientY + 'px';
        document.body.appendChild(spark);
        setTimeout(function () { if (spark.parentNode) spark.parentNode.removeChild(spark); }, 580);
    });

    // ─── helpers ────────────────────────────────────────────────────────────────

    function postJson(url, payload) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(function (r) { return r.json(); });
    }

    function setActivePill(step) {
        [1, 2, 3].forEach(function (n) {
            var pill = document.getElementById('step_pill_' + n);
            if (pill) pill.classList.toggle('is-active', n === step);
        });
    }

    function showStep(step) {
        ['aml_step1', 'aml_step2', 'aml_step3'].forEach(function (id, i) {
            var el = document.getElementById(id);
            if (el) el.classList.toggle('d-none', i + 1 !== step);
        });
        setActivePill(step);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function riskClass(risk) {
        if (risk === 'RED') return 'risk-red';
        if (risk === 'YELLOW') return 'risk-yellow';
        return 'risk-green';
    }

    function statusClass(status) {
        if (status === 'CURRENTLY_SANCTIONED') return 'status-red';
        if (status === 'PREVIOUSLY_SANCTIONED') return 'status-yellow';
        return 'status-green';
    }

    function statusLabel(status) {
        if (status === 'CURRENTLY_SANCTIONED') return 'Currently Sanctioned';
        if (status === 'PREVIOUSLY_SANCTIONED') return 'Previously Sanctioned (Historical)';
        return 'No Sanctions Record Found';
    }

    function riskCaption(risk) {
        if (risk === 'RED') return 'High-risk match pattern found. Escalate for compliance review.';
        if (risk === 'YELLOW') return 'Potential match found. Manual review is recommended.';
        return 'No likely sanctions match found in this preliminary check.';
    }

    function renderMatches(matches) {
        if (!matches || !matches.length) {
            return '<p class="mb-0 text-success fw-semibold">No likely matches found in screened watchlists.</p>';
        }
        var rows = matches.map(function (m) {
            var rowStatus = (m.record_status === 'active') ? 'Current' : 'Historical';
            var rowClass = (m.record_status === 'active') ? 'status-red' : 'status-yellow';
            return '<tr>' +
                '<td>' + (m.listed_name || '') + '</td>' +
                '<td>' + (m.list_source || '') + '</td>' +
                '<td>' + (m.listed_type || '') + '</td>' +
                '<td>' + (m.score || 0) + '%</td>' +
                '<td>' + (m.matched_via || '') + '</td>' +
                '<td><span class="result-status-pill ' + rowClass + '">' + rowStatus + '</span></td>' +
                '</tr>';
        }).join('');
        return '<div class="table-responsive"><table class="table table-sm">' +
            '<thead><tr><th>Name</th><th>Source</th><th>Type</th><th>Score</th><th>Matched Via</th><th>Record Status</th></tr></thead>' +
            '<tbody>' + rows + '</tbody></table></div>';
    }

    function setText(id, val) {
        var el = document.getElementById(id);
        if (el) el.textContent = val || '—';
    }

    function setVerifyMessage(text, ok) {
        var msg = document.getElementById('aml_verify_msg');
        if (!msg) return;
        if (!text) {
            msg.classList.add('d-none');
            msg.textContent = '';
            msg.className = 'small mt-2 mb-0 d-none';
            return;
        }
        msg.classList.remove('d-none');
        msg.textContent = text;
        msg.className = 'small mt-2 mb-0 ' + (ok ? 'text-success' : 'text-danger');
    }

    function updateVerifyPill() {
        var pill = document.getElementById('aml_verify_status');
        if (!pill) return;
        pill.textContent = emailVerified ? 'Verified' : 'Not Verified';
        pill.classList.toggle('is-verified', emailVerified);
    }

    function resetEmailVerification() {
        emailVerified = false;
        verifiedEmail = '';
        updateVerifyPill();
        setVerifyMessage('', false);
    }

    // ─── Step 1: Run screening ───────────────────────────────────────────────────

    searchBtn.addEventListener('click', function () {
        var name        = (document.getElementById('aml_name').value || '').trim();
        var dob         = (document.getElementById('aml_dob').value || '').trim();
        var gender      = (document.getElementById('aml_gender').value || '').trim();
        var nationality = (document.getElementById('aml_nationality').value || '').trim();
        var errEl       = document.getElementById('aml_search_error');

        if (!name || !dob || !gender || !nationality) {
            if (errEl) errEl.classList.remove('d-none');
            return;
        }
        if (errEl) errEl.classList.add('d-none');

        searchBtn.disabled = true;
        showLoader('Scanning ' + name + ' across international watchlists…');

        postJson('/sanction-check/search', { name: name, dob: dob, gender: gender, nationality: nationality })
            .then(function (data) {
                searchBtn.disabled = false;
                hideLoader();

                if (!data.success) {
                    if (errEl) { errEl.textContent = data.error || 'Search failed.'; errEl.classList.remove('d-none'); }
                    return;
                }

                lastResult = data;

                // Populate subject summary
                setText('ss_name', data.query);
                setText('ss_dob', data.dob);
                setText('ss_gender', data.gender);
                setText('ss_nationality', data.nationality);
                var summaryBox = document.getElementById('aml_subject_summary');
                if (summaryBox) summaryBox.classList.remove('d-none');

                // Risk badge
                var badge = document.getElementById('aml_risk_badge');
                if (badge) { badge.textContent = data.risk_level; badge.className = 'risk-badge ' + riskClass(data.risk_level); }
                setText('aml_risk_caption', riskCaption(data.risk_level));

                // Result summary row
                var summary = document.getElementById('aml_result_summary');
                if (summary) {
                    summary.classList.remove('d-none');
                    summary.innerHTML =
                        '<div class="aml-summary-grid">' +
                        '<div><span>Screened Name</span><strong>' + (data.query || '—') + '</strong></div>' +
                        '<div><span>Risk Level</span><strong>' + (data.risk_level || '—') + '</strong></div>' +
                        '<div><span>Total Matches</span><strong>' + (data.total_matches || 0) + '</strong></div>' +
                        '<div><span>Current Matches</span><strong>' + (data.current_matches || 0) + '</strong></div>' +
                        '<div><span>Historical Matches</span><strong>' + (data.historical_matches || 0) + '</strong></div>' +
                        '<div><span>Sanctions Status</span><strong><span class="result-status-pill ' + statusClass(data.risk_status || '') + '">' + statusLabel(data.risk_status || '') + '</span></strong></div>' +
                        '</div>';
                }

                var tableWrap = document.getElementById('aml_match_table_wrap');
                if (tableWrap) tableWrap.innerHTML = renderMatches(data.matches || []);

                showStep(2);
            })
            .catch(function () {
                searchBtn.disabled = false;
                hideLoader();
                if (errEl) { errEl.textContent = 'Connection error. Please try again.'; errEl.classList.remove('d-none'); }
            });
    });

    // ─── Step 2: Proceed / Re-screen ────────────────────────────────────────────

    var proceedBtn = document.getElementById('aml_proceed_btn');
    if (proceedBtn) {
        proceedBtn.addEventListener('click', function () {
            resetEmailVerification();
            showStep(3);
        });
    }

    var rescreenBtn = document.getElementById('aml_rescreen_btn');
    if (rescreenBtn) {
        rescreenBtn.addEventListener('click', function () {
            lastResult = null;
            // Clear step 1 fields
            ['aml_name', 'aml_dob', 'aml_nationality'].forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.value = '';
            });
            var genderEl = document.getElementById('aml_gender');
            if (genderEl) genderEl.value = '';
            var errEl = document.getElementById('aml_search_error');
            if (errEl) errEl.classList.add('d-none');
            resetEmailVerification();
            showStep(1);
        });
    }

    var emailInput = document.getElementById('aml_email');
    if (emailInput) {
        emailInput.addEventListener('input', function () {
            var current = (emailInput.value || '').trim().toLowerCase();
            if (emailVerified && current !== verifiedEmail) {
                resetEmailVerification();
                setVerifyMessage('Email changed. Please verify again.', false);
            }
        });
    }

    var sendOtpBtn = document.getElementById('aml_send_otp_btn');
    if (sendOtpBtn) {
        sendOtpBtn.addEventListener('click', function () {
            var email = (document.getElementById('aml_email').value || '').trim().toLowerCase();
            if (!email) {
                setVerifyMessage('Enter your email first.', false);
                return;
            }

            sendOtpBtn.disabled = true;
            postJson('/sanction-check/send-otp', { email: email }).then(function (data) {
                sendOtpBtn.disabled = false;
                if (!data.success) {
                    setVerifyMessage(data.error || 'Unable to send verification code.', false);
                    return;
                }
                resetEmailVerification();
                setVerifyMessage(data.message || 'Verification code sent.', true);
            }).catch(function () {
                sendOtpBtn.disabled = false;
                setVerifyMessage('Connection error while sending verification code.', false);
            });
        });
    }

    var verifyOtpBtn = document.getElementById('aml_verify_otp_btn');
    if (verifyOtpBtn) {
        verifyOtpBtn.addEventListener('click', function () {
            var email = (document.getElementById('aml_email').value || '').trim().toLowerCase();
            var otp = (document.getElementById('aml_otp_code').value || '').trim();
            if (!email || !otp) {
                setVerifyMessage('Email and verification code are required.', false);
                return;
            }

            verifyOtpBtn.disabled = true;
            postJson('/sanction-check/verify-otp', { email: email, otp: otp }).then(function (data) {
                verifyOtpBtn.disabled = false;
                if (!data.success) {
                    resetEmailVerification();
                    setVerifyMessage(data.error || 'Invalid verification code.', false);
                    return;
                }
                emailVerified = true;
                verifiedEmail = email;
                updateVerifyPill();
                setVerifyMessage(data.message || 'Email verified successfully.', true);
            }).catch(function () {
                verifyOtpBtn.disabled = false;
                setVerifyMessage('Connection error while verifying code.', false);
            });
        });
    }

    // ─── Step 3: Generate certificate ───────────────────────────────────────────

    var certificateBtn = document.getElementById('aml_certificate_btn');
    if (certificateBtn) {
        certificateBtn.addEventListener('click', function () {
            if (!lastResult) { showStep(1); return; }

            var personName  = (document.getElementById('aml_person_name').value || '').trim();
            var companyName = (document.getElementById('aml_company_name').value || '').trim();
            var email       = (document.getElementById('aml_email').value || '').trim();
            var mobile      = (document.getElementById('aml_mobile').value || '').trim();
            var errEl       = document.getElementById('aml_form_error');

            if (!personName || !companyName || !email || !mobile) {
                if (errEl) errEl.classList.remove('d-none');
                return;
            }

            if (!emailVerified || email !== verifiedEmail) {
                if (errEl) {
                    errEl.textContent = 'Please verify your email with OTP before generating the certificate.';
                    errEl.classList.remove('d-none');
                }
                return;
            }

            if (errEl) errEl.classList.add('d-none');

            certificateBtn.disabled = true;
            showLoader('Generating your compliance certificate…');

            postJson('/sanction-check/signup', {
                person_name:    personName,
                company_name:   companyName,
                email:          email,
                mobile:         mobile,
                screened_name:  lastResult.query,
                dob:            lastResult.dob,
                gender:         lastResult.gender,
                nationality:    lastResult.nationality,
                risk_level:     lastResult.risk_level,
                risk_status:    lastResult.risk_status,
                total_matches:  lastResult.total_matches,
                current_matches: lastResult.current_matches,
                historical_matches: lastResult.historical_matches
            }).then(function (data) {
                certificateBtn.disabled = false;
                hideLoader();

                if (!data.success) {
                    if (errEl) { errEl.textContent = data.error || 'Certificate request failed.'; errEl.classList.remove('d-none'); }
                    return;
                }

                resetEmailVerification();

                var w = window.open('', '_blank');
                if (w) {
                    w.document.open();
                    w.document.write(data.certificate_html || '<h1>Certificate generated</h1>');
                    w.document.close();
                }
            }).catch(function () {
                certificateBtn.disabled = false;
                hideLoader();
                if (errEl) { errEl.textContent = 'Connection error. Please try again.'; errEl.classList.remove('d-none'); }
            });
        });
    }

    updateVerifyPill();
})();
