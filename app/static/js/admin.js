// admin.js (fixed) - builds JSON and posts to /api/products
// Key fixes:
//  - product image rows and variant image rows are tagged with data-role,
//    and inputs have specific classes so collection is robust.
//  - variant.images are collected reliably and included in payload.

window.addEventListener ('DOMContentLoaded', () => {
  const imagesContainer = document.getElementById('product-images');
  const addImageBtn = document.getElementById('add-product-image');
  const variantsContainer = document.getElementById('variants');
  const addVariantBtn = document.getElementById('add-variant');
  const submitBtn = document.getElementById('submit-product');
  const feedback = document.getElementById('admin-feedback');

  // small helper to create element with attrs
  async function el(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    for (const k in attrs) {
      if (k === 'class') e.className = attrs[k];
      else if (k === 'html') e.innerHTML = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    children.forEach(c => {
      if (typeof c === 'string') e.appendChild(document.createTextNode(c));
      else if (c) e.appendChild(c);
    });
    return e;
  }

  // PRODUCT IMAGE ROWS (tagged with data-role="product-image")
  async function addProductImageRow(url = '', alt = '', order = 0) {
    const row = document.createElement('div');
    row.className = 'image-row';
    row.setAttribute('data-role', 'product-image');

    const urlIn = el('input', { type: 'text', class: 'form-input img-url', placeholder: 'Image URL' });
    urlIn.value = url;
    const altIn = el('input', { type: 'text', class: 'form-input img-alt', placeholder: 'Alt text' });
    altIn.value = alt;
    const ordIn = el('input', { type: 'number', class: 'form-input img-order', placeholder: 'Order' });
    ordIn.value = order;

    const del = el('button', { class: 'btn btn-danger', type: 'button' }, 'Remove');
    del.addEventListener('click', async () => {
      const r = document.createElement('div');
      r.className = 'variant-image-row';
      r.setAttribute('data-role', 'variant-image');

      const u = el('input', { type: 'text', class: 'form-input img-url', placeholder: 'Image URL' });
      const a = el('input', { type: 'text', class: 'form-input img-alt', placeholder: 'Alt text' });
      const o = el('input', { type: 'number', class: 'form-input img-order', placeholder: 'Order' });

      const d = el('button', { class: 'btn btn-danger', type: 'button' }, 'Remove');
      d.addEventListener('click', async () => {
    feedback.style.display = 'none';
    feedback.className = 'feedback';

    const payload = {
      images: [],
      variants: []
    };

    // Basic product fields
    payload.product_sku = (document.getElementById('product_sku') || {}).value?.trim?.() || '';
    payload.name = (document.getElementById('name') || {}).value?.trim?.() || '';
    payload.category = (document.getElementById('category') || {}).value?.trim?.() || '';
    payload.description = (document.getElementById('description') || {}).value?.trim?.() || '';

    // Price -> cents
    const basePriceStr = (document.getElementById('base_price') || {}).value || '0';
    const basePriceFloat = parseFloat(basePriceStr.replace(',', '.')) || 0;
    payload.base_price_cents = Math.round(basePriceFloat * 100);

    // Collect product images reliably
    imagesContainer.querySelectorAll('[data-role="product-image"]').forEach(row => {
      const urlEl = row.querySelector('.img-url');
      if (!urlEl) return;
      const url = (urlEl.value || '').trim();
      if (!url) return;
      const alt = (row.querySelector('.img-alt')?.value || '').trim();
      const order = parseInt(row.querySelector('.img-order')?.value || '0', 10) || 0;
      payload.images.push({ url, alt_text: alt, order });
    });

    // Collect variants
    document.querySelectorAll('.variant-fields').forEach(v => {
      const sku = (v.querySelector('.variant-sku') || {}).value?.trim?.() || '';
      if (!sku) return; // skip incomplete variant

      const color = (v.querySelector('.variant-color') || {}).value?.trim?.() || '';
      const size = (v.querySelector('.variant-size') || {}).value?.trim?.() || '';
      const stock = parseInt((v.querySelector('.variant-stock') || {}).value || '0', 10) || 0;
      const pmStr = (v.querySelector('.variant-price-mod') || {}).value || '0';
      const pmFloat = parseFloat(pmStr.replace(',', '.')) || 0;
      const price_modifier_cents = Math.round(pmFloat * 100);

      const variant = {
        sku,
        color_name: color,
        size,
        stock_quantity: stock,
        price_modifier_cents,
        images: []
      };

      // Collect variant images inside this variant
      v.querySelectorAll('[data-role="variant-image"]').forEach(imgRow => {
        const url = (imgRow.querySelector('.img-url') || {}).value?.trim?.() || '';
        if (!url) return;
        const alt = (imgRow.querySelector('.img-alt') || {}).value?.trim?.() || '';
        const order = parseInt((imgRow.querySelector('.img-order') || {}).value || '0', 10) || 0;
        variant.images.push({ url, alt_text: alt, order });
      });

      payload.variants.push(variant);
    });

    // Validate minimal fields
    if (!payload.product_sku || !payload.name || payload.variants.length === 0) {
      feedback.style.display = 'block';
      feedback.className = 'feedback error';
      feedback.textContent = 'Product SKU, name and at least one variant are required.';
      return;
    }

    // POST payload
    try {
      const resp = await fetch('/api/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(payload)
      });

      const data = await resp.json();
      if (!resp.ok) {
        feedback.style.display = 'block';
        feedback.className = 'feedback error';
        feedback.textContent = data.error || 'Failed to create product';
        return;
      }

      feedback.style.display = 'block';
      feedback.className = 'feedback success';
      feedback.textContent = `Product created: ${data.product_sku || data.name || ''}`;

      // Redirect to product page after a short delay
      setTimeoutasync (() => {
        window.location.href = `/product/${encodeURIComponent(payload.product_sku)}`;
      }, 800);

    } catch (err) {
      feedback.style.display = 'block';
      feedback.className = 'feedback error';
      feedback.textContent = 'Network or server error when creating product.';
      console.error(err);
    }
  });
});
