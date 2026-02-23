// static/js/cart.js
// Full cart script: renders session cart, lets user update quantities/remove items,
// applies promo codes, shows VAT breakdown and performs checkout.

document.addEventListener('DOMContentLoaded', () => {
  // Elements from the new cart.html structure
  const cartContainer = document.getElementById('cart-container');
  const cartSummary = document.getElementById('cart-summary');
  const subtotalEl = document.getElementById('summary-subtotal');
  const totalEl = document.getElementById('summary-total');
  const totalLabel = document.getElementById('total-label');
  const checkoutBtn = document.getElementById('checkout-btn');
  const checkoutFeedback = document.getElementById('checkout-feedback');
  const continueShoppingBtn = document.querySelector('.continue-shopping');
  const clearCartBtn = document.querySelector('.clear-cart');
  const vatToggle = document.getElementById('vat-toggle');

  // Local state
  let cartData = { items: [], subtotal_cents: 0 };
  let lastCalc = null; // keep last calculate-totals response

  // Format cents -> CurrencyX.YY
  function formatPrice(cents) {
    if (typeof cents !== 'number') cents = Number(cents || 0);
    // Use last calculated currency symbol if available, otherwise default
    const symbol = (lastCalc && lastCalc.currency_symbol) || (window.appConfig && window.appConfig.currencySymbol) || '€';
    return `${symbol}${(cents / 100).toFixed(2)}`;
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  function getIconUrl(url) {
    if (!url || !url.includes('/static/')) return url;
    const dotIdx = url.lastIndexOf('.');
    const base = dotIdx !== -1 ? url.substring(0, dotIdx) : url;
    if (base.endsWith('_icon')) return url;
    return base + '_icon.webp';
  }

  function updateVatLabel() {
    if (!totalLabel) return;
    // Check toggle state or fallback to local storage
    let showVat = false;
    if (vatToggle) {
        showVat = vatToggle.checked;
    } else {
        showVat = localStorage.getItem('show_vat') === 'true';
    }

    if (showVat) {
        totalLabel.textContent = 'Total Due Incl. Tax';
    } else {
        totalLabel.textContent = 'Total Due Excl. Tax';
    }
  }

  // Fetch session cart from backend and render
  async function refreshCart() {
    try {
      const res = await fetch('/api/cart', { credentials: 'same-origin' });
      if (!res.ok) throw new Error('Failed to load cart');
      const data = await res.json();
      cartData = data;
      renderCart(data);
      await recalcTotals();

      // Update label and prices after render
      updateVatLabel();
      if (window.updateAllPrices) window.updateAllPrices();

    } catch (err) {
      console.error('refreshCart error:', err);
      cartContainer.innerHTML = '<tr><td colspan="5">Unable to load cart. Try reloading the page.</td></tr>';
    }
  }

  function renderCart(data) {
    cartContainer.innerHTML = ''; // Clear existing content

    if (!data || !Array.isArray(data.items) || data.items.length === 0) {
      cartContainer.innerHTML = '<tr><td colspan="5">Your cart is empty.</td></tr>';
      cartSummary.style.display = 'none';
      return;
    }

    cartSummary.style.display = 'block';

    data.items.forEach(item => {
      const tr = document.createElement('tr');

      // Product Info Cell
      const tdProduct = document.createElement('td');
      const productInfo = document.createElement('div');
      productInfo.className = 'product-info';
      const img = document.createElement('img');
      img.src = getIconUrl(item.image_url) || '/static/img/placeholder_small.webp';
      img.alt = item.product_name || '';
      const details = document.createElement('div');
      const title = document.createElement('p');
      title.textContent = item.product_name || item.sku;
      const meta = document.createElement('span');
      meta.textContent = `${item.color || ''} ${item.size ? '- ' + item.size : ''}`.trim();
      const sku = document.createElement('p');
      sku.textContent = `SKU: ${item.sku}`;
      details.appendChild(title);
      details.appendChild(meta);
      details.appendChild(sku);
      productInfo.appendChild(img);
      productInfo.appendChild(details);
      tdProduct.appendChild(productInfo);

      // Price Cell
      const tdPrice = document.createElement('td');
      tdPrice.className = 'product-price';
      tdPrice.dataset.basePriceCents = item.unit_price_cents;
      tdPrice.textContent = formatPrice(item.unit_price_cents); // Fallback

      // Quantity Cell
      const tdQuantity = document.createElement('td');
      const quantitySelector = document.createElement('div');
      quantitySelector.className = 'quantity-selector';
      const minusBtn = document.createElement('button');
      minusBtn.textContent = '-';
      const qtyInput = document.createElement('input');
      qtyInput.type = 'text';
      qtyInput.value = item.quantity;
      qtyInput.dataset.sku = item.sku;
      qtyInput.className = 'quantity-input';
      const plusBtn = document.createElement('button');
      plusBtn.textContent = '+';
      quantitySelector.appendChild(minusBtn);
      quantitySelector.appendChild(qtyInput);
      quantitySelector.appendChild(plusBtn);
      tdQuantity.appendChild(quantitySelector);

      // Total Cell
      const tdTotal = document.createElement('td');
      tdTotal.className = 'product-price';
      tdTotal.dataset.basePriceCents = item.line_total_cents;
      tdTotal.textContent = formatPrice(item.line_total_cents); // Fallback

      // Delete Cell
      const tdDelete = document.createElement('td');
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'delete-btn';
      deleteBtn.innerHTML = '🗑️';
      deleteBtn.dataset.sku = item.sku;
      tdDelete.appendChild(deleteBtn);

      tr.appendChild(tdProduct);
      tr.appendChild(tdPrice);
      tr.appendChild(tdQuantity);
      tr.appendChild(tdTotal);
      tr.appendChild(tdDelete);
      cartContainer.appendChild(tr);

      // Event Listeners for quantity controls
      minusBtn.addEventListener('click', () => updateCartItem(item.sku, item.quantity - 1));
      plusBtn.addEventListener('click', () => updateCartItem(item.sku, item.quantity + 1));
      qtyInput.addEventListener('change', (e) => {
        const newQty = parseInt(e.target.value, 10);
        if (!isNaN(newQty) && newQty >= 0) {
          updateCartItem(item.sku, newQty);
        }
      });
      deleteBtn.addEventListener('click', () => updateCartItem(item.sku, 0));
    });
  }

  async function updateCartItem(sku, quantity) {
    try {
      const res = await fetch('/api/cart', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ sku, quantity: Math.max(0, quantity) })
      });
      if (!res.ok) {
        const data = await res.json();
        console.error('Failed to update cart:', data.error);
        return;
      }
      await refreshCart();
    } catch (err) {
      console.error('updateCartItem error:', err);
    }
  }

  async function recalcTotals() {
    const items = (cartData.items || []).map(it => ({ sku: it.sku, quantity: it.quantity }));

    try {
      const res = await fetch('/api/calculate-totals', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ items, shipping_country_iso: null, promo_code: null })
      });
      const data = await res.json();

      if (!res.ok) {
        // Fallback display
        if (subtotalEl) subtotalEl.textContent = formatPrice(cartData.subtotal_cents || 0);
        if (totalEl) totalEl.textContent = formatPrice(cartData.subtotal_cents || 0);
        return;
      }

      lastCalc = data;

      // Update Subtotal
      if (subtotalEl) {
          subtotalEl.classList.add('product-price');
          subtotalEl.dataset.basePriceCents = data.subtotal_cents || 0;
          subtotalEl.textContent = formatPrice(data.subtotal_cents || 0); // Fallback
      }

      // Update Total
      const subtotalAfterDiscount = (data.subtotal_after_discount_cents || data.subtotal_cents || 0);
      if (totalEl) {
          totalEl.classList.add('product-price');
          totalEl.dataset.basePriceCents = subtotalAfterDiscount;
          totalEl.textContent = formatPrice(subtotalAfterDiscount); // Fallback
      }

      // Apply dynamic pricing if available
      if (window.updateAllPrices) window.updateAllPrices();

    } catch (err) {
      console.error('recalcTotals error:', err);
    }
  }

  if (checkoutBtn) {
      checkoutBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const isAuthenticated = checkoutBtn.dataset.isAuthenticated === 'true';
        if (isAuthenticated) {
          window.location.href = '/checkout/shipping-address';
        } else {
          window.location.href = '/checkout/login';
        }
      });
  }

  if (continueShoppingBtn) {
      continueShoppingBtn.addEventListener('click', () => {
        window.location.href = '/index';
      });
  }

  if (clearCartBtn) {
      clearCartBtn.addEventListener('click', async () => {
        const itemsToClear = (cartData.items || []).map(item => updateCartItem(item.sku, 0));
        await Promise.all(itemsToClear);
        await refreshCart();
      });
  }

  // Listen for VAT toggle change to update label
  if (vatToggle) {
      vatToggle.addEventListener('change', updateVatLabel);
  }

  (async function init() {
    await refreshCart();
  })();
});
