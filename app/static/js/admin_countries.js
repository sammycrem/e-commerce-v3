// static/js/admin_countries.js
(function() {
    'use strict';

    function $(sel, root = document) { return root.querySelector(sel); }
    function el(tag, attrs = {}, ...children) {
        const e = document.createElement(tag);
        for (const k in attrs) {
            if (k === 'class') e.className = attrs[k];
            else if (k === 'html') e.innerHTML = attrs[k];
            else e.setAttribute(k, attrs[k]);
        }
        children.forEach(c => {
            if (typeof c === 'string') e.appendChild(document.createTextNode(c));
            else if (c instanceof Node) e.appendChild(c);
        });
        return e;
    }

    document.addEventListener('DOMContentLoaded', () => {
        const countryList = $('#country-list');
        const newBtn = $('#btn-new-country');
        const saveBtn = $('#save-country');
        const delBtn = $('#delete-country');

        // Fields
        const fName = $('#country_name');
        const fIso = $('#country_iso');
        const fVat = $('#country_vat');
        const fCur = $('#country_currency');
        const fShip = $('#country_shipping');
        const fFree = $('#country_free_threshold');

        let currentId = null;

        if (!countryList) return;

        function clearForm() {
            fName.value = '';
            fIso.value = '';
            fVat.value = '';
            fCur.value = 'EUR';
            fShip.value = '';
            fFree.value = '';
            currentId = null;
            $('#country-editor-title').textContent = 'Create New Country';
        }

        async function loadCountries() {
            try {
                const res = await fetch('/api/admin/countries');
                const data = await res.json();
                renderList(data);
            } catch (err) {
                console.error(err);
            }
        }

        function renderList(countries) {
            countryList.innerHTML = '';
            countries.forEach(c => {
                const badge = c.is_default ? el('span', { class: 'badge bg-success ms-2' }, 'Default') : null;
                const nameContent = el('span', {}, c.name);

                const headerContent = el('div', { class: 'd-flex w-100 justify-content-between' },
                    el('h6', { class: 'mb-1' }, nameContent, badge),
                    el('small', {}, c.iso_code)
                );

                const item = el('button', { type: 'button', class: 'list-group-item list-group-item-action' },
                    headerContent,
                    el('small', {}, `VAT: ${(c.default_vat_rate * 100).toFixed(0)}%, Ship: ${(c.shipping_cost_cents/100).toFixed(2)} ${c.currency_code}`)
                );
                item.addEventListener('click', () => editCountry(c));
                countryList.appendChild(item);
            });
        }

        function editCountry(c) {
            currentId = c.id;
            fName.value = c.name;
            fIso.value = c.iso_code;
            fVat.value = c.default_vat_rate;
            fCur.value = c.currency_code;
            fShip.value = c.shipping_cost_cents;
            fFree.value = c.free_shipping_threshold_cents !== null ? c.free_shipping_threshold_cents : '';

            $('#country-editor-title').innerHTML = '';
            $('#country-editor-title').appendChild(document.createTextNode('Edit ' + c.name));

            if (!c.is_default) {
                const makeDefaultBtn = el('button', { class: 'btn btn-sm btn-outline-success ms-3' }, 'Make Default');
                makeDefaultBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (!confirm(`Set ${c.name} as default country?`)) return;
                    try {
                        const headers = {};
                        const csrfToken = document.querySelector('meta[name="csrf-token"]');
                        if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;
                        const res = await fetch(`/api/admin/countries/${c.id}/set-default`, { method: 'POST', headers: headers });
                        if (res.ok) {
                            loadCountries();
                            // clear form to reset view
                            clearForm();
                        } else {
                            alert('Failed to set default');
                        }
                    } catch(err) {
                        console.error(err);
                    }
                });
                $('#country-editor-title').appendChild(makeDefaultBtn);
            } else {
                const defBadge = el('span', { class: 'badge bg-success ms-3' }, 'Default Country');
                $('#country-editor-title').appendChild(defBadge);
            }
        }

        newBtn.addEventListener('click', clearForm);

        saveBtn.addEventListener('click', async () => {
            const payload = {
                name: fName.value.trim(),
                iso_code: fIso.value.trim(),
                default_vat_rate: parseFloat(fVat.value),
                currency_code: fCur.value.trim(),
                shipping_cost_cents: parseInt(fShip.value),
                free_shipping_threshold_cents: fFree.value ? parseInt(fFree.value) : null
            };

            // Basic validation
            if (!payload.iso_code || payload.iso_code.length !== 2) {
                alert('ISO Code must be 2 characters');
                return;
            }

            try {
                const headers = { 'Content-Type': 'application/json' };
                const csrfToken = document.querySelector('meta[name="csrf-token"]');
                if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

                const res = await fetch('/api/admin/countries', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (res.ok) {
                    loadCountries();
                    // If creating new, form remains populated but acts as edit now?
                    // Usually we clear or re-select. Let's just reload list.
                    // If update logic relies on ISO match, it works.
                    alert('Saved successfully');
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (err) {
                console.error(err);
                alert('Network Error');
            }
        });

        delBtn.addEventListener('click', async () => {
            if (!currentId) return;
            if (!confirm('Delete this country setting?')) return;

            try {
                const headers = {};
                const csrfToken = document.querySelector('meta[name="csrf-token"]');
                if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

                const res = await fetch(`/api/admin/countries/${currentId}`, { method: 'DELETE', headers: headers });
                if (res.ok) {
                    clearForm();
                    loadCountries();
                } else {
                    const d = await res.json();
                    alert(d.error || 'Failed');
                }
            } catch (err) {
                console.error(err);
            }
        });

        loadCountries();
    });
})();
