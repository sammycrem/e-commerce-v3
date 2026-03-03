(async function() {
    'use strict';

    function $(sel, root = document) { return root.querySelector(sel); }

    document.addEventListener('DOMContentLoaded', async () => {
        const btnGenerate = $('#btn-generate-report');
        const btnExport = $('#btn-export-report');
        const reportType = $('#report-type');
        const reportStart = $('#report-start');
        const reportEnd = $('#report-end');
        const reportResults = $('#report-results');

        if (!btnGenerate) return;

        // Set default dates (Current Month)
        const now = new Date();
        const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
        const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
        // Correctly format to YYYY-MM-DD using local time part
        const formatDate = (d) => {
            const year = d.getFullYear();
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        };

        reportStart.value = formatDate(firstDay);
        reportEnd.value = formatDate(lastDay);

        btnGenerate.addEventListener('click', loadReport);
        btnExport.addEventListener('click', exportReport);

        async function loadReport() {
            const type = reportType.value;
            const start = reportStart.value; // yyyy-mm-dd
            const end = reportEnd.value;

            // Build URL
            const url = new URL('/api/admin/reports', window.location.origin);
            url.searchParams.append('type', type);
            if (start) url.searchParams.append('start_date', start);
            if (end) url.searchParams.append('end_date', end);

            reportResults.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div><p>Loading report...</p></div>';

            try {
                const res = await fetch(url);
                if (!res.ok) throw new Error('Failed to load report');
                const data = await res.json();
                renderTable(type, data);
            } catch (err) {
                console.error(err);
                reportResults.innerHTML = `<div class="alert alert-danger">Error: ${err.message}</div>`;
            }
        }

        async function exportReport() {
            const type = reportType.value;
            const start = reportStart.value;
            const end = reportEnd.value;

            const url = new URL('/api/admin/reports', window.location.origin);
            url.searchParams.append('type', type);
            if (start) url.searchParams.append('start_date', start);
            if (end) url.searchParams.append('end_date', end);
            url.searchParams.append('format', 'csv');

            window.location.href = url.toString();
        }

        async function renderTable(type, data) {
            if (!data || data.length === 0) {
                reportResults.innerHTML = '<p class="text-center py-5">No data found for the selected period.</p>';
                return;
            }

            let headers = [];
            let rows = [];

            const currencySymbol = window.appConfig?.currencySymbol || '€';

            function formatMoney(cents) {
                return currencySymbol + ' ' + (cents / 100).toFixed(2);
            }

            function escapeHtml(text) {
                if (text == null) return '';
                return String(text)
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;")
                    .replace(/'/g, "&#039;");
            }

            if (type === 'summary') {
                headers = ['Orders', 'Gross Sales', 'Discounts', 'Shipping', 'VAT', 'Returns', 'Net Sales', 'Total Collected'];
                // data is array of 1 object
                const row = data[0];
                rows.push([
                    row.orders_count,
                    formatMoney(row.gross_sales),
                    formatMoney(row.discounts),
                    formatMoney(row.shipping),
                    formatMoney(row.vat),
                    formatMoney(row.returns),
                    formatMoney(row.net_sales),
                    formatMoney(row.total_collected)
                ]);
            } else if (type === 'daily') {
                headers = ['Date', 'Orders', 'Gross Sales', 'Discounts', 'Net Sales', 'Shipping', 'VAT', 'Total'];
                data.forEach(r => {
                    rows.push([
                        r.date,
                        r.orders_count,
                        formatMoney(r.gross_sales),
                        formatMoney(r.discounts),
                        formatMoney(r.net_sales),
                        formatMoney(r.shipping),
                        formatMoney(r.vat),
                        formatMoney(r.total)
                    ]);
                });
            } else if (type === 'items') {
                headers = ['SKU', 'Name', 'Sold', 'Revenue'];
                data.forEach(r => {
                    rows.push([
                        r.sku,
                        r.name,
                        r.sold,
                        formatMoney(r.revenue)
                    ]);
                });
            }

            let html = '<table class="table table-striped table-hover sortable"><thead><tr>';
            headers.forEach((h, idx) => {
                html += `<th data-col="${idx}" style="cursor:pointer;">${h} <i class="fas fa-sort text-muted small"></i></th>`;
            });
            html += '</tr></thead><tbody>';
            rows.forEach(row => {
                html += '<tr>';
                row.forEach(cell => {
                    html += `<td>${escapeHtml(cell)}</td>`;
                });
                html += '</tr>';
            });
            html += '</tbody></table>';

            reportResults.innerHTML = html;
            makeSortable(reportResults.querySelector('table'));
        }

        async function makeSortable(table) {
            const headers = table.querySelectorAll('th');
            const tbody = table.querySelector('tbody');

            headers.forEach(th => {
                th.addEventListener('click', () => {
                    const colIdx = parseInt(th.dataset.col);
                    const rows = Array.from(tbody.querySelectorAll('tr'));
                    const isAsc = th.dataset.order === 'asc';

                    // Toggle order
                    th.dataset.order = isAsc ? 'desc' : 'asc';

                    // Reset icons
                    headers.forEach(h => h.querySelector('i').className = 'fas fa-sort text-muted small');
                    th.querySelector('i').className = `fas fa-sort-${isAsc ? 'down' : 'up'}`;

                    rows.sort((a, b) => {
                        const cellA = a.children[colIdx].innerText;
                        const cellB = b.children[colIdx].innerText;

                        // Check if looks like a number (and not a date like YYYY-MM-DD which has -)
                        // Simple heuristic: if it parses as float and doesn't contain '-', treat as number.
                        // Or cleaner: check header name? No, generic is better.
                        const isDate = cellA.match(/^\d{4}-\d{2}-\d{2}$/);
                        if (isDate) {
                             return isAsc ? cellA.localeCompare(cellB) : cellB.localeCompare(cellA);
                        }

                        const numA = parseFloat(cellA.replace(/[^0-9.-]+/g,""));
                        const numB = parseFloat(cellB.replace(/[^0-9.-]+/g,""));

                        if (!isNaN(numA) && !isNaN(numB)) {
                            return isAsc ? numA - numB : numB - numA;
                        }

                        return isAsc ? cellA.localeCompare(cellB) : cellB.localeCompare(cellA);
                    });

                    rows.forEach(r => tbody.appendChild(r));
                });
            });
        }
    });
})();
