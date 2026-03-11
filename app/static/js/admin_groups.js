// static/js/admin_groups.js
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

  function $(sel) { return document.querySelector(sel); }

  document.addEventListener('DOMContentLoaded', async () => {
    const groupList = $('#group-list');
    const saveBtn = $('#save-group');
    const delBtn = $('#delete-group');
    const newBtn = $('#btn-new-group');
    const groupNameInput = $('#group_name');
    const groupSlugInput = $('#group_slug');
    const groupActiveInput = $('#group_active');
    const groupMetaTitleInput = $('#group_meta_title');
    const groupMetaDescriptionInput = $('#group_meta_description');
    const editorTitle = $('#group-editor-title');
    const groupProductsContainer = $('#group-products-container');
    const productSelect = $('#group-product-select');
    const addSkuInput = $('#group-add-sku');
    const addSkuBtn = $('#btn-group-add-sku');

    let currentGroupProducts = [];

    if (!groupList) return;

    async function loadGroups() {
      const res = await fetch('/api/admin/product-groups');
      const data = await res.json();
      groupList.innerHTML = '';
      data.forEach(group => {
        const item = el('button', {
            class: 'list-group-item list-group-item-action',
            type: 'button'
        }, group.name);
        item.onclick = () => loadGroupDetail(group.id);
        groupList.appendChild(item);
      });
    }

    async function loadGroupDetail(id) {
        const res = await fetch(`/api/admin/product-groups/${id}`);
        const group = await res.json();
        groupNameInput.value = group.name;
        groupSlugInput.value = group.slug || '';
        groupActiveInput.checked = group.is_active;
        groupMetaTitleInput.value = group.meta_title || '';
        groupMetaDescriptionInput.value = group.meta_description || '';
        saveBtn.dataset.id = group.id;
        editorTitle.textContent = 'Edit Group: ' + group.name;
        currentGroupProducts = group.products || [];
        renderGroupProducts();

        document.querySelectorAll('#group-list .list-group-item').forEach(btn => {
            if (btn.textContent === group.name) btn.classList.add('active');
            else btn.classList.remove('active');
        });
    }

    async function loadAllProducts() {
        const res = await fetch('/api/admin/products');
        const products = await res.json();
        productSelect.innerHTML = '<option value="">-- Choose Product --</option>';
        products.forEach(p => {
            productSelect.appendChild(el('option', { value: p.product_sku }, p.name + ' (' + p.product_sku + ')'));
        });
    }

    function getIconUrl(url) {
        if (!url) return '/static/img/placeholder.webp';
        const parts = url.split('.');
        const ext = parts.pop();
        return parts.join('.') + '_icon.webp';
    }

    function renderGroupProducts() {
        groupProductsContainer.innerHTML = '';
        if (currentGroupProducts.length === 0) {
            groupProductsContainer.appendChild(el('div', { class: 'text-muted small p-2' }, 'No products in this group.'));
            return;
        }
        currentGroupProducts.forEach(p => {
            const imgUrl = (p.images && p.images.length) ? getIconUrl(p.images[0].url) : '/static/img/placeholder.webp';
            const item = el('div', { class: 'list-group-item d-flex justify-content-between align-items-center' },
                el('div', { class: 'd-flex align-items-center' },
                    el('img', { src: imgUrl, class: 'me-3 rounded', style: 'width: 40px; height: 40px; object-fit: cover;' }),
                    el('div', {},
                        el('div', { class: 'fw-bold' }, p.name),
                        el('div', { class: 'small text-muted' }, p.product_sku)
                    )
                ),
                el('button', { class: 'btn btn-sm btn-outline-danger', type: 'button' }, 'Remove')
            );
            item.querySelector('button').onclick = () => {
                currentGroupProducts = currentGroupProducts.filter(x => x.product_sku !== p.product_sku);
                renderGroupProducts();
            };
            groupProductsContainer.appendChild(item);
        });
    }

    productSelect.onchange = async () => {
        const sku = productSelect.value;
        if (!sku) return;
        if (currentGroupProducts.some(p => p.product_sku === sku)) {
             productSelect.value = '';
             return;
        }

        const res = await fetch(`/api/admin/products/${sku}`);
        if (res.ok) {
            const p = await res.json();
            currentGroupProducts.push(p);
            renderGroupProducts();
        }
        productSelect.value = '';
    };

    addSkuBtn.onclick = async () => {
        const sku = addSkuInput.value.trim();
        if (!sku) return;

        if (currentGroupProducts.some(p => p.product_sku === sku)) {
            addSkuInput.value = '';
            return;
        }

        const res = await fetch(`/api/admin/products/${sku}`);
        if (res.ok) {
            const p = await res.json();
            currentGroupProducts.push(p);
            renderGroupProducts();
            addSkuInput.value = '';
        } else {
            await alert('Product not found with SKU: ' + sku);
        }
    };

    newBtn.onclick = () => {
      groupNameInput.value = '';
      groupSlugInput.value = '';
      groupActiveInput.checked = false;
      groupMetaTitleInput.value = '';
      groupMetaDescriptionInput.value = '';
      delete saveBtn.dataset.id;
      editorTitle.textContent = 'Create New Product Group';
      currentGroupProducts = [];
      renderGroupProducts();
      document.querySelectorAll('#group-list .list-group-item').forEach(btn => btn.classList.remove('active'));
    };

    saveBtn.onclick = async () => {
      const name = groupNameInput.value.trim();
      if (!name) return await alert('Group name is required');

      const id = saveBtn.dataset.id;
      const method = id ? 'PUT' : 'POST';
      const url = id ? `/api/admin/product-groups/${id}` : '/api/admin/product-groups';

      const headers = { 'Content-Type': 'application/json' };
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const body = {
          name,
          slug: groupSlugInput.value.trim(),
          is_active: groupActiveInput.checked,
          meta_title: groupMetaTitleInput.value.trim(),
          meta_description: groupMetaDescriptionInput.value.trim(),
          product_skus: currentGroupProducts.map(p => p.product_sku)
      };

      const res = await fetch(url, {
        method,
        headers,
        body: JSON.stringify(body)
      });

      if (res.ok) {
        const savedGroup = await res.json();
        await loadGroups();
        await loadGroupDetail(savedGroup.id);
        await alert('Group saved successfully');
      } else {
        const err = await res.json();
        await alert(err.error || 'Failed to save group');
      }
    };

    delBtn.onclick = async () => {
      const id = saveBtn.dataset.id;
      if (!id) return await alert('Select a group to delete');
      if (!await confirm('Are you sure you want to delete this group?')) return;

      const headers = {};
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch(`/api/admin/product-groups/${id}`, { method: 'DELETE', headers });
      if (res.ok) {
        await loadGroups();
        newBtn.onclick();
      } else {
        const err = await res.json();
        await alert(err.error || 'Failed to delete group');
      }
    };

    await loadGroups();
    await loadAllProducts();

    window.refreshAllGroups = async () => {
        await loadGroups();
        await loadAllProducts();
    };
  });
})();
