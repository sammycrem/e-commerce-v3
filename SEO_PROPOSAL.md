# SEO Product Improvement Proposal for Google Search

This proposal outlines the recommended changes to improve the SEO (Search Engine Optimization) of the E-Commerce Pro application, focusing on product pages to enhance visibility in Google Search results.

## 1. Dynamic Meta Tags

Currently, the application uses a static title `{% block title %}My Shop{% endblock %}` in `layout.html` and a simple override in `product_detail.html`. To improve SEO, we need to ensure that every page has unique, descriptive meta tags relevant to its content.

**Proposed Changes:**

*   **Page Titles:** Update `product_detail.html` to generate titles like: `{{ product.name }} - {{ product.category }} | E-Commerce Pro`.
*   **Meta Description:** Add a `<meta name="description">` tag. For product pages, this should be populated with the product's `short_description` or a truncated version of the full description.
*   **Keywords (Optional):** While less critical for Google, adding a `<meta name="keywords">` tag populated with product tags can be beneficial for other engines.

**Implementation Plan:**
- Modify `layout.html` to accept `meta_description` and `meta_keywords` blocks.
- Update `product_detail.html` to populate these blocks using product data.

## 2. Structured Data (JSON-LD)

Google uses structured data to understand the content of the page and to generate Rich Snippets (e.g., displaying price, availability, and review ratings directly in search results).

**Proposed Changes:**

*   Implement `Schema.org/Product` markup in `product_detail.html`.
*   Include the following properties:
    *   `name`: Product Name
    *   `image`: URL of the main product image
    *   `description`: Short description
    *   `sku`: Product SKU
    *   `offers`:
        *   `@type`: "Offer"
        *   `url`: Canonical URL of the product
        *   `priceCurrency`: Currency code (e.g., "EUR", "USD")
        *   `price`: Base price (converted from cents)
        *   `availability`: "http://schema.org/InStock" (based on stock quantity)
    *   `aggregateRating` (if reviews exist):
        *   `ratingValue`: Average rating
        *   `reviewCount`: Number of reviews

**Implementation Plan:**
- Add a `<script type="application/ld+json">` block in `product_detail.html` that dynamically constructs this JSON object.

## 3. Canonical URLs

Canonical tags prevent duplicate content issues, which can arise if the same product is accessible via multiple URLs (e.g., with different query parameters).

**Proposed Changes:**

*   Add a `<link rel="canonical" href="...">` tag in the `<head>` of `layout.html`.
*   In `product_detail.html`, set this to the clean, absolute URL of the product page (e.g., `https://example.com/product/SKU-123`).

## 4. Open Graph & Twitter Card Tags

These tags control how content appears when shared on social media (Facebook, Twitter, LinkedIn, etc.), which drives traffic and signals relevance.

**Proposed Changes:**

*   Add standard OG tags in `layout.html` / `product_detail.html`:
    *   `og:title`: Product Name
    *   `og:description`: Short Description
    *   `og:image`: Main Image URL
    *   `og:url`: Canonical URL
    *   `og:type`: "product"

## 5. XML Sitemap

A sitemap helps Googlebot discover and index pages more efficiently.

**Proposed Changes:**

*   Create a new route `/sitemap.xml` in the Flask application.
*   Dynamically generate XML listing all active product URLs, category pages, and static pages (Home, Shop, Contact).
*   Add the sitemap URL to `robots.txt`.

## 6. URL Structure & Performance

*   **URL Structure:** The current structure `/product/<sku>` is good. Ensure SKUs are URL-friendly (already enforced by new creation rules).
*   **Image Optimization:** Continue ensuring all images are served in modern formats (WebP) and properly sized (already implemented with `_icon` logic). Add `alt` text to all images (already in schema, ensure it's in HTML `<img>` tags).

## Summary of Immediate Action Items

1.  Update `layout.html` to support dynamic meta tags and structured data blocks.
2.  Update `product_detail.html` to inject Product Schema JSON-LD and SEO-friendly meta tags.
3.  Create a sitemap generator route.

This proposal sets the foundation for a significant improvement in organic search visibility.
