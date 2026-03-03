import pytest
from app.models import Product
from app.extensions import db

def test_admin_product_search(authenticated_client):
    # Setup: ensure we have some products
    p1 = Product(product_sku="SEARCH-1", name="Alpha Product", status="published", category="Test", base_price_cents=1000)
    p2 = Product(product_sku="SEARCH-2", name="Beta Item", status="published", category="Test", base_price_cents=1000)
    p3 = Product(product_sku="SEARCH-3", name="Gamma Product", status="draft", category="Test", base_price_cents=1000)
    db.session.add_all([p1, p2, p3])
    db.session.commit()

    # Search for "Product"
    response = authenticated_client.get('/api/admin/products?q=Product')
    assert response.status_code == 200
    data = response.get_json()
    names = [p['name'] for p in data]
    assert "Alpha Product" in names
    assert "Gamma Product" in names
    assert "Beta Item" not in names

    # Search for "Alpha"
    response = authenticated_client.get('/api/admin/products?q=Alpha')
    assert response.status_code == 200
    data = response.get_json()
    names = [p['name'] for p in data]
    assert "Alpha Product" in names
    assert len(data) == 1

    # Search with status filter
    response = authenticated_client.get('/api/admin/products?q=Product&status=published')
    assert response.status_code == 200
    data = response.get_json()
    names = [p['name'] for p in data]
    assert "Alpha Product" in names
    assert "Gamma Product" not in names
