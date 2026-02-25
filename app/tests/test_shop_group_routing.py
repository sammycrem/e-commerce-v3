import pytest
from app.models import Product, ProductGroup

def test_shop_group_query_param(client, app):
    with app.app_context():
        # Create a group and products
        group = ProductGroup(name='Test Group', slug='test-group', is_active=True)
        p1 = Product(product_sku='P1', name='Product 1', base_price_cents=1000, status='published')
        p2 = Product(product_sku='P2', name='Product 2', base_price_cents=2000, status='published')
        group.products = [p1]

        from app.extensions import db
        db.session.add_all([group, p1, p2])
        db.session.commit()

        group_id = group.id
        p1_sku = p1.product_sku
        p2_sku = p2.product_sku

    # Test filtering by group:slug in category param
    response = client.get(f'/shop?category=group:test-group')
    assert response.status_code == 200
    html = response.data.decode()
    assert 'Product 1' in html
    assert 'Product 2' not in html
    assert 'Test Group' in html

    # Test filtering by invalid group:slug
    response = client.get(f'/shop?category=group:non-existent')
    assert response.status_code == 200
    # Should fallback to searching category "group:non-existent" which yields nothing
    html = response.data.decode()
    assert 'Product 1' not in html
    assert 'Product 2' not in html
