/* SGC Website Online Booking — public calendar + form (dependency-free).
 * Fetches real available slots from /book-session/slots and confirms via
 * /book-session/confirm. No login required.
 */
(function () {
    'use strict';

    function init() {
        var app = document.getElementById('sgc-booking-app');
        if (!app) {
            return;
        }

        var calEl = document.getElementById('sgc-bk-cal');
        var monthLabel = document.getElementById('sgc-bk-month-label');
        var prevBtn = document.getElementById('sgc-bk-prev');
        var nextBtn = document.getElementById('sgc-bk-next');
        var slotsEl = document.getElementById('sgc-bk-slots');
        var slotsTitle = document.getElementById('sgc-bk-slots-title');
        var selectedEl = document.getElementById('sgc-bk-selected');
        var whenInput = document.getElementById('sgc-bk-when');
        var form = document.getElementById('sgc-bk-form');
        var submitBtn = document.getElementById('sgc-bk-submit');
        var messageEl = document.getElementById('sgc-bk-message');

        var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'];
        var DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

        var now = new Date();
        var viewYear = now.getFullYear();
        var viewMonth = now.getMonth() + 1;
        var currentSlots = {};
        var selectedDay = null;

        function post(url, payload) {
            return fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(function (res) { return res.json(); });
        }

        function pad(n) { return n < 10 ? '0' + n : '' + n; }

        function loadMonth() {
            calEl.innerHTML = '<div class="sgc-cal-loading">Loading availability…</div>';
            slotsEl.innerHTML = '';
            slotsTitle.textContent = 'Select a day';
            selectedDay = null;
            post('/book-session/slots', { year: viewYear, month: viewMonth })
                .then(function (data) {
                    if (!data || !data.success) {
                        calEl.innerHTML = '<div class="sgc-cal-loading">'
                            + ((data && data.error) || 'Unable to load availability.')
                            + '</div>';
                        return;
                    }
                    viewYear = data.year;
                    viewMonth = data.month;
                    currentSlots = data.slots || {};
                    renderCalendar();
                })
                .catch(function () {
                    calEl.innerHTML = '<div class="sgc-cal-loading">Unable to load availability.</div>';
                });
        }

        function renderCalendar() {
            monthLabel.textContent = MONTHS[viewMonth - 1] + ' ' + viewYear;

            var grid = document.createElement('div');
            grid.className = 'sgc-cal-table';

            DOW.forEach(function (d) {
                var h = document.createElement('div');
                h.className = 'sgc-cal-dow';
                h.textContent = d;
                grid.appendChild(h);
            });

            var first = new Date(viewYear, viewMonth - 1, 1);
            var lead = (first.getDay() + 6) % 7;
            var daysInMonth = new Date(viewYear, viewMonth, 0).getDate();

            for (var i = 0; i < lead; i++) {
                var blank = document.createElement('div');
                blank.className = 'sgc-cal-cell empty';
                grid.appendChild(blank);
            }

            var todayKey = pad(now.getFullYear()) + '-' + pad(now.getMonth() + 1)
                + '-' + pad(now.getDate());

            for (var day = 1; day <= daysInMonth; day++) {
                var key = viewYear + '-' + pad(viewMonth) + '-' + pad(day);
                var cell = document.createElement('button');
                cell.type = 'button';
                cell.className = 'sgc-cal-cell';
                cell.textContent = day;
                var hasSlots = currentSlots[key] && currentSlots[key].length;
                if (key === todayKey) {
                    cell.classList.add('today');
                }
                if (hasSlots) {
                    cell.classList.add('available');
                    cell.setAttribute('data-day', key);
                    cell.addEventListener('click', onDayClick);
                } else {
                    cell.classList.add('disabled');
                    cell.disabled = true;
                }
                grid.appendChild(cell);
            }

            calEl.innerHTML = '';
            calEl.appendChild(grid);
        }

        function onDayClick(ev) {
            var key = ev.currentTarget.getAttribute('data-day');
            selectedDay = key;
            Array.prototype.forEach.call(
                calEl.querySelectorAll('.sgc-cal-cell.selected'),
                function (c) { c.classList.remove('selected'); }
            );
            ev.currentTarget.classList.add('selected');
            renderSlots(key);
        }

        function renderSlots(key) {
            var times = currentSlots[key] || [];
            slotsTitle.textContent = 'Available times — ' + key;
            slotsEl.innerHTML = '';
            times.forEach(function (slot) {
                var b = document.createElement('button');
                b.type = 'button';
                b.className = 'sgc-slot';
                b.textContent = slot.label;
                b.setAttribute('data-iso', slot.iso);
                b.addEventListener('click', function () {
                    Array.prototype.forEach.call(
                        slotsEl.querySelectorAll('.sgc-slot.selected'),
                        function (s) { s.classList.remove('selected'); }
                    );
                    b.classList.add('selected');
                    whenInput.value = slot.iso;
                    selectedEl.textContent = 'Selected: ' + key + ' at ' + slot.label;
                    selectedEl.classList.add('has-value');
                    submitBtn.disabled = false;
                });
                slotsEl.appendChild(b);
            });
        }

        prevBtn.addEventListener('click', function () {
            viewMonth -= 1;
            if (viewMonth < 1) { viewMonth = 12; viewYear -= 1; }
            loadMonth();
        });
        nextBtn.addEventListener('click', function () {
            viewMonth += 1;
            if (viewMonth > 12) { viewMonth = 1; viewYear += 1; }
            loadMonth();
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            messageEl.textContent = '';
            messageEl.className = 'sgc-bk-message mt-3';

            var payload = {
                name: (document.getElementById('sgc-bk-name').value || '').trim(),
                email: (document.getElementById('sgc-bk-email').value || '').trim(),
                phone: (document.getElementById('sgc-bk-phone').value || '').trim(),
                topic: document.getElementById('sgc-bk-topic').value,
                notes: (document.getElementById('sgc-bk-notes').value || '').trim(),
                when: whenInput.value
            };
            if (!payload.when) {
                messageEl.textContent = 'Please pick a time slot first.';
                messageEl.classList.add('error');
                return;
            }
            submitBtn.disabled = true;
            submitBtn.classList.add('loading');

            post('/book-session/confirm', payload)
                .then(function (data) {
                    submitBtn.classList.remove('loading');
                    if (!data || !data.success) {
                        messageEl.textContent = (data && data.error) || 'Booking failed. Please try again.';
                        messageEl.classList.add('error');
                        submitBtn.disabled = false;
                        loadMonth();
                        return;
                    }
                    messageEl.innerHTML = data.message
                        + (data.booking_url ? ' <a href="' + data.booking_url
                            + '">Manage your booking</a>.' : '');
                    messageEl.classList.add('success');
                    form.reset();
                    whenInput.value = '';
                    selectedEl.textContent = 'No time selected yet.';
                    selectedEl.classList.remove('has-value');
                })
                .catch(function () {
                    submitBtn.classList.remove('loading');
                    submitBtn.disabled = false;
                    messageEl.textContent = 'Network error. Please try again.';
                    messageEl.classList.add('error');
                });
        });

        loadMonth();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
