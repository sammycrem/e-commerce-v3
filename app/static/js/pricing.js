// static/js/pricing.js
(async function() {
    'use strict';

    document.addEventListener('DOMContentLoaded', async () => {
        const vatToggle = document.getElementById('vat-toggle');
        const shipToContainer = document.getElementById('ship-to-container');
        const shipToSelect = document.getElementById('ship-to-select');

        let countries = [];
        let countryMap = {};

        // 1. Initialize State from LocalStorage
        const storedShowVat = localStorage.getItem('show_vat') === 'true';
        const storedCountryId = localStorage.getItem('selected_country_id');

        if (vatToggle) vatToggle.checked = storedShowVat;

        // 2. Event Listeners
        if (vatToggle) {
            vatToggle.addEventListener ('change', () => {
                const isChecked = vatToggle.checked;
                localStorage.setItem('show_vat', isChecked);
                handleVatVisibility(isChecked);
                updatePrices();
            });
        }

        if (shipToSelect) {
            shipToSelect.addEventListener ('change', () => {
                const val = shipToSelect.value;
                if (val) localStorage.setItem('selected_country_id', val);
                else localStorage.removeItem('selected_country_id');
                updatePrices();
            });
        }

        // 3. Logic
        async function init() {
            // Determine if we need to show the Ship To selector
            // Only if Mode is SHIPPING_ADDRESS
            const mode = window.appConfig.vatMode || 'SHIPPING_ADDRESS';

            if (mode === 'SHIPPING_ADDRESS') {
                // Fetch countries for the dropdown
                await loadCountries();
                if (shipToContainer) {
                    shipToContainer.classList.remove('d-none');
                    // Handle visibility logic: toggle controls visibility of ship-to?
                    // Proposal says "ensure accurate VAT display when in Incl. VAT mode... a Ship To dropdown will be added".
                    // Usually always visible if it affects pricing, or only when Show VAT is ON.
                    // Let's show only when Show VAT is ON to reduce clutter? Or always?
                    // "To ensure accurate VAT display when in Incl. VAT mode... a Ship To dropdown will be added"
                    handleVatVisibility(vatToggle ? vatToggle.checked : storedShowVat);
                }
            } else {
                if (shipToContainer) shipToContainer.classList.add('d-none');
            }

            // Initial Price Update
            updatePrices();
        }

        async function handleVatVisibility(showVat) {
            const mode = window.appConfig.vatMode || 'SHIPPING_ADDRESS';
            if (mode === 'SHIPPING_ADDRESS' && shipToContainer) {
                // Show Ship To only if we care about VAT?
                // Or maybe always allow user to select ship to context?
                // Let's hide it if VAT excluded (default B2B view) to keep header clean, show if B2C.
                if (showVat) shipToContainer.classList.remove('d-none');
                else shipToContainer.classList.add('d-none');
            }
        }

        async function loadCountries() {
            try {
                const res = await fetch('/api/countries/public');
                if (res.ok) {
                    countries = await res.json();
                    countryMap = {};
                    shipToSelect.innerHTML = '<option value="" class="text-dark">Ship to...</option>';
                    countries.forEach(c => {
                        countryMap[c.id] = c;
                        const opt = document.createElement('option');
                        opt.value = c.id;
                        opt.textContent = c.name; // + ` (${(c.vat_rate*100).toFixed(0)}%)`; optional hint
                        opt.className = "text-dark";
                        if (String(c.id) === String(storedCountryId)) opt.selected = true;
                        shipToSelect.appendChild(opt);
                    });
                }
            } catch (err) {
                console.error("Failed to load countries", err);
            }
        }

        async function getEffectiveVatRate() {
            const mode = window.appConfig.vatMode || 'SHIPPING_ADDRESS';

            if (mode === 'DEFAULT_COUNTRY') {
                return window.appConfig.defaultVatRate || 0.0;
            } else {
                // SHIPPING_ADDRESS
                const selectedId = shipToSelect ? shipToSelect.value : storedCountryId;
                if (selectedId && countryMap[selectedId]) {
                    return countryMap[selectedId].vat_rate;
                }
                // Fallback to default if no country selected
                return window.appConfig.defaultVatRate || 0.0;
            }
        }

        async function updatePrices() {
            const showVat = vatToggle ? vatToggle.checked : false;
            const rate = getEffectiveVatRate();
            const symbol = window.appConfig.currencySymbol || '€';

            document.querySelectorAll('.product-price').forEach(el => {
                const baseCents = parseInt(el.dataset.basePriceCents || 0);
                if (!baseCents && baseCents !== 0) return;

                let finalCents = baseCents;
                let suffix = "";

                if (showVat) {
                    // Calc incl VAT
                    // Rate is decimal like 0.19
                    finalCents = Math.round(baseCents * (1 + rate));
                    suffix = " <small class='text-muted fs-6 fw-normal'>(incl. VAT)</small>";
                } else {
                    suffix = " <small class='text-muted fs-6 fw-normal'>(excl. VAT)</small>";
                }

                const fmt = (finalCents / 100).toFixed(2);
                el.innerHTML = `${symbol}${fmt}${suffix}`;
            });
        }

        // Export updatePrices
        window.updateAllPrices = updatePrices;

        // Export for other scripts if needed (e.g., product page variant updates)
        window.calculateDisplayPrice = async function(baseCents) {
             const showVat = vatToggle ? vatToggle.checked : false;
             const rate = getEffectiveVatRate();
             const symbol = window.appConfig.currencySymbol || '€';

             let finalCents = baseCents;
             let suffix = "";
             if (showVat) {
                 finalCents = Math.round(baseCents * (1 + rate));
                 suffix = " (incl. VAT)";
             } else {
                 suffix = " (excl. VAT)";
             }
             return {
                 cents: finalCents,
                 formatted: `${symbol}${(finalCents/100).toFixed(2)}${suffix}`,
                 rawFormatted: `${symbol}${(finalCents/100).toFixed(2)}`
             };
        };

        // Listen for custom event from product.js if variants change?
        // product.js usually updates the #product-price element directly.
        // We should wrap product.js logic or have it call us.
        // For now, init() handles static prices. product.js needs update.

        init();
    });
})();
