/** @odoo-module **/

import { session } from "@web/session";

const SPINNER_HTML = '<div class="text-muted small p-2">Loading journal entries…</div>';

function _fmt(n) {
    const v = +n;
    if (!isFinite(v)) return "";
    return v.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

/**
 * Build the inline <tr> that gets injected right under the clicked
 * account row. Shows opening balance, every period move line, and the
 * closing balance; layout mirrors a General Ledger so it's familiar.
 */
function renderMoveLinesHtml(accountName, data) {
    if (!data || data.error) {
        return (
            '<tr class="sgc-drilldown-row">' +
                '<td colspan="99" class="p-3 sgc-drilldown-cell">' +
                    `<div class="alert alert-danger small p-2 mb-0">` +
                        `${(data && data.error) || "Could not load journal entries"}` +
                    "</div>" +
                "</td>" +
            "</tr>"
        );
    }
    const lines = data.move_lines || [];
    if (lines.length === 0) {
        return (
            '<tr class="sgc-drilldown-row">' +
                '<td colspan="99" class="p-3 sgc-drilldown-cell">' +
                    `<div class="text-muted small">No journal entries in this period.</div>` +
                "</td>" +
            "</tr>"
        );
    }
    const openingRow = `
        <tr class="table-light fw-bold">
            <td colspan="5" class="text-start sgc-drilldown-summary">Opening balance</td>
            <td class="text-end sgc-drilldown-num">${_fmt(data.opening_debit)}</td>
            <td class="text-end sgc-drilldown-num">${_fmt(data.opening_credit)}</td>
            <td class="text-end sgc-drilldown-num">${_fmt(data.opening_balance)}</td>
        </tr>`;
    const rowsHtml = lines.map((m, i) => `
        <tr>
            <td class="text-muted">${i + 1}</td>
            <td>${m.date || ""}</td>
            <td>${m.ref || ""}</td>
            <td>${m.partner_name || ""}</td>
            <td class="text-start">${m.label || ""}</td>
            <td class="text-end sgc-drilldown-num">${_fmt(m.debit)}</td>
            <td class="text-end sgc-drilldown-num">${_fmt(m.credit)}</td>
            <td class="text-end sgc-drilldown-num">${_fmt(m.balance)}</td>
        </tr>
    `).join("");
    return (
        '<tr class="sgc-drilldown-row sgc-drilldown-open">' +
            '<td colspan="99" class="p-3 sgc-drilldown-cell">' +
                '<div class="d-flex flex-wrap justify-content-between align-items-center mb-2">' +
                    `<strong>${accountName} — Journal entries (${lines.length})</strong>` +
                    `<small class="text-muted">` +
                        `Opening: ${_fmt(data.opening_balance)} • ` +
                        `Period: ${_fmt(data.period_balance)} • ` +
                        `Closing: ${_fmt(data.final_balance)}` +
                    "</small>" +
                "</div>" +
                '<table class="table table-sm table-bordered sgc-drilldown-table mb-0">' +
                    "<thead><tr>" +
                        "<th>#</th><th>Date</th><th>Ref</th>" +
                        "<th>Partner</th><th>Label</th>" +
                        '<th class="text-end">Debit</th>' +
                        '<th class="text-end">Credit</th>' +
                        '<th class="text-end">Balance</th>' +
                    "</tr></thead>" +
                    "<tbody>" + openingRow + rowsHtml + "</tbody>" +
                "</table>" +
            "</td>" +
        "</tr>"
    );
}

/**
 * Attach a click delegate on the report container so account rows can
 * be expanded to view move lines (drill-down). Idempotent: subsequent
 * calls on the same element are no-ops thanks to the dataset flag.
 *
 * Re-rendered <tr data-account-id> elements (when the wizard re-runs)
 * are picked up automatically because the delegate lives on the parent
 * container, which never gets re-rendered itself - only its innerHTML.
 */
export function attachDrilldownHandler(containerEl, wizardId) {
    if (!containerEl || containerEl.dataset.sgcDrilldownAttached === "1") {
        return;
    }
    containerEl.dataset.sgcDrilldownAttached = "1";
    containerEl.addEventListener("click", async (ev) => {
        const row = ev.target.closest("tr[data-account-id]");
        if (!row) return;
        // Ignore clicks that land inside an already-expanded drill row.
        if (row.closest("tr.sgc-drilldown-row")) return;
        ev.preventDefault();

        const acctId = row.dataset.accountId;
        // Account name comes from the row's Account-Name cell (col 2).
        const nameCell = row.querySelector("td.sgc-col-text:not(:first-child)");
        const accountName =
            (nameCell && nameCell.textContent.trim()) ||
            `Account #${acctId}`;

        // Toggle: if a drill row already follows this account row, remove it.
        const existing = row.nextElementSibling;
        if (existing && existing.classList.contains("sgc-drilldown-row")) {
            existing.remove();
            row.classList.remove("sgc-row-expanded");
            return;
        }

        row.classList.add("sgc-row-expanded");
        const placeholder = document.createElement("tr");
        placeholder.className = "sgc-drilldown-row";
        placeholder.innerHTML = `<td colspan="99">${SPINNER_HTML}</td>`;
        row.after(placeholder);

        try {
            const resp = await fetch(
                `/sgc/dfr/drilldown/${wizardId}/${acctId}`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": session.csrf_token,
                    },
                    body: JSON.stringify({}),
                }
            );
            const data = await resp.json();
            placeholder.outerHTML = renderMoveLinesHtml(accountName, data);
        } catch (err) {
            placeholder.outerHTML =
                `<tr class="sgc-drilldown-row"><td colspan="99">` +
                `<div class="alert alert-danger small p-2 m-2">` +
                `Network error: ${err && err.message ? err.message : err}` +
                `</div></td></tr>`;
        }
    });
}
