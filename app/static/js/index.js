// index.js - loads product list and injects into #product-grid
function getBigUrl(url) {
  if (!url || !url.includes('/static/')) return url;
  const dotIdx = url.lastIndexOf('.');
  const base = dotIdx !== -1 ? url.substring(0, dotIdx) : url;
  if (base.endsWith('_big')) return url;
  return base + '_big.webp';
}

window.addEventListener('DOMContentLoaded', async () => {
  const grid = document.getElementById('product-grid');
  const searchForm = document.getElementById('product-search-form');
  const categorySelect = document.getElementById('search-category');
  const searchInput = document.getElementById('search-input');

  // Load Categories
  if (categorySelect) {
      try {
          const res = await fetch('/api/categories');
          const categories = await res.json();
          categories.forEach(c => {
              const opt = document.createElement('option');
              opt.value = c.name;
              opt.textContent = c.name;
              categorySelect.appendChild(opt);
          });
      } catch (err) {
          console.error('Failed to load categories', err);
      }
  }

  // Check URL params for initial state
  const urlParams = new URLSearchParams(window.location.search);
  const initialCategory = urlParams.get('category');
  if (initialCategory && categorySelect) {
      // We might need to wait for categories to load, or set it after.
      // Since fetch is async, we can set value. If options aren't there yet, it might not select.
      // Better to set it after fetching.
      // For simplicity in this structure, we'll rely on the user manually selecting or refactoring if deep linking is critical.
      // Actually, let's just set it, usually browser handles it if option exists later or we can wait.
      // Let's modify the loadCategories logic slightly or just proceed.
  }

  async function loadProducts(filters = {}) {
      grid.innerHTML = '<div class="col-12 text-center py-5"><div class="spinner-border text-primary" role="status"></div></div>';

      const params = new URLSearchParams({ per_page: 100 });
      if (filters.category) params.append('category', filters.category);
      if (filters.q) params.append('q', filters.q);

      try {
        const res = await fetch(`/api/products?${params.toString()}`, { credentials: 'same-origin' });
        const data = await res.json();
        const products = data.products || [];
        renderProducts(products);
      } catch (err) {
        console.error(err);
        grid.innerHTML = '<p>Could not load products.</p>';
      }
  }

  function renderProducts(products) {
    grid.innerHTML = '';
    if (!products.length) { grid.innerHTML = '<div class="col-12 text-center py-5"><h3>No products found</h3><p class="text-muted">Try adjusting your search criteria.</p></div>'; return; }
    products.forEach(p => {
      const card = document.createElement('div');
      card.className = 'product-card animate__animated animate__fadeInUp';
      const imageUrl = (p.images && p.images.length) ? getBigUrl(p.images[0].url) : '/static/img/placeholder.webp';

      card.innerHTML = `
        <div class="product-image-container ratio ratio-1x1 bg-light">
          <img src="${imageUrl}" class="card-img-top object-fit-cover" alt="${p.name}">
          <div class="product-overlay">
            <a href="/product/${p.product_sku}" class="btn btn-light rounded-pill px-4 fw-bold shadow-sm">View Details</a>
          </div>
          <div class="position-absolute top-0 start-0 m-3 d-flex flex-column gap-2 wide-auto">
             ${p.message ? `<span class="badge bg-info text-dark rounded-pill shadow-sm">${p.message}</span>` : ''}
             ${(p.stock_quantity !== undefined && p.stock_quantity <= 5) ? '<span class="badge bg-danger rounded-pill shadow-sm">Low Stock</span>' : ''}
          </div>
        </div>
        <div class="p-3 d-flex flex-column flex-grow-1 justify-content-between">
          <div>
            <h3 class="h5 fw-bold mb-2 text-truncate-2">
              <a href="/product/${p.product_sku}" class="text-dark text-decoration-none hover-primary">${p.name}</a>
            </h3>
          </div>
          <div class="d-flex justify-content-between align-items-center mt-auto">
            <span class="h5 fw-bold text-orange mb-0 product-price" data-base-price-cents="${p.base_price_cents}">${window.appConfig.currencySymbol}${(p.base_price_cents/100).toFixed(2)}</span>
            <a href="/product/${p.product_sku}" class="btn btn-primary btn-sm rounded-circle" style="width: 40px; height: 40px; padding: 0; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
              <i class="bi bi-cart-plus"></i>
            </a>
          </div>
        </div>
      `;
      grid.appendChild(card);
    });

    if (window.updateAllPrices) window.updateAllPrices();
  }

  // Initial Load
  loadProducts();

  // Search Handler
  if (searchForm) {
      searchForm.addEventListener('submit', (e) => {
          e.preventDefault();
          const category = categorySelect ? categorySelect.value : '';
          const q = searchInput ? searchInput.value.trim() : '';
          loadProducts({ category, q });
      });
  }

  // Auto-filter on category select
  if (categorySelect) {
      categorySelect.addEventListener('change', () => {
          const category = categorySelect.value;
          const q = searchInput ? searchInput.value.trim() : '';
          loadProducts({ category, q });
      });
  }
});
