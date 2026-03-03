document.addEventListener('DOMContentLoaded', async () => {
    const shippingMethods = document.querySelectorAll('input[name="shipping_method"]');
    const subtotalEl = document.getElementById('summary-subtotal');
    const discountEl = document.getElementById('summary-discount');
    const shippingEl = document.getElementById('summary-shipping');
    const vatEl = document.getElementById('summary-vat');
    const totalEl = document.getElementById('summary-total');
    const grandTotalExclTaxEl = document.getElementById('summary-grand-total-excl-tax');

    const summaryCard = document.querySelector('.summary-card');
    const baseShipping = parseFloat(summaryCard.dataset.baseShipping);
    const vatRate = parseFloat(summaryCard.dataset.vatRate);
    const itemVat = parseFloat(summaryCard.dataset.itemVat);

    const symbol = window.appConfig.currencySymbol;
    const subtotal = parseFloat(subtotalEl.textContent.replace(symbol, ''));
    const discountText = discountEl ? discountEl.textContent.replace('-' + symbol, '').replace(symbol, '') : '0';
    const discount = parseFloat(discountText) || 0;

    shippingMethods.forEach(method => {
        method.addEventListener('change', () => {
            let newShippingCost = baseShipping;
            if (method.value === 'express') {
                newShippingCost = baseShipping * 1.25;
            } else if (method.value === 'economic') {
                newShippingCost = baseShipping * 0.9;
            }

            // Round shipping cost to 2 decimals like in backend
            newShippingCost = Math.round(newShippingCost * 100) / 100;

            const shippingVat = Math.round(newShippingCost * vatRate * 100) / 100;
            const totalVat = itemVat + shippingVat;
            const subtotalAfterDiscount = subtotal - discount;
            const newGrandTotalExclTax = subtotalAfterDiscount + newShippingCost;
            const newTotal = newGrandTotalExclTax + totalVat;

            shippingEl.textContent = `${symbol}${newShippingCost.toFixed(2)}`;
            if (grandTotalExclTaxEl) {
                grandTotalExclTaxEl.textContent = `${symbol}${newGrandTotalExclTax.toFixed(2)}`;
            }
            vatEl.textContent = `${symbol}${totalVat.toFixed(2)}`;
            totalEl.textContent = `${symbol}${newTotal.toFixed(2)}`;

            // Update UI feedback for selected card
            shippingMethods.forEach(m => {
                const card = m.closest('.card');
                if (card) {
                    if (m.checked) {
                        card.classList.add('border-primary', 'bg-light');
                    } else {
                        card.classList.remove('border-primary', 'bg-light');
                    }
                }
            });

            sessionStorage.setItem('shipping_method', method.value);
            sessionStorage.setItem('shipping_cost', newShippingCost.toFixed(2));
            sessionStorage.setItem('total', newTotal.toFixed(2));
        });
    });

    // Removed preventDefault to allow form submission
    const proceedBtn = document.getElementById('proceed-to-checkout');
    if (proceedBtn) {
        proceedBtn.addEventListener('click', (e) => {
            const shippingMethod = sessionStorage.getItem('shipping_method');
            console.log('Proceeding with Shipping Method:', shippingMethod);
        });
    }
});
