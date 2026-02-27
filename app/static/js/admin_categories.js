// static/js/admin_categories.js
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
    const categoryList = $('#category-list');
    const saveBtn = $('#save-category');
    const delBtn = $('#delete-category');
    const newBtn = $('#btn-new-category');
    const catNameInput = $('#cat_name');
    const catSlugInput = $('#cat_slug');
    const catMetaTitleInput = $('#cat_meta_title');
    const catMetaDescriptionInput = $('#cat_meta_description');
    const editorTitle = $('#category-editor-title');

    if (!categoryList) return;

    async function loadCategories() {
      const res = await fetch('/api/admin/categories');
      const data = await res.json();
      categoryList.innerHTML = '';
      data.forEach(cat => {
        const item = el('button', {
            class: 'list-group-item list-group-item-action',
            type: 'button'
        }, cat.name);
        item.onclick = () => {
          catNameInput.value = cat.name;
          catSlugInput.value = cat.slug || '';
          catMetaTitleInput.value = cat.meta_title || '';
          catMetaDescriptionInput.value = cat.meta_description || '';
          saveBtn.dataset.id = cat.id;
          editorTitle.textContent = 'Edit Category: ' + cat.name;
        };
        categoryList.appendChild(item);
      });

      if (window.refreshProductCategories) {
          window.refreshProductCategories(data);
      }
    }

    newBtn.onclick = () => {
      catNameInput.value = '';
      catSlugInput.value = '';
      catMetaTitleInput.value = '';
      catMetaDescriptionInput.value = '';
      delete saveBtn.dataset.id;
      editorTitle.textContent = 'Add New Category';
    };

    saveBtn.onclick = async () => {
      const name = catNameInput.value.trim();
      const slug = catSlugInput.value.trim();
      const meta_title = catMetaTitleInput.value.trim();
      const meta_description = catMetaDescriptionInput.value.trim();
      if (!name) return await alert('Category name is required');

      const id = saveBtn.dataset.id;
      const method = id ? 'PUT' : 'POST';
      const url = id ? `/api/admin/categories/${id}` : '/api/admin/categories';

      const headers = { 'Content-Type': 'application/json' };
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch(url, {
        method,
        headers,
        body: JSON.stringify({
            name,
            slug,
            meta_title,
            meta_description
        })
      });

      if (res.ok) {
        await loadCategories();
        newBtn.onclick();
      } else {
        const err = await res.json();
        await alert(err.error || 'Failed to save category');
      }
    };

    delBtn.onclick = async () => {
      const id = saveBtn.dataset.id;
      if (!id) return await alert('Select a category to delete');
      if (!await confirm('Are you sure? Products using this category might prevent deletion.')) return;

      const headers = {};
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch(`/api/admin/categories/${id}`, { method: 'DELETE', headers });
      if (res.ok) {
        await loadCategories();
        newBtn.onclick();
      } else {
        const err = await res.json();
        await alert(err.error || 'Failed to delete category');
      }
    };

    await loadCategories();
    window.refreshAllCategories = loadCategories;
  });
})();
