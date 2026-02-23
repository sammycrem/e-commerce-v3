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

  document.addEventListener('DOMContentLoaded', () => {
    const categoryList = $('#category-list');
    const saveBtn = $('#save-category');
    const delBtn = $('#delete-category');
    const newBtn = $('#btn-new-category');
    const catNameInput = $('#cat_name');
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
          saveBtn.dataset.id = cat.id;
          editorTitle.textContent = 'Edit Category: ' + cat.name;
        };
        categoryList.appendChild(item);
      });

      // Also trigger a refresh of product category dropdown if it exists
      if (window.refreshProductCategories) {
          window.refreshProductCategories(data);
      }
    }

    newBtn.onclick = () => {
      catNameInput.value = '';
      delete saveBtn.dataset.id;
      editorTitle.textContent = 'Add New Category';
    };

    saveBtn.onclick = async () => {
      const name = catNameInput.value.trim();
      if (!name) return alert('Category name is required');

      const id = saveBtn.dataset.id;
      const method = id ? 'PUT' : 'POST';
      const url = id ? `/api/admin/categories/${id}` : '/api/admin/categories';

      const headers = { 'Content-Type': 'application/json' };
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch(url, {
        method,
        headers,
        body: JSON.stringify({ name })
      });

      if (res.ok) {
        loadCategories();
        newBtn.onclick();
      } else {
        const err = await res.json();
        alert(err.error || 'Failed to save category');
      }
    };

    delBtn.onclick = async () => {
      const id = saveBtn.dataset.id;
      if (!id) return alert('Select a category to delete');
      if (!confirm('Are you sure? Products using this category might prevent deletion.')) return;

      const headers = {};
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch(`/api/admin/categories/${id}`, { method: 'DELETE', headers });
      if (res.ok) {
        loadCategories();
        newBtn.onclick();
      } else {
        const err = await res.json();
        alert(err.error || 'Failed to delete category');
      }
    };

    loadCategories();
    window.refreshAllCategories = loadCategories;
  });
})();
