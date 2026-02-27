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

    document.addEventListener('DOMContentLoaded', async () => {
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
                item.addEventListener('click', () => {
                    fName.value = c.name;
                    fIso.value = c.iso_code;
                    fVat.value = (c.default_vat_rate * 100).toFixed(0);
                    fCur.value = c.currency_code;
                    fShip.value = c.shipping_cost_cents;
                    fFree.value = c.free_shipping_threshold_cents || '';
                    currentId = c.id;
                    $('#country-editor-title').textContent = 'Edit Country: ' + c.name;

                    const makeDefaultBtn = el('button', { class: 'btn btn-sm btn-outline-success ms-3', type: 'button' }, 'Set as Default');
                    makeDefaultBtn.onclick = async (e) => {
                        e.stopPropagation();
                        if (!await confirm(`Set ${c.name} as default country?`)) return;
                        try {
                            const headers = {};
                            const csrfToken = document.querySelector('meta[name="csrf-token"]');
                            if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;
                            const res = await fetch(`/api/admin/countries/${c.id}/set-default`, { method: 'POST', headers: headers });
                            if (res.ok) {
                                await loadCountries();
                                clearForm();
                            } else {
                                await alert('Failed to set default');
                            }
                        } catch(err) {
                            console.error(err);
                        }
                    };

                    if (!c.is_default) {
                        $('#country-editor-title').appendChild(makeDefaultBtn);
                    } else {
                        const defBadge = el('span', { class: 'badge bg-success ms-3' }, 'Default Country');
                        $('#country-editor-title').appendChild(defBadge);
                    }
                });
                countryList.appendChild(item);
            });
        }

        newBtn.addEventListener('click', clearForm);

        saveBtn.addEventListener('click', async () => {
            const payload = {
                name: fName.value.trim(),
                iso_code: fIso.value.trim(),
                default_vat_rate: parseFloat(fVat.value) / 100,
                currency_code: fCur.value.trim(),
                shipping_cost_cents: parseInt(fShip.value),
                free_shipping_threshold_cents: fFree.value ? parseInt(fFree.value) : null
            };

            if (!payload.iso_code || payload.iso_code.length !== 2) {
                await alert('ISO Code must be 2 characters');
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
                    await loadCountries();
                    await alert('Saved successfully');
                } else {
                    await alert('Error: ' + data.error);
                }
            } catch (err) {
                console.error(err);
                await alert('Network Error');
            }
        });

        delBtn.addEventListener('click', async () => {
            if (!currentId) return;
            if (!await confirm('Delete this country setting?')) return;

            try {
                const headers = {};
                const csrfToken = document.querySelector('meta[name="csrf-token"]');
                if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

                const res = await fetch(`/api/admin/countries/${currentId}`, { method: 'DELETE', headers: headers });
                if (res.ok) {
                    clearForm();
                    await loadCountries();
                } else {
                    const d = await res.json();
                    await alert(d.error || 'Failed');
                }
            } catch (err) {
                console.error(err);
            }
        });

        await loadCountries();
    });
})();
