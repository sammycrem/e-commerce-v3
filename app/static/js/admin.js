// static/js/admin.js
// admin.js (fixed) - builds JSON and posts to /api/products

window.addEventListener('DOMContentLoaded', async () => {
  const imagesContainer = document.getElementById('product-images');
  const addImageBtn = document.getElementById('add-product-image');
  const variantsContainer = document.getElementById('variants');
  const addVariantBtn = document.getElementById('add-variant');
  const submitBtn = document.getElementById('submit-product');
  const feedback = document.getElementById('admin-feedback');

  function el(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    for (const k in attrs) {
      if (k === 'class') e.className = attrs[k];
      else if (k === 'html') e.innerHTML = attrs[k];
      else if (k === 'for') e.htmlFor = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    children.forEach(c => {
      if (typeof c === 'string') e.appendChild(document.createTextNode(c));
      else if (c) e.appendChild(c);
    });
    return e;
  }

  function addProductImageRow(url = '', alt = '', order = 0) {
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
    del.addEventListener('click', () => row.remove());

    row.appendChild(urlIn);
    row.appendChild(altIn);
    row.appendChild(ordIn);
    row.appendChild(del);
    imagesContainer.appendChild(row);
  }

  function addVariantRow() {
    const wrapper = el('div', { class: 'variant-fields', style: 'border:1px solid #eee; padding:10px; margin-bottom:10px;' });

    const skuIn = el('input', { type: 'text', class: 'form-input variant-sku', placeholder: 'Variant SKU' });
    const colorIn = el('input', { type: 'text', class: 'form-input variant-color', placeholder: 'Color' });
    const sizeIn = el('input', { type: 'text', class: 'form-input variant-size', placeholder: 'Size' });
    const stockIn = el('input', { type: 'number', class: 'form-input variant-stock', placeholder: 'Stock' });
    const pmIn = el('input', { type: 'text', class: 'form-input variant-price-mod', placeholder: 'Price mod' });

    const vImgs = el('div', { class: 'variant-images' });
    const addVImgBtn = el('button', { class: 'btn btn-sm', type: 'button' }, 'Add Variant Image');

    function addVariantImageRow() {
      const r = document.createElement('div');
      r.className = 'variant-image-row';
      r.setAttribute('data-role', 'variant-image');

      const u = el('input', { type: 'text', class: 'form-input img-url', placeholder: 'Image URL' });
      const a = el('input', { type: 'text', class: 'form-input img-alt', placeholder: 'Alt text' });
      const o = el('input', { type: 'number', class: 'form-input img-order', placeholder: 'Order' });

      const d = el('button', { class: 'btn btn-danger', type: 'button' }, 'Remove');
      d.addEventListener('click', () => r.remove());

      r.appendChild(u);
      r.appendChild(a);
      r.appendChild(o);
      r.appendChild(d);
      vImgs.appendChild(r);
    }

    addVImgBtn.addEventListener('click', () => addVariantImageRow());

    const removeVar = el('button', { class: 'btn btn-danger', type: 'button' }, 'Remove Variant');
    removeVar.addEventListener('click', () => wrapper.remove());

    wrapper.appendChild(el('label', {}, 'SKU')); wrapper.appendChild(skuIn);
    wrapper.appendChild(el('label', {}, 'Color')); wrapper.appendChild(colorIn);
    wrapper.appendChild(el('label', {}, 'Size')); wrapper.appendChild(sizeIn);
    wrapper.appendChild(el('label', {}, 'Stock')); wrapper.appendChild(stockIn);
    wrapper.appendChild(el('label', {}, 'Price Mod')); wrapper.appendChild(pmIn);
    wrapper.appendChild(vImgs);
    wrapper.appendChild(addVImgBtn);
    wrapper.appendChild(removeVar);

    variantsContainer.appendChild(wrapper);
  }

  if (addImageBtn) addImageBtn.addEventListener('click', () => addProductImageRow());
  if (addVariantBtn) addVariantBtn.addEventListener('click', () => addVariantRow());

  if (submitBtn) submitBtn.addEventListener('click', async () => {
    feedback.style.display = 'none';
    feedback.className = 'feedback';

    const payload = {
      images: [],
      variants: []
    };

    payload.product_sku = (document.getElementById('product_sku') || {}).value?.trim?.() || '';
    payload.name = (document.getElementById('name') || {}).value?.trim?.() || '';
    payload.category = (document.getElementById('category') || {}).value?.trim?.() || '';
    payload.description = (document.getElementById('description') || {}).value?.trim?.() || '';

    const basePriceStr = (document.getElementById('base_price') || {}).value || '0';
    const basePriceFloat = parseFloat(basePriceStr.replace(',', '.')) || 0;
    payload.base_price_cents = Math.round(basePriceFloat * 100);

    imagesContainer.querySelectorAll('[data-role="product-image"]').forEach(row => {
      const urlEl = row.querySelector('.img-url');
      if (!urlEl) return;
      const url = (urlEl.value || '').trim();
      if (!url) return;
      const alt = (row.querySelector('.img-alt')?.value || '').trim();
      const order = parseInt(row.querySelector('.img-order')?.value || '0', 10) || 0;
      payload.images.push({ url, alt_text: alt, order });
    });

    document.querySelectorAll('.variant-fields').forEach(v => {
      const sku = (v.querySelector('.variant-sku') || {}).value?.trim?.() || '';
      if (!sku) return;

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

      v.querySelectorAll('[data-role="variant-image"]').forEach(imgRow => {
        const url = (imgRow.querySelector('.img-url') || {}).value?.trim?.() || '';
        if (!url) return;
        const alt = (imgRow.querySelector('.img-alt') || {}).value?.trim?.() || '';
        const order = parseInt((imgRow.querySelector('.img-order') || {}).value || '0', 10) || 0;
        variant.images.push({ url, alt_text: alt, order });
      });

      payload.variants.push(variant);
    });

    if (!payload.product_sku || !payload.name || payload.variants.length === 0) {
      feedback.style.display = 'block';
      feedback.className = 'feedback error';
      feedback.textContent = 'Product SKU, name and at least one variant are required.';
      return;
    }

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

      setTimeout(() => {
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
