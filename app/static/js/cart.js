// static/js/cart.js
// Logic for /cart page. Loads cart from API and renders items with quantity controls.

document.addEventListener('DOMContentLoaded', async () => {
  const container = document.getElementById('cart-items-container');
  const summaryEl = document.getElementById('cart-summary');
  const clearCartBtn = document.getElementById('clear-cart-btn');
  const vatToggle = document.getElementById('vat-toggle');

  let cartData = { items: [] };

  function formatPrice(cents) {
      const symbol = (window.appConfig && window.appConfig.currencySymbol) || '$';
      return `${symbol}${(cents / 100).toFixed(2)}`;
  }

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
  }

  function getIconUrl(url) {
    if (!url || !url.includes('/static/')) return url;
    const dotIdx = url.lastIndexOf('.');
    const base = dotIdx !== -1 ? url.substring(0, dotIdx) : url;
    if (base.endsWith('_icon')) return url;
    return base + '_icon.webp';
  }

  async function refreshCart() {
    try {
      const res = await fetch('/api/cart', { credentials: 'same-origin' });
      if (!res.ok) throw new Error('Failed to load cart');
      cartData = await res.json();
      await renderCart();
    } catch (err) {
      console.error('refreshCart error:', err);
      if (container) container.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Error loading cart.</td></tr>';
    }
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
      if (!res.ok) throw new Error('Failed to update cart');
      await refreshCart();
    } catch (err) {
      console.error('updateCartItem error:', err);
    }
  }

  function updateVatLabel() {
      const labels = document.querySelectorAll('.vat-label');
      const isVat = vatToggle && vatToggle.checked;
      labels.forEach(l => {
          l.textContent = isVat ? '(incl. VAT)' : '(excl. VAT)';
      });
  }

  async function renderCart() {
    if (!container) return;
    container.innerHTML = '';

    if (!cartData.items || cartData.items.length === 0) {
      container.innerHTML = `
        <tr>
            <td colspan="5" class="text-center py-5">
                <i class="bi bi-cart-x fs-1 text-muted mb-3"></i>
                <h3>Your cart is empty</h3>
                <p class="text-muted">Looks like you haven't added anything yet.</p>
                <a href="/shop" class="btn btn-primary mt-3">Start Shopping</a>
            </td>
        </tr>
      `;
      if (summaryEl) summaryEl.classList.add('d-none');
      if (clearCartBtn) clearCartBtn.classList.add('d-none');
      return;
    }

    if (summaryEl) summaryEl.classList.remove('d-none');
    if (clearCartBtn) clearCartBtn.classList.remove('d-none');

    cartData.items.forEach(item => {
      const row = document.createElement('tr');
      const img = getIconUrl(item.image_url) || '/static/img/placeholder.webp';

      row.innerHTML = `
        <td>
            <div class="d-flex align-items-center gap-3">
                <img src="${img}" class="img-fluid rounded" alt="${item.product_name}" style="width: 60px; height: 60px; object-fit: cover;">
                <div>
                    <h6 class="mb-0"><a href="/product/${item.product_sku}" class="text-dark text-decoration-none">${item.product_name}</a></h6>
                    <small class="text-muted">${item.color || ''} ${item.size ? ' / ' + item.size : ''}</small>
                </div>
            </div>
        </td>
        <td>
            <div class="text-primary fw-bold product-price" data-base-price-cents="${item.unit_price_cents}">${formatPrice(item.unit_price_cents)}</div>
        </td>
        <td>
            <div class="quantity-selector">
                <button class="minus-btn" type="button">-</button>
                <input type="text" value="${item.quantity}" readonly style="width: 40px; text-align: center; border: none; background: transparent;">
                <button class="plus-btn" type="button">+</button>
            </div>
        </td>
        <td>
            <div class="fw-bold product-price" data-base-price-cents="${item.unit_price_cents * item.quantity}">${formatPrice(item.unit_price_cents * item.quantity)}</div>
        </td>
        <td>
            <button class="btn btn-sm btn-outline-danger delete-item-btn" type="button">
                <i class="bi bi-trash"></i>
            </button>
        </td>
      `;

      row.querySelector('.minus-btn').addEventListener('click', () => updateCartItem(item.sku, item.quantity - 1));
      row.querySelector('.plus-btn').addEventListener('click', () => updateCartItem(item.sku, item.quantity + 1));
      row.querySelector('.delete-item-btn').addEventListener('click', () => updateCartItem(item.sku, 0));

      container.appendChild(row);
    });

    // Update Summary
    const subtotalEl = document.getElementById('cart-subtotal');
    if (subtotalEl) {
        subtotalEl.dataset.basePriceCents = cartData.subtotal_cents;
        subtotalEl.textContent = formatPrice(cartData.subtotal_cents);
    }
    const totalEl = document.getElementById('summary-total');
    if (totalEl) {
        totalEl.dataset.basePriceCents = cartData.subtotal_cents;
        totalEl.textContent = formatPrice(cartData.subtotal_cents);
    }

    if (window.updateAllPrices) await window.updateAllPrices();
    updateVatLabel();
  }

  if (clearCartBtn) {
      clearCartBtn.addEventListener('click', async () => {
        if (!await confirm('Are you sure you want to clear your cart?')) return;
        const itemsToClear = (cartData.items || []).map(item => updateCartItem(item.sku, 0));
        await Promise.all(itemsToClear);
        await refreshCart();
      });
  }

  if (vatToggle) {
      vatToggle.addEventListener('change', updateVatLabel);
  }

  (async function init() {
    await refreshCart();
  })();
});
