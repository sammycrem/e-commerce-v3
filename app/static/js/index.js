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

  // Load Categories (only if not already populated by Jinja2)
  if (categorySelect && categorySelect.options.length <= 1) {
      try {
          const res = await fetch('/api/categories');
          const categories = await res.json();
          categories.forEach(c => {
              // Avoid duplicates if Jinja2 partially populated or something
              if (![...categorySelect.options].some(opt => opt.value === c.name)) {
                  const opt = document.createElement('option');
                  opt.value = c.name;
                  opt.textContent = c.name;
                  categorySelect.appendChild(opt);
              }
          });
      } catch (err) {
          console.error('Failed to load categories', err);
      }
  }

  // Check URL params for initial state
  const urlParams = new URLSearchParams(window.location.search);
  const initialCategory = urlParams.get('category');
  const initialQ = urlParams.get('q');

  if (initialCategory && categorySelect) {
      categorySelect.value = initialCategory;
  }
  if (initialQ && searchInput) {
      searchInput.value = initialQ;
  }

  async function loadProducts(filters = {}) {
      if (!grid) return;
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
        grid.innerHTML = '<div class="col-12 text-center py-5"><h3>Error loading products</h3><p>Please try again later.</p></div>';
      }
  }

  function renderProducts(products) {
    if (!grid) return;
    grid.innerHTML = '';
    if (!products.length) {
        grid.innerHTML = '<div class="col-12 text-center py-5"><h3>No products found</h3><p class="text-muted">Try adjusting your search criteria.</p></div>';
        return;
    }
    products.forEach(p => {
      const col = document.createElement('div');
      col.className = 'col-sm-6 col-md-4 col-lg-3 wide-20 animate__animated animate__fadeIn';

      const imageUrl = (p.images && p.images.length) ? getBigUrl(p.images[0].url) : '/static/img/placeholder.webp';

      col.innerHTML = `
        <div class="card h-100 shadow-sm border-0 product-card overflow-hidden" style="border-radius: 0;">
            <a href="/product/${p.product_sku}" class="product-image-container d-block position-relative">
                <img src="${imageUrl}" class="card-img-top" alt="${p.name}" style="height: 350px; object-fit: cover; border-radius: 0;">
                <div class="product-overlay d-flex align-items-center justify-content-center opacity-0 transition">
                    <span class="btn btn-primary shadow">View Details</span>
                </div>
                <div class="position-absolute top-0 start-0 m-3 d-flex flex-column gap-2 wide-auto">
                    ${p.message ? `<span class="badge bg-info text-dark rounded-pill shadow-sm">${p.message}</span>` : ''}
                    ${(p.stock_quantity !== undefined && p.stock_quantity <= 5) ? '<span class="badge bg-danger rounded-pill shadow-sm">Low Stock</span>' : ''}
                </div>
            </a>
            <div class="card-body">
                <h5 class="card-title fw-bold mb-2" style="font-size: medium !important;">
                    <a href="/product/${p.product_sku}" class="text-decoration-none text-dark">${p.name}</a>
                </h5>
                <p class="card-text text-muted small mb-3 text-truncate-2">${p.short_description || ''}</p>
                <div class="d-flex justify-content-between align-items-center">
                    <span class="h5 fw-bold text-primary mb-0 product-price" data-base-price-cents="${p.base_price_cents}">${window.appConfig.currencySymbol}${(p.base_price_cents/100).toFixed(2)}</span>
                    <div class="text-warning">
                        ${renderStars(p.average_rating || 0)}
                        <span class="text-muted small ms-1" style="font-size: 0.8rem;">(${p.review_count || 0})</span>
                    </div>
                </div>
            </div>
        </div>
      `;
      grid.appendChild(col);
    });

    if (window.updateAllPrices) window.updateAllPrices();
  }

  function renderStars(rating) {
      let stars = '';
      for (let i = 1; i <= 5; i++) {
          if (rating >= i) stars += '<i class="bi bi-star-fill small"></i>';
          else if (rating >= i - 0.5) stars += '<i class="bi bi-star-half small"></i>';
          else stars += '<i class="bi bi-star small"></i>';
      }
      return stars;
  }

  // Initial Load
  if (grid) {
      loadProducts({ category: initialCategory, q: initialQ });
  }

  // Search Handler
  if (searchForm) {
      searchForm.addEventListener('submit', (e) => {
          if (grid) {
              e.preventDefault();
              const category = categorySelect ? categorySelect.value : '';
              const q = searchInput ? searchInput.value.trim() : '';
              loadProducts({ category, q });
          }
          // Natural submit to /shop if no grid
      });
  }

  // Auto-filter on category select
  if (categorySelect) {
      categorySelect.addEventListener('change', () => {
          const category = categorySelect.value;
          const q = searchInput ? searchInput.value.trim() : '';
          if (grid) {
              loadProducts({ category, q });
          } else {
              window.location.href = `/shop?category=${encodeURIComponent(category)}&q=${encodeURIComponent(q)}`;
          }
      });
  }
});
