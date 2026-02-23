document.addEventListener('DOMContentLoaded', () => {
    const applyPromoBtn = document.getElementById('apply-promo-btn');
    const promoInput = document.getElementById('promo-code');
    const promoFeedback = document.getElementById('promo-feedback');
    const summaryCard = document.querySelector('.summary-card');

    const subtotalEl = document.getElementById('summary-subtotal');
    const discountEl = document.getElementById('summary-discount');
    const discountRow = document.getElementById('summary-discount-row');
    const shippingEl = document.getElementById('summary-shipping');
    const grandTotalExclTaxEl = document.getElementById('summary-grand-total-excl-tax');
    const vatEl = document.getElementById('summary-vat');
    const totalEl = document.getElementById('summary-total');

    function formatPrice(cents) {
        const symbol = (window.appConfig && window.appConfig.currencySymbol) || '€';
        return `${symbol}${(cents / 100).toFixed(2)}`;
    }

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    async function refreshSummary(promoCode = '') {
        try {
            // Get cart items first
            const cartRes = await fetch('/api/cart');
            const cartData = await cartRes.json();
            const items = cartData.items.map(it => ({ sku: it.sku, quantity: it.quantity }));

            const countryIso = summaryCard.dataset.countryIso;
            const shippingMethod = summaryCard.dataset.shippingMethod;

            const res = await fetch('/api/calculate-totals', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    items: items,
                    shipping_country_iso: countryIso,
                    shipping_method: shippingMethod,
                    promo_code: promoCode || null
                })
            });

            if (!res.ok) throw new Error('Failed to calculate totals');
            const data = await res.json();

            // Update UI
            if (subtotalEl) {
                subtotalEl.textContent = formatPrice(data.subtotal_cents);
                subtotalEl.dataset.subtotalCents = data.subtotal_cents;
            }

            if (data.discount_cents > 0) {
                const symbol = (window.appConfig && window.appConfig.currencySymbol) || '€';
                if (discountEl) discountEl.textContent = `-${symbol}${(data.discount_cents / 100).toFixed(2)}`;
                if (discountRow) {
                    discountRow.style.display = 'flex';
                    discountRow.classList.remove('d-none');
                    discountRow.style.setProperty('display', 'flex', 'important');
                }
            } else {
                if (discountRow) {
                    discountRow.style.display = 'none';
                    discountRow.style.setProperty('display', 'none', 'important');
                }
            }

            if (shippingEl) shippingEl.textContent = formatPrice(data.shipping_cost_cents);

            const grandTotalExclTax = data.subtotal_after_discount_cents + data.shipping_cost_cents;
            if (grandTotalExclTaxEl) grandTotalExclTaxEl.textContent = formatPrice(grandTotalExclTax);

            if (vatEl) vatEl.textContent = formatPrice(data.vat_cents);
            if (totalEl) totalEl.textContent = formatPrice(data.total_cents);

            return data;
        } catch (err) {
            console.error('Error refreshing summary:', err);
            if (promoFeedback) {
                promoFeedback.textContent = 'Error updating summary';
                promoFeedback.className = 'small mt-1 mb-0 text-danger';
            }
        }
    }

    if (applyPromoBtn) {
        applyPromoBtn.addEventListener('click', async () => {
            const code = promoInput.value.trim();
            if (!code) {
                promoFeedback.textContent = 'Please enter a promo code';
                promoFeedback.className = 'small mt-1 mb-0 text-danger';
                return;
            }

            try {
                // We need subtotal for apply-promo API
                const subtotal = parseInt(subtotalEl.dataset.subtotalCents);

                const res = await fetch('/api/apply-promo', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        code: code,
                        cart_subtotal_cents: subtotal
                    })
                });

                const data = await res.json();
                if (res.ok) {
                    promoFeedback.textContent = `Promo code '${code}' applied successfully!`;
                    promoFeedback.className = 'small mt-1 mb-0 text-success';
                    await refreshSummary(code);
                } else {
                    promoFeedback.textContent = data.error || 'Invalid promo code';
                    promoFeedback.className = 'small mt-1 mb-0 text-danger';
                    await refreshSummary(''); // Clear discount if invalid
                }
            } catch (err) {
                console.error('Error applying promo:', err);
                promoFeedback.textContent = 'Error applying promo code';
                promoFeedback.className = 'small mt-1 mb-0 text-danger';
            }
        });
    }
});
