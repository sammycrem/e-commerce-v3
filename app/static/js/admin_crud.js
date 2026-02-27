// static/js/admin_crud.js
// Admin Product CRUD using SKU as identifier
// Fixed: prefill variant images when editing a product

(async function () {
  'use strict';

  async function el(tag, attrs = {}, ...children) {
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
  async function getRandomChar() {
    const chars = 'abcdefghijklmnopqrstuvwxyz';
    return chars.charAt(Math.floor(Math.random() * chars.length));
  }

  async function generateProductSkuSuffix() {
    // _ + letter + 0-9
    return '_' + getRandomChar() + Math.floor(Math.random() * 10);
  }

  async function generateVariantSkuSuffix() {
    // _ + letter + 0-99
    return '_' + getRandomChar() + Math.floor(Math.random() * 100);
  }

  async function sanitizeSkuInput(val) {
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
        exportJsonBtn.addEventListener('click', async () => {
            e.preventDefault();
            window.location.href = '/api/admin/products/export?format=json';
        });
    }

    const exportCsvBtn = $('#btn-export-csv');
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', async () => {
            e.preventDefault();
            window.location.href = '/api/admin/products/export?format=csv';
        });
    }

    // Import Handlers
    const importBtn = $('#btn-import-products');
    if (importBtn && importModal) {
        importBtn.addEventListener('click', async () => {
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
                    loadProducts(); // Refresh list
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

    async function showFeedback(msg, type = 'info') {
      feedback.style.display = 'block';
      feedback.className = `feedback ${type === 'error' ? 'error' : 'success'}`;
      feedback.textContent = msg;
    }

    async function parsePriceToCents(str) {
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

    async function getIconUrl(url) {
      if (!url || !url.includes('/static/')) return url;
      const dotIdx = url.lastIndexOf('.');
      const base = dotIdx !== -1 ? url.substring(0, dotIdx) : url;
      if (base.endsWith('_icon')) return url;
      return base + '_icon.webp';
    }

    // Add product image row
    async function addProductImageRow(url = '', alt = '', order = 0) {
      const urlInput = el('input', { type: 'text', class: 'form-input img-url', placeholder: 'Image URL', value: url });
      const previewImg = el('img', {
        src: getIconUrl(url) || '/static/img/placeholder_small.webp',
        style: 'width:50px; height:50px; object-fit:cover; border-radius:4px; border:1px solid #eee;'
      });

      urlInput.addEventListener ('input', () => {
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
      row.querySelector ('.btn-upload').addEventListener('click', async () => {
        triggerUpload (urlInput).then(() => {
          previewImg.src = getIconUrl(urlInput.value);
        });
      });
      row.querySelector('.btn-danger').addEventListener('click', async () => {
        const selected = PREDEFINED_COLORS.find(c => c.name.toLowerCase() === color.value.toLowerCase());
        if (selected) {
          const base = parsePriceToCents($('#base_price').value);
          const modCents = Math.round(base * selected.modifier);
          priceMod.value = (modCents / 100).toFixed(2);
          updateFinalPrice();
        }
      });

      updateFinalPrice();

      // container for variant image rows
      const vImgs = el('div', { class: 'variant-images' });

      // function to add one variant-image row (used for both prefill and "Add image" button)
      async function addVariantImageRow(url = '', alt = '', order = 0) {
        const vUrlInput = el('input', { type: 'text', class: 'form-input img-url', placeholder: 'Image URL', value: url });
        const vPreviewImg = el('img', {
          src: getIconUrl(url) || '/static/img/placeholder_small.webp',
          style: 'width:40px; height:40px; object-fit:cover; border-radius:4px; border:1px solid #eee;'
        });

        vUrlInput.addEventListener ('input', () => {
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
        r.querySelector ('.btn-upload').addEventListener('click', async () => {
          triggerUpload (vUrlInput).then(() => {
            vPreviewImg.src = getIconUrl(vUrlInput.value);
          });
        });
        r.querySelector('.btn-danger').addEventListener('click', async () => {
        // Generate NEW suffix for duplicate
        const newSuffix = generateVariantSkuSuffix();

        // Construct new SKU based on CURRENT inputs (or parent's inputs)
        // The requirement says: "use the same original variant name only change the last id"
        // But also "update color and size depending on user variant input" on save.
        // So for the duplicate action, we clone the values but give a new SKU.

        // Let's create the duplicate row
        const currentPrefill = {
          sku: sku.value.replace(wrapper.dataset.skuSuffix, newSuffix), // Just swap suffix
          color_name: color.value,
          size: size.value,
          stock_quantity: parseInt(stock.value || '0'),
          price_modifier_cents: parsePriceToCents(priceMod.value),
          images: []
        };
        // If the original SKU didn't have our suffix yet, append the new one
        if (currentPrefill.sku === sku.value) {
            currentPrefill.sku += newSuffix;
        }

        $all('[data-role="variant-image"]', wrapper).forEach(imgRow => {
          currentPrefill.images.push({
            url: imgRow.querySelector('.img-url').value,
            alt_text: imgRow.querySelector('.img-alt').value,
            display_order: parseInt(imgRow.querySelector('.img-order').value || '0')
          });
        });

        // Add row
        addVariantRow(currentPrefill);
      });

      const removeBtn = el('button', { class: 'btn btn-danger', type: 'button' }, 'Remove Variant');
      removeBtn.addEventListener('click', async () => {
      $all('.variant-fields').forEach(v => {
        const pm = v.querySelector('.variant-price-mod');
        const display = v.querySelector('.variant-final-price');
        const base = parsePriceToCents($('#base_price').value);
        const mod = parsePriceToCents(pm.value);
        display.textContent = `Final Price: ${((base + mod) / 100).toFixed(2)} ${window.appConfig.currencySymbol}`;
      });
    });

    // Load products list
    async function loadProducts() {
      const statusFilter = $('#product-filter-status') ? $('#product-filter-status').value : 'all';
      const res = await fetch(`/api/admin/products?status=${encodeURIComponent(statusFilter)}`);
      const data = await res.json();
      productList.innerHTML = '';
      // support both { products: [...] } and direct array
      const list = Array.isArray(data) ? data : (data.products || []);
      list.forEach(p => {
        // Do not hide soft-deleted if explicitly filtered?
        // Backend filters by status. If status='decommissioned' (which might map to is_active=False),
        // we should show it if returned by API.
        // Previously: if (p.is_active === false) return;
        // We will remove this client-side check and trust the API response.

        // Category Filter
        const catFilter = $('#product-filter-category') ? $('#product-filter-category').value : 'all';
        if (catFilter !== 'all' && p.category !== catFilter) return;

        // Image icon
        const mainImg = (p.images && p.images.length > 0) ? p.images[0].url : null;
        const iconUrl = mainImg ? getIconUrl(mainImg) : '';
        const imgEl = iconUrl ? el('img', {
            src: iconUrl,
            style: 'width: 50px; height: 50px; object-fit: cover; vertical-align: middle; float: right; margin-top: -25px; border-radius: 4px;'
        }) : '';

        // Copy icon
        const copyIcon = el('i', {
            class: 'fas fa-copy text-muted',
            style: 'margin-left: 8px; cursor: pointer; font-size: 1.1em;',
            title: 'Copy SKU'
        });
        copyIcon.addEventListener('click', async () => {
            e.stopPropagation();
            if (navigator.clipboard) {
                navigator.clipboard.writeText (p.product_sku).then(() => {
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
        item.addEventListener('click', async () => {
        const val = $('#product_sku').value.trim();
        if (val) {
            let newVal = sanitizeSkuInput(val);
            // Append suffix if not present (simple check for now, or just append if it's a new entry)
            // Ideally check if we are editing or creating.
            const editSku = saveBtn.dataset.editSku;
            if (!editSku) {
                // Creation Mode: Ensure suffix
                // Check if it ends with _[a-z][0-9]
                if (!/_[a-z]\d$/.test(newVal)) {
                    newVal += generateProductSkuSuffix();
                }
            }
            $('#product_sku').value = newVal;

            // Trigger update on variants if needed?
            // $all('.variant-fields').forEach(v => ... update logic ...)
        }
    });

    // Save product (POST or PUT)
    saveBtn.addEventListener('click', async () => {
      // Final SKU sanitization/generation
      let pSku = $('#product_sku').value.trim();
      let editSku = saveBtn.dataset.editSku;

      if (!editSku && pSku) {
           pSku = sanitizeSkuInput(pSku);
           if (!/_[a-z]\d$/.test(pSku)) {
               pSku += generateProductSkuSuffix();
           }
           $('#product_sku').value = pSku;
      }

      // Update All Variant SKUs before payload construction
      $all('.variant-fields').forEach(v => {
          const skuInput = v.querySelector('.variant-sku');
          const cVal = sanitizeSkuInput(v.querySelector('.variant-color').value.trim() || 'Color');
          const sVal = sanitizeSkuInput(v.querySelector('.variant-size').value.trim() || 'Size');
          const suffix = v.dataset.skuSuffix || generateVariantSkuSuffix();

          // Reconstruct: ProductSKU_Color_Size_Suffix
          skuInput.value = `${pSku}_${cVal}_${sVal}${suffix}`;
          // Ensure dataset is updated just in case
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

      // Re-read editSku (though it shouldn't change, consistency is good)
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
          loadProducts();
        } else {
          showFeedback(data.error || 'Save failed', 'error');
        }
      } catch (err) {
        showFeedback('Network error', 'error');
        console.error(err);
      }
    });

    // Duplicate Product
    $ ('#btn-duplicate-product').addEventListener('click', async () => {
        const editSku = saveBtn.dataset.editSku;
        if (!editSku) {
            showFeedback('Load a product first to duplicate', 'error');
            return;
        }

        // 1. Generate new Product SKU suffix
        // Replace old suffix _x[0-9] or just append if not matching
        let pSku = $('#product_sku').value.trim();
        // Remove existing suffix if present (simple regex for _x[0-9])
        pSku = pSku.replace(/_[a-z]\d+$/, '');
        // Append new suffix
        pSku += generateProductSkuSuffix();

        // 2. Update UI
        $('#product_sku').value = pSku;

        // Update name
        const currentName = $('#name').value.trim();
        if (currentName) {
            $('#name').value = "Copy of " + currentName;
        }

        // 3. Clear edit state so it saves as NEW
        saveBtn.dataset.editSku = '';

        // 4. Update all Variant SKUs
        $all('.variant-fields').forEach(v => {
            const skuInput = v.querySelector('.variant-sku');
            const cVal = sanitizeSkuInput(v.querySelector('.variant-color').value.trim() || 'Color');
            const sVal = sanitizeSkuInput(v.querySelector('.variant-size').value.trim() || 'Size');

            // Generate NEW suffix for variant
            const suffix = generateVariantSkuSuffix();

            // Reconstruct: ProductSKU_Color_Size_Suffix
            skuInput.value = `${pSku}_${cVal}_${sVal}${suffix}`;
            // Update dataset
            v.dataset.skuSuffix = suffix;
        });

        showFeedback('Product duplicated. Modify and click Save to create.', 'success');
    });

    // Delete product
    delBtn.addEventListener('click', async () => {
      const sku = saveBtn.dataset.editSku;
      if (!sku) return showFeedback('No product selected', 'error');

      // Check current status
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
        loadProducts();
        // reset editor if hard deleted or if soft deleted (to clear view)
        ['product_sku', 'name', 'slug', 'meta_title', 'meta_description', 'category', 'base_price', 'message', 'description', 'short_description', 'product_details', 'related_products', 'proposed_products', 'tag1', 'tag2', 'tag3', 'weight_grams', 'length', 'width', 'height'].forEach(id => $(`#${id}`).value = '');
        imagesContainer.innerHTML = '';
        variantsContainer.innerHTML = '';
        saveBtn.dataset.editSku = '';
        $('#status').value = 'draft';
      } else {
          // If 409 Conflict (Used in order), show specific error
          if (res.status === 409) {
              await alert("Error: " + (data.error || "Cannot delete product used in orders."));
              showFeedback('Deletion blocked', 'error');
          } else {
              showFeedback(data.error || 'Delete failed', 'error');
          }
      }
    });

    // New product button
    if (newBtn) newBtn.addEventListener('click', async () => {
      ['product_sku', 'name', 'slug', 'meta_title', 'meta_description', 'category', 'base_price', 'message', 'description', 'short_description', 'product_details', 'related_products', 'proposed_products', 'tag1', 'tag2', 'tag3', 'weight_grams', 'length', 'width', 'height'].forEach(id => $(`#${id}`).value = '');
      $('#status').value = 'draft';
      imagesContainer.innerHTML = '';
      variantsContainer.innerHTML = '';
      addProductImageRow();
      addVariantRow();
      saveBtn.dataset.editSku = '';
      showFeedback('New product');
    });

    // --- Category Dropdown Logic ---
    async function loadCategoryDropdown() {
      const categorySelect = $('#category');
      if (!categorySelect) return;

      const res = await fetch('/api/admin/categories');
      if (res.ok) {
        const categories = await res.json();
        updateCategorySelect(categories);
      }
    }

    async function updateCategorySelect(categories) {
      // Editor Dropdown
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

      // Filter Dropdown
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

    // Expose for admin_categories.js
    window.refreshProductCategories = updateCategorySelect;

    // Initial load
    loadProducts();
    loadCategoryDropdown();
  });
})();
