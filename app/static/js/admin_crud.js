// static/js/admin_crud.js
// Admin Product CRUD using SKU as identifier
// Fixed: prefill variant images when editing a product

(function () {
  'use strict';

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

  function $(sel, root = document) { return root.querySelector(sel); }
  function $all(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

  // SKU Helpers
  function getRandomChar() {
    const chars = 'abcdefghijklmnopqrstuvwxyz';
    return chars.charAt(Math.floor(Math.random() * chars.length));
  }

  function generateProductSkuSuffix() {
    // _ + letter + 0-9
    return '_' + getRandomChar() + Math.floor(Math.random() * 10);
  }

  function generateVariantSkuSuffix() {
    // _ + letter + 0-99
    return '_' + getRandomChar() + Math.floor(Math.random() * 100);
  }

  function sanitizeSkuInput(val) {
    return val.trim().replace(/\s+/g, '_');
  }

  const PREDEFINED_COLORS = [
    { name: 'White', modifier: 0.0 },
    { name: 'Red', modifier: 0.20 },
    { name: 'Black', modifier: 0.10 }
  ];

  document.addEventListener('DOMContentLoaded', async () => {
    const imagesContainer = $('#product-images');
    const variantsContainer = $('#variants');
    const feedback = $('#admin-feedback');
    const productList = $('#product-list');
    const newBtn = $('#btn-new-product');
    const saveBtn = $('#save-product');
    const delBtn = $('#delete-product');

    // --- Import / Export Logic ---
    const importModalEl = document.getElementById('importModal');
    let importModal;
    if (importModalEl && window.bootstrap) {
        importModal = new bootstrap.Modal(importModalEl);
    }

    // Export Handlers
    const exportJsonBtn = $('#btn-export-json');
    if (exportJsonBtn) {
        exportJsonBtn.addEventListener('click', (e) => {
            e.preventDefault();
            window.location.href = '/api/admin/products/export?format=json';
        });
    }

    const exportCsvBtn = $('#btn-export-csv');
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', (e) => {
            e.preventDefault();
            window.location.href = '/api/admin/products/export?format=csv';
        });
    }

    // Import Handlers
    const importBtn = $('#btn-import-products');
    if (importBtn && importModal) {
        importBtn.addEventListener('click', () => {
             // Reset form
             const form = $('#importForm');
             if (form) form.reset();
             importModal.show();
        });
    }

    const confirmImportBtn = $('#btn-confirm-import');
    if (confirmImportBtn) {
        confirmImportBtn.addEventListener('click', async () => {
            const fileInput = $('#importFile');
            const file = fileInput.files[0];
            if (!file) {
                await alert("Please select a file.");
                return;
            }

            const mode = document.querySelector('input[name="importMode"]:checked').value;

            const formData = new FormData();
            formData.append('file', file);
            formData.append('mode', mode);

            // Disable button
            confirmImportBtn.disabled = true;
            confirmImportBtn.textContent = 'Importing...';

            try {
                const headers = {};
                const csrfToken = document.querySelector('meta[name="csrf-token"]');
                if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

                const res = await fetch('/api/admin/products/import', {
                    method: 'POST',
                    headers: headers,
                    body: formData
                });
                const data = await res.json();

                if (res.ok) {
                    showFeedback(data.message || 'Import successful', 'success');
                    importModal.hide();
                    await loadProducts(); // Refresh list
                } else {
                    await alert(data.error || 'Import failed');
                }
            } catch (err) {
                console.error(err);
                await alert('An error occurred during import.');
            } finally {
                confirmImportBtn.disabled = false;
                confirmImportBtn.textContent = 'Import';
            }
        });
    }
    // ----------------------------

    if (!imagesContainer || !variantsContainer) return;

    function showFeedback(msg, type = 'info') {
      feedback.style.display = 'block';
      feedback.className = `feedback ${type === 'error' ? 'error' : 'success'}`;
      feedback.textContent = msg;
    }

    function parsePriceToCents(str) {
      const cleaned = (str || '').replace(',', '.').replace(/[^0-9.]/g, '');
      const val = parseFloat(cleaned);
      return isNaN(val) ? 0 : Math.round(val * 100);
    }

    async function triggerUpload(targetInput) {
      const fileInput = el('input', { type: 'file', accept: 'image/*' });
      fileInput.onchange = async () => {
        if (!fileInput.files.length) return;
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        try {
          showFeedback('Uploading...');
          const headers = {};
          const csrfToken = document.querySelector('meta[name="csrf-token"]');
          if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

          const res = await fetch('/api/admin/upload-image', {
            method: 'POST',
            headers: headers,
            body: formData
          });
          const data = await res.json();
          if (res.ok) {
            targetInput.value = data.url;
            targetInput.dispatchEvent(new Event('input'));
            showFeedback('Upload successful', 'success');
          } else {
            showFeedback(data.error || 'Upload failed', 'error');
          }
        } catch (err) {
          showFeedback('Upload error', 'error');
          console.error(err);
        }
      };
      fileInput.click();
    }

    function getIconUrl(url) {
      if (!url || !url.includes('/static/')) return url;
      const dotIdx = url.lastIndexOf('.');
      const base = dotIdx !== -1 ? url.substring(0, dotIdx) : url;
      if (base.endsWith('_icon')) return url;
      return base + '_icon.webp';
    }

    // Add product image row
    function addProductImageRow(url = '', alt = '', order = 0) {
      const urlInput = el('input', { type: 'text', class: 'form-input img-url', placeholder: 'Image URL', value: url });
      const previewImg = el('img', {
        src: getIconUrl(url) || '/static/img/placeholder_small.webp',
        style: 'width:50px; height:50px; object-fit:cover; border-radius:4px; border:1px solid #eee;'
      });

      urlInput.addEventListener('input', () => {
        previewImg.src = getIconUrl(urlInput.value) || '/static/img/placeholder_small.webp';
      });

      const row = el('div', { class: 'image-row', 'data-role': 'product-image' },
        previewImg,
        urlInput,
        el('input', { type: 'text', class: 'form-input img-alt', placeholder: 'Alt text', value: alt }),
        el('input', { type: 'number', class: 'form-input img-order', placeholder: 'Order', value: order }),
        el('button', { class: 'btn btn-secondary btn-upload', type: 'button' }, 'Upload'),
        el('button', { class: 'btn btn-danger', type: 'button' }, 'Remove')
      );
      row.querySelector ('.btn-upload').addEventListener('click', () => {
        triggerUpload(urlInput);
      });
      row.querySelector('.btn-danger').addEventListener('click', () => row.remove());
      imagesContainer.appendChild(row);
    }

    // Add variant row
    function addVariantRow(prefill = {}) {
      const wrapper = el('div', { class: 'variant-fields', style: 'border:1px solid #eee; padding:10px; border-radius:6px; margin-bottom:8px;' });

      let initialSku = prefill.sku || '';
      if (!initialSku) {
         const pSku = $('#product_sku').value.trim() || 'ProductSKU';
         initialSku = sanitizeSkuInput(pSku) + generateVariantSkuSuffix();
      }

      const sku = el('input', { type: 'text', class: 'form-input variant-sku', placeholder: 'Variant SKU', value: initialSku });
      const colorListId = 'colors-' + Math.random().toString(36).substr(2, 9);
      const colorDatalist = el('datalist', { id: colorListId });
      PREDEFINED_COLORS.forEach(c => colorDatalist.appendChild(el('option', { value: c.name })));

      const color = el('input', { type: 'text', class: 'form-input variant-color', placeholder: 'Color (e.g. Red)', value: prefill.color_name || '', list: colorListId });
      const size = el('input', { type: 'text', class: 'form-input variant-size', placeholder: 'Size (e.g. M)', value: prefill.size || '' });
      const stock = el('input', { type: 'number', class: 'form-input variant-stock', placeholder: 'Stock', value: prefill.stock_quantity || 0 });
      const priceMod = el('input', { type: 'text', class: 'form-input variant-price-mod', placeholder: 'Price modifier', value: prefill.price_modifier_cents ? (prefill.price_modifier_cents / 100).toFixed(2) : '0.00' });

      const finalPriceDisplay = el('div', { class: 'mt-1 small fw-bold text-primary variant-final-price' }, `Final Price: 0.00 ${window.appConfig.currencySymbol}`);

      function updateFinalPrice() {
        const base = parsePriceToCents($('#base_price').value);
        const mod = parsePriceToCents(priceMod.value);
        finalPriceDisplay.textContent = `Final Price: ${((base + mod) / 100).toFixed(2)} ${window.appConfig.currencySymbol}`;
      }

      priceMod.addEventListener('input', updateFinalPrice);
      color.addEventListener('change', () => {
        const selected = PREDEFINED_COLORS.find(c => c.name.toLowerCase() === color.value.toLowerCase());
        if (selected) {
          const base = parsePriceToCents($('#base_price').value);
          const modCents = Math.round(base * selected.modifier);
          priceMod.value = (modCents / 100).toFixed(2);
          updateFinalPrice();
        }
      });

      updateFinalPrice();

      const vImgs = el('div', { class: 'variant-images' });

      function addVariantImageRow(url = '', alt = '', order = 0) {
        const vUrlInput = el('input', { type: 'text', class: 'form-input img-url', placeholder: 'Image URL', value: url });
        const vPreviewImg = el('img', {
          src: getIconUrl(url) || '/static/img/placeholder_small.webp',
          style: 'width:40px; height:40px; object-fit:cover; border-radius:4px; border:1px solid #eee;'
        });

        vUrlInput.addEventListener('input', () => {
          vPreviewImg.src = getIconUrl(vUrlInput.value) || '/static/img/placeholder_small.webp';
        });

        const r = el('div', { class: 'variant-image-row', 'data-role': 'variant-image' },
          vPreviewImg,
          vUrlInput,
          el('input', { type: 'text', class: 'form-input img-alt', placeholder: 'Alt text', value: alt }),
          el('input', { type: 'number', class: 'form-input img-order', placeholder: 'Order', value: order }),
          el('button', { class: 'btn btn-secondary btn-upload', type: 'button' }, 'Upload'),
          el('button', { class: 'btn btn-danger', type: 'button' }, 'Remove')
        );
        r.querySelector ('.btn-upload').addEventListener('click', () => {
          triggerUpload(vUrlInput);
        });
        r.querySelector('.btn-danger').addEventListener('click', () => r.remove());
        vImgs.appendChild(r);
      }

      if (Array.isArray(prefill.images) && prefill.images.length) {
        prefill.images.forEach(img => {
          addVariantImageRow(img.url, img.alt_text || img.alt || '', img.display_order ?? img.order ?? 0);
        });
      }

      const addImg = el('button', { class: 'btn btn-outline-primary', type: 'button', style: 'margin-right: 8px;' }, 'Add Variant Image');
      addImg.addEventListener('click', () => addVariantImageRow());

      let currentSuffix = generateVariantSkuSuffix();
      const parts = initialSku.split('_');
      if (parts.length > 1) {
          const last = parts[parts.length-1];
          if (/^[a-z]\d+$/.test(last)) {
              currentSuffix = '_' + last;
          }
      }
      wrapper.dataset.skuSuffix = currentSuffix;

      function updateVariantSku() {
          const pSku = sanitizeSkuInput($('#product_sku').value.trim() || 'ProductSKU');
          const cVal = sanitizeSkuInput(color.value.trim() || 'Color');
          const sVal = sanitizeSkuInput(size.value.trim() || 'Size');
          sku.value = `${pSku}_${cVal}_${sVal}${wrapper.dataset.skuSuffix}`;
      }

      color.addEventListener('input', updateVariantSku);
      size.addEventListener('input', updateVariantSku);

      const duplicateBtn = el('button', { class: 'btn btn-outline-primary', type: 'button', style: 'margin-right: 8px;' }, 'Duplicate');
      duplicateBtn.addEventListener('click', () => {
        const newSuffix = generateVariantSkuSuffix();
        const currentPrefill = {
          sku: sku.value.replace(wrapper.dataset.skuSuffix, newSuffix),
          color_name: color.value,
          size: size.value,
          stock_quantity: parseInt(stock.value || '0'),
          price_modifier_cents: parsePriceToCents(priceMod.value),
          images: []
        };
        if (currentPrefill.sku === sku.value) currentPrefill.sku += newSuffix;

        $all('[data-role="variant-image"]', wrapper).forEach(imgRow => {
          currentPrefill.images.push({
            url: imgRow.querySelector('.img-url').value,
            alt_text: imgRow.querySelector('.img-alt').value,
            display_order: parseInt(imgRow.querySelector('.img-order').value || '0')
          });
        });

        addVariantRow(currentPrefill);
      });

      const removeBtn = el('button', { class: 'btn btn-danger', type: 'button' }, 'Remove Variant');
      removeBtn.addEventListener('click', () => wrapper.remove());

      wrapper.appendChild(el('label', {}, 'Variant SKU')); wrapper.appendChild(sku);
      wrapper.appendChild(el('label', {}, 'Color')); wrapper.appendChild(color);
      wrapper.appendChild(el('label', {}, 'Size')); wrapper.appendChild(size);
      wrapper.appendChild(el('label', {}, 'Stock quantity')); wrapper.appendChild(stock);
      wrapper.appendChild(el('label', {}, `Price modifier (${window.appConfig.currencySymbol})`)); wrapper.appendChild(priceMod);
      wrapper.appendChild(finalPriceDisplay);
      wrapper.appendChild(colorDatalist);
      wrapper.appendChild(vImgs);
      wrapper.appendChild(addImg);
      wrapper.appendChild(duplicateBtn);
      wrapper.appendChild(removeBtn);

      variantsContainer.appendChild(wrapper);
    }

    $('#add-product-image').addEventListener('click', () => addProductImageRow());
    $('#add-variant').addEventListener('click', () => addVariantRow());

    addProductImageRow();
    addVariantRow();

    $('#base_price').addEventListener('input', () => {
      $all('.variant-fields').forEach(v => {
        const pm = v.querySelector('.variant-price-mod');
        const display = v.querySelector('.variant-final-price');
        const base = parsePriceToCents($('#base_price').value);
        const mod = parsePriceToCents(pm.value);
        display.textContent = `Final Price: ${((base + mod) / 100).toFixed(2)} ${window.appConfig.currencySymbol}`;
      });
    });

    async function loadProducts() {
      const statusFilter = $('#product-filter-status') ? $('#product-filter-status').value : 'all';
      const res = await fetch(`/api/admin/products?status=${encodeURIComponent(statusFilter)}`);
      const data = await res.json();
      productList.innerHTML = '';
      const list = Array.isArray(data) ? data : (data.products || []);
      list.forEach(p => {
        const catFilter = $('#product-filter-category') ? $('#product-filter-category').value : 'all';
        if (catFilter !== 'all' && p.category !== catFilter) return;

        const mainImg = (p.images && p.images.length > 0) ? p.images[0].url : null;
        const iconUrl = mainImg ? getIconUrl(mainImg) : '';
        const imgEl = iconUrl ? el('img', {
            src: iconUrl,
            style: 'width: 50px; height: 50px; object-fit: cover; vertical-align: middle; float: right; margin-top: -25px; border-radius: 4px;'
        }) : '';

        const copyIcon = el('i', {
            class: 'fas fa-copy text-muted',
            style: 'margin-left: 8px; cursor: pointer; font-size: 1.1em;',
            title: 'Copy SKU'
        });
        copyIcon.addEventListener('click', (e) => {
            e.stopPropagation();
            if (navigator.clipboard) {
                navigator.clipboard.writeText(p.product_sku).then(() => {
                    copyIcon.className = 'fas fa-check text-success';
                    setTimeout(() => copyIcon.className = 'fas fa-copy text-muted', 1000);
                });
            }
        });

        const item = el('div', { class: 'product-list-item', style: 'padding:6px; border-bottom:1px solid #eee; cursor:pointer;' },
            el('div', {}, `${p.name}`),
            el('small', { class: 'text-muted' },
                `${p.product_sku}`,
                copyIcon,
                imgEl,
                document.createTextNode(` - ${p.status}`)
            )
        );
        item.addEventListener('click', () => loadProduct(p.product_sku));
        productList.appendChild(item);
      });
    }

    if ($('#product-filter-status')) {
        $('#product-filter-status').addEventListener('change', loadProducts);
    }
    if ($('#product-filter-category')) {
        $('#product-filter-category').addEventListener('change', loadProducts);
    }

    async function loadProduct(sku) {
      const res = await fetch(`/api/admin/products/${encodeURIComponent(sku)}`);
      if (!res.ok) return showFeedback(`Failed to load product ${sku}`, 'error');
      const p = await res.json();
      $('#product_sku').value = p.product_sku;
      $('#name').value = p.name;
      $('#slug').value = p.slug || '';
      $('#meta_title').value = p.meta_title || '';
      $('#meta_description').value = p.meta_description || '';
      const catSelect = $('#category');
      if (catSelect) {
        catSelect.dataset.pendingValue = p.category;
        catSelect.value = p.category;
      }
      $('#base_price').value = (p.base_price_cents / 100).toFixed(2);
      $('#message').value = p.message || '';
      $('#status').value = p.status || 'draft';
      $('#description').value = p.description || '';
      $('#short_description').value = p.short_description || '';
      $('#product_details').value = p.product_details || '';
      $('#related_products').value = (p.related_products || []).join(', ');
      $('#proposed_products').value = (p.proposed_products || []).join(', ');
      $('#tag1').value = p.tag1 || '';
      $('#tag2').value = p.tag2 || '';
      $('#tag3').value = p.tag3 || '';
      $('#weight_grams').value = p.weight_grams || 0;
      $('#length').value = p.dimensions_json?.length || 0;
      $('#width').value = p.dimensions_json?.width || 0;
      $('#height').value = p.dimensions_json?.height || 0;
      imagesContainer.innerHTML = '';
      (p.images || []).forEach(img => addProductImageRow(img.url, img.alt_text || img.alt || '', img.display_order || img.order || 0));
      variantsContainer.innerHTML = '';
      (p.variants || []).forEach(v => addVariantRow(v));
      saveBtn.dataset.editSku = p.product_sku;
      showFeedback(`Loaded product ${p.name}`);
    }

    $('#product_sku').addEventListener('blur', () => {
        const val = $('#product_sku').value.trim();
        if (val) {
            let newVal = sanitizeSkuInput(val);
            const editSku = saveBtn.dataset.editSku;
            if (!editSku) {
                if (!/_[a-z]\d$/.test(newVal)) {
                    newVal += generateProductSkuSuffix();
                }
            }
            $('#product_sku').value = newVal;
        }
    });

    saveBtn.addEventListener('click', async () => {
      let pSku = $('#product_sku').value.trim();
      let editSku = saveBtn.dataset.editSku;

      if (!editSku && pSku) {
           pSku = sanitizeSkuInput(pSku);
           if (!/_[a-z]\d$/.test(pSku)) {
               pSku += generateProductSkuSuffix();
           }
           $('#product_sku').value = pSku;
      }

      $all('.variant-fields').forEach(v => {
          const skuInput = v.querySelector('.variant-sku');
          const cVal = sanitizeSkuInput(v.querySelector('.variant-color').value.trim() || 'Color');
          const sVal = sanitizeSkuInput(v.querySelector('.variant-size').value.trim() || 'Size');
          const suffix = v.dataset.skuSuffix || generateVariantSkuSuffix();
          skuInput.value = `${pSku}_${cVal}_${sVal}${suffix}`;
          v.dataset.skuSuffix = suffix;
      });

      const payload = {
        product_sku: pSku,
        name: $('#name').value.trim(),
        slug: $('#slug').value.trim(),
        meta_title: $('#meta_title').value.trim(),
        meta_description: $('#meta_description').value.trim(),
        category: $('#category').value.trim(),
        message: $('#message').value.trim(),
        status: $('#status').value,
        description: $('#description').value.trim(),
        short_description: $('#short_description').value.trim(),
        product_details: $('#product_details').value.trim(),
        related_products: $('#related_products').value.split(',').map(s => s.trim()).filter(s => s),
        proposed_products: $('#proposed_products').value.split(',').map(s => s.trim()).filter(s => s),
        tag1: $('#tag1').value.trim(),
        tag2: $('#tag2').value.trim(),
        tag3: $('#tag3').value.trim(),
        weight_grams: parseInt($('#weight_grams').value || '0'),
        dimensions_json: {
          length: parseInt($('#length').value || '0'),
          width: parseInt($('#width').value || '0'),
          height: parseInt($('#height').value || '0')
        },
        base_price_cents: parsePriceToCents($('#base_price').value),
        images: [],
        variants: []
      };

      $all('[data-role="product-image"]').forEach(row => {
        const url = row.querySelector('.img-url').value.trim();
        if (!url) return;
        payload.images.push({
          url,
          alt_text: row.querySelector('.img-alt').value.trim(),
          display_order: parseInt(row.querySelector('.img-order').value || '0')
        });
      });

      $all('.variant-fields').forEach(v => {
        const sku = v.querySelector('.variant-sku').value.trim();
        if (!sku) return;
        const variant = {
          sku,
          color_name: v.querySelector('.variant-color').value.trim(),
          size: v.querySelector('.variant-size').value.trim(),
          stock_quantity: parseInt(v.querySelector('.variant-stock').value || '0'),
          price_modifier_cents: parsePriceToCents(v.querySelector('.variant-price-mod').value),
          images: []
        };
        $all('[data-role="variant-image"]', v).forEach(imgRow => {
          const url = imgRow.querySelector('.img-url').value.trim();
          if (!url) return;
          variant.images.push({
            url,
            alt_text: imgRow.querySelector('.img-alt').value.trim(),
            display_order: parseInt(imgRow.querySelector('.img-order').value || '0')
          });
        });
        payload.variants.push(variant);
      });

      editSku = saveBtn.dataset.editSku;
      const method = editSku ? 'PUT' : 'POST';
      const url = editSku ? `/api/admin/products/${encodeURIComponent(editSku)}` : '/api/admin/products';

      try {
        const headers = { 'Content-Type': 'application/json' };
        const csrfToken = document.querySelector('meta[name="csrf-token"]');
        if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

        const res = await fetch(url, { method, headers: headers, body: JSON.stringify(payload) });
        const data = await res.json();
        if (res.ok) {
          showFeedback(`Product ${data.name} saved.`, 'success');
          await loadProducts();
        } else {
          showFeedback(data.error || 'Save failed', 'error');
        }
      } catch (err) {
        showFeedback('Network error', 'error');
        console.error(err);
      }
    });

    $('#btn-duplicate-product').addEventListener('click', () => {
        const editSku = saveBtn.dataset.editSku;
        if (!editSku) {
            showFeedback('Load a product first to duplicate', 'error');
            return;
        }

        let pSku = $('#product_sku').value.trim();
        pSku = pSku.replace(/_[a-z]\d+$/, '');
        pSku += generateProductSkuSuffix();

        $('#product_sku').value = pSku;
        const currentName = $('#name').value.trim();
        if (currentName) $('#name').value = "Copy of " + currentName;

        saveBtn.dataset.editSku = '';

        $all('.variant-fields').forEach(v => {
            const skuInput = v.querySelector('.variant-sku');
            const cVal = sanitizeSkuInput(v.querySelector('.variant-color').value.trim() || 'Color');
            const sVal = sanitizeSkuInput(v.querySelector('.variant-size').value.trim() || 'Size');
            const suffix = generateVariantSkuSuffix();
            skuInput.value = `${pSku}_${cVal}_${sVal}${suffix}`;
            v.dataset.skuSuffix = suffix;
        });

        showFeedback('Product duplicated. Modify and click Save to create.', 'success');
    });

    delBtn.addEventListener('click', async () => {
      const sku = saveBtn.dataset.editSku;
      if (!sku) return showFeedback('No product selected', 'error');

      const statusSelect = $('#status');
      const isDecommissioned = statusSelect.value === 'decommissioned';

      let msg = 'Decommission this product? It will remain in the database but hidden from the shop.';
      if (isDecommissioned) {
          msg = 'PERMANENTLY DELETE this product? This will remove it from the database entirely.\n\nNote: Products used in past orders cannot be deleted.';
      }

      if (!await confirm(msg)) return;

      const headers = {};
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch(`/api/admin/products/${encodeURIComponent(sku)}`, { method: 'DELETE', headers: headers });
      const data = await res.json();

      if (res.ok) {
        showFeedback(data.message || 'Deleted', 'success');
        await loadProducts();
        ['product_sku', 'name', 'slug', 'meta_title', 'meta_description', 'category', 'base_price', 'message', 'description', 'short_description', 'product_details', 'related_products', 'proposed_products', 'tag1', 'tag2', 'tag3', 'weight_grams', 'length', 'width', 'height'].forEach(id => $(`#${id}`).value = '');
        imagesContainer.innerHTML = '';
        variantsContainer.innerHTML = '';
        saveBtn.dataset.editSku = '';
        $('#status').value = 'draft';
      } else {
          if (res.status === 409) {
              await alert("Error: " + (data.error || "Cannot delete product used in orders."));
              showFeedback('Deletion blocked', 'error');
          } else {
              showFeedback(data.error || 'Delete failed', 'error');
          }
      }
    });

    newBtn.addEventListener('click', () => {
      ['product_sku', 'name', 'slug', 'meta_title', 'meta_description', 'category', 'base_price', 'message', 'description', 'short_description', 'product_details', 'related_products', 'proposed_products', 'tag1', 'tag2', 'tag3', 'weight_grams', 'length', 'width', 'height'].forEach(id => $(`#${id}`).value = '');
      $('#status').value = 'draft';
      imagesContainer.innerHTML = '';
      variantsContainer.innerHTML = '';
      addProductImageRow();
      addVariantRow();
      saveBtn.dataset.editSku = '';
      showFeedback('New product');
    });

    async function loadCategoryDropdown() {
      const categorySelect = $('#category');
      if (!categorySelect) return;

      const res = await fetch('/api/admin/categories');
      if (res.ok) {
        const categories = await res.json();
        updateCategorySelect(categories);
      }
    }

    function updateCategorySelect(categories) {
      const categorySelect = $('#category');
      if (categorySelect) {
        const desiredVal = categorySelect.dataset.pendingValue || categorySelect.value;
        categorySelect.innerHTML = '<option value="">Select Category</option>';
        categories.forEach(cat => {
            const opt = el('option', { value: cat.name }, cat.name);
            if (cat.name === desiredVal) opt.selected = true;
            categorySelect.appendChild(opt);
        });
      }

      const filterSelect = $('#product-filter-category');
      if (filterSelect) {
          const currentFilter = filterSelect.value;
          filterSelect.innerHTML = '<option value="all">All Categories</option>';
          categories.forEach(cat => {
              const opt = el('option', { value: cat.name }, cat.name);
              if (cat.name === currentFilter) opt.selected = true;
              filterSelect.appendChild(opt);
          });
      }
    }

    window.refreshProductCategories = updateCategorySelect;

    await loadProducts();
    await loadCategoryDropdown();
  });
})();
