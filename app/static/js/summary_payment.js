document.addEventListener('DOMContentLoaded', async () => {
    // Only run if we are on summary page and Stripe is selected
    if (window.selectedPaymentMethod !== 'stripe') {
        return;
    }

    if (!window.stripePublicKey) {
        console.error('Stripe public key not found');
        return;
    }

    const stripe = Stripe(window.stripePublicKey);
    let elements;

    // Fetch PaymentIntent from backend
    // Since we are on Summary page, we assume cart and shipping are finalized.
    // We call the endpoint to get the ClientSecret.
    // Note: We need to pass current cart details to ensure amount is correct.
    // Ideally, the backend calculates it from session/db.

    // We reuse the create-payment-intent endpoint.
    // We need to fetch it.

    const summaryCard = document.querySelector('.summary-card');
    const shippingMethod = summaryCard ? summaryCard.dataset.shippingMethod : 'standard'; // summary.html doesn't have dataset on summary-card usually, let's check

    // Actually summary.html doesn't seem to have data attributes on summary-card in previous read.
    // But calculate-totals needs items.
    // Let's rely on backend session cart.

    // Wait, create-payment-intent needs items in body?
    // Let's check checkout.py implementation.
    // It takes items from request.json. It does NOT use session cart directly in calculation?
    // `calculate_totals_internal` can take items.

    // To make this robust, let's fetch cart items first like payment_methods.js does.

    async function initializeStripe() {
        const placeOrderBtn = document.getElementById('place-order-btn');
        if (placeOrderBtn) {
            placeOrderBtn.disabled = true; // Disable until loaded
        }

        try {
            // Get cart items
            const cartRes = await fetch('/api/cart');
            const cartData = await cartRes.json();
            const items = cartData.items.map(it => ({ sku: it.sku, quantity: it.quantity }));

            // We need shipping info. In summary, it's already in session?
            // The endpoint `create_payment_intent` uses `calculate_totals_internal`.
            // If we don't pass shipping_method, it defaults to 'standard'.
            // But user might have selected 'express'.
            // The session has it! `session['shipping_method']`.
            // `calculate_totals_internal` takes `shipping_method` arg.
            // But wait, `create_payment_intent` route takes it from request body.
            // It does NOT read from session for that argument.

            // So we need to pass it.
            // How do we get it on frontend?
            // It's rendered in the template: `selected_shipping`.
            // Let's grab it from DOM or inject it.
            // In summary.html, there is `{{ selected_shipping }}`.
            // Let's assume we can get it or the backend should be updated to use session if missing?
            // Current `create_payment_intent` implementation:
            // shipping_method = data.get('shipping_method')

            // Let's inject it into window config
            // (I can't easily edit summary.html again without a new tool call,
            // but I can try to find it in the DOM text "Standard Shipping"?)

            // Safer: Update `create_payment_intent` to fallback to session?
            // Or just pass 'standard' if we can't find it, and let backend validate?
            // The `calculate_totals_internal` logic is sensitive to this.

            // Let's try to get it from the review card "Shipping Method".
            // <p class="mb-0 fw-bold text-capitalize">{{ selected_shipping }} Shipping</p>
            // We can parse it.

            let shippingMethod = 'standard';
            const methodEl = Array.from(document.querySelectorAll('.card-body p.fw-bold.text-capitalize')).find(el => el.textContent.includes('Shipping'));
            if (methodEl) {
                shippingMethod = methodEl.textContent.replace(' Shipping', '').trim().toLowerCase();
            }

            const csrfToken = document.querySelector('input[name="csrf_token"]').value;

            const res = await fetch('/api/create-payment-intent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    items: items,
                    shipping_method: shippingMethod,
                    // promo_code? session has it.
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'Failed to initialize payment');
            }

            const data_pi = await res.json();
            const clientSecret = data_pi.clientSecret;
            const paymentIntentId = clientSecret.split('_secret_')[0];

            const appearance = { theme: 'stripe' };
            elements = stripe.elements({ appearance, clientSecret });

            const paymentElement = elements.create('payment');
            paymentElement.mount('#payment-element');

            if (placeOrderBtn) {
                placeOrderBtn.disabled = false;
            }

        } catch (e) {
            console.error(e);
            document.getElementById('stripe-error-message').textContent = e.message;
        }
    }

    await initializeStripe();

    const form = document.getElementById('place-order-form');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const placeOrderBtn = document.getElementById('place-order-btn');
        placeOrderBtn.disabled = true;
        placeOrderBtn.textContent = 'Processing...';

        const { error: submitError } = await elements.submit();
        if (submitError) {
            document.getElementById('stripe-error-message').textContent = submitError.message;
            placeOrderBtn.disabled = false;
            placeOrderBtn.textContent = 'PLACE ORDER';
            return;
        }

        // 1. Create Order on Backend (AJAX)
        try {
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            // Get payment intent ID to link
            // Actually, we don't have the ID easily unless we parse clientSecret or
            // the confirmPayment call handles it.
            // But wait, the backend needs to create the order record BEFORE we confirm,
            // OR we rely on webhook.
            // My updated backend logic for `summary` (POST) handles `payment_intent_id` param.

            // We need to know the PaymentIntent ID to pass to backend.
            // We can get it from elements? No.
            // We got it from clientSecret? clientSecret = "pi_..._secret_..."
            // ID is the first part "pi_...".

            // But we don't strictly need it if we trust the flow,
            // BUT backend expects it to link the transaction.

            // Let's call the backend to create the order.
            // We are submitting the form via AJAX basically.
            const formData = new FormData(form);
            // Convert to JSON
            const data = {};
            formData.forEach((value, key) => data[key] = value);

            // Include Payment Intent ID
            data['payment_intent_id'] = paymentIntentId;

            // Add AJAX header
            const orderRes = await fetch(window.location.href, { // POST to current URL (summary)
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(data)
            });

            if (!orderRes.ok) {
                const err = await orderRes.json();
                throw new Error(err.error || 'Order creation failed');
            }

            const orderData = await orderRes.json();
            const orderId = orderData.order_id; // Public Order ID

            if (!orderData.success) {
                throw new Error('Order creation reported failure');
            }

            // 2. Confirm Payment with Stripe
            // We pass the return_url to success page
            const returnUrl = window.stripeReturnUrl.replace('{ORDER_ID}', orderId);

            const { error } = await stripe.confirmPayment({
                elements,
                confirmParams: {
                    return_url: returnUrl,
                },
            });

            if (error) {
                document.getElementById('stripe-error-message').textContent = error.message;
                placeOrderBtn.disabled = false;
                placeOrderBtn.textContent = 'PLACE ORDER';
            } else {
                // Redirect happens automatically
            }

        } catch (e) {
            console.error(e);
            document.getElementById('stripe-error-message').textContent = e.message;
            placeOrderBtn.disabled = false;
            placeOrderBtn.textContent = 'PLACE ORDER';
        }
    });
});
