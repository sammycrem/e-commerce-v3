// index.js - loads product list and injects into #product-grid
function getBigUrl(url) {
  if (!url || !url.includes('/static/')) return url;
  const dotIdx = url.lastIndexOf('.');
  const base = dotIdx !== -1 ? url.substring(0, dotIdx) : url;
  if (base.endsWith('_big')) return url;
  return base + '_big.webp';
}

function getIconUrl(url) {
  if (!url || !url.includes('/static/')) return url;
  const dotIdx = url.lastIndexOf('.');
  const base = dotIdx !== -1 ? url.substring(0, dotIdx) : url;
  if (base.endsWith('_icon')) return url;
  return base + '_icon.webp';
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
              const val = c.slug || c.name;
              // Avoid duplicates if Jinja2 partially populated or something
              if (![...categorySelect.options].some(opt => opt.value === val)) {
                  const opt = document.createElement('option');
                  opt.value = val;
                  opt.textContent = c.name;
                  categorySelect.appendChild(opt);
              }
          });
      } catch (err) {
          console.error('Failed to load categories', err);
      }
  }

  // Check URL params and path for initial state
  const urlParams = new URLSearchParams(window.location.search);
  let initialCategory = urlParams.get('category');
  let initialGroupId = urlParams.get('group_id');
  const initialQ = urlParams.get('q');

  const path = window.location.pathname;
  if (path.includes('/shop/category/')) {
      initialCategory = decodeURIComponent(path.split('/shop/category/')[1]);
  } else if (path.includes('/shop/group/')) {
      initialGroupId = decodeURIComponent(path.split('/shop/group/')[1]);
  }

  if (categorySelect) {
      if (initialGroupId) {
          categorySelect.value = `group:${initialGroupId}`;
      } else if (initialCategory) {
          categorySelect.value = initialCategory;
      }
  }
  if (initialQ && searchInput) {
      searchInput.value = initialQ;
  }

  // Simple in-memory cache for product queries
  const productsCache = new Map();

  async function loadProducts(filters = {}) {
      if (!grid) return 0;

      const perPage = filters.per_page || 100;
      const params = new URLSearchParams({ per_page: perPage });

      if (filters.category) {
          if (filters.category.startsWith('group:')) {
              const val = filters.category.split(':')[1];
              if (isNaN(val)) params.append('group_slug', val);
              else params.append('group_id', val);
          } else {
              params.append('category', filters.category);
          }
      } else if (filters.group_id) {
          if (isNaN(filters.group_id)) params.append('group_slug', filters.group_id);
          else params.append('group_id', filters.group_id);
      }

      if (filters.q) params.append('q', filters.q);

      const cacheKey = params.toString();
      if (productsCache.has(cacheKey)) {
          const cachedData = productsCache.get(cacheKey);
          renderProducts(cachedData.products);
          return cachedData.products.length;
      }

      // Only show spinner if not already present and not in cache
      if (!grid.querySelector('.spinner-border')) {
          grid.innerHTML = '<div class="col-12 text-center py-5"><div class="spinner-border text-primary" role="status"></div></div>';
      }
      try {
        const res = await fetch(`/api/products?${params.toString()}`, { credentials: 'same-origin' });
        const data = await res.json();
        const products = data.products || [];

        // Cache the results
        productsCache.set(cacheKey, { products, timestamp: Date.now() });

        renderProducts(products);
        return products.length;
      } catch (err) {
        console.error(err);
        grid.innerHTML = '<div class="col-12 text-center py-5"><h3>Error loading products</h3><p>Please try again later.</p></div>';
        return 0;
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

      // Use icon URL for thumbnails in the grid for better performance
      const imageUrl = (p.images && p.images.length) ? getIconUrl(p.images[0].url) : '/static/img/placeholder.webp';

      col.innerHTML = `
        <div class="card h-100 shadow-sm border-0 product-card overflow-hidden" style="border-radius: 0;">
            <a href="/product/${p.product_sku}" class="product-image-container d-block position-relative">
                <img src="${imageUrl}" class="card-img-top" alt="${p.name}" style="height: 350px; object-fit: cover; border-radius: 0;" loading="lazy">
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
          const val = categorySelect.value;
          const q = searchInput ? searchInput.value.trim() : '';

          // For SEO and consistency, we redirect to the landing page of the category/group
          // except if we are already on a shop page and just want to filter (though redirection is still fine)
          // We'll redirect if q is present anyway to show results

          let url = '';
          if (val.startsWith('group:')) {
              const groupSlug = val.split(':')[1];
              url = `/shop/group/${encodeURIComponent(groupSlug)}`;
          } else if (val) {
              url = `/shop/category/${encodeURIComponent(val)}`;
          } else {
              url = '/shop';
          }

          if (q) {
              url += (url.includes('?') ? '&' : '?') + `q=${encodeURIComponent(q)}`;
          }
          window.location.href = url;
      });
  }

  // Initial Load
  if (grid) {
      const isHomePage = window.location.pathname === '/' || window.location.pathname === '/index';
      const noFilters = !initialCategory && !initialGroupId && !initialQ;

      // Skip initial AJAX load if products are already server-rendered (prevents double-load flicker)
      if (grid.querySelector('.product-card')) {
          return;
      }

      if (isHomePage && noFilters) {
          // Home page default behavior: Performance first, curated SEO content
          // Try loading featured collection (curated), fallback to all products if empty.
          loadProducts({ group_id: 'featured-collection', per_page: 8 }).then(count => {
              const heading = document.querySelector('#featured-products h2');
              if (count === 0) {
                  // Fallback to all products (legacy behavior)
                  loadProducts({ per_page: 8 });
                  if (heading) heading.textContent = 'Our Collection';
              } else {
                  if (heading) heading.textContent = 'Featured Collection';
              }
          });
      } else {
          loadProducts({
              category: initialCategory,
              group_id: initialGroupId,
              q: initialQ
          });
      }
  }
});
