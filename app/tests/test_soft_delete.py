import pytest
from app.app import create_app, setup_database
from app.extensions import db
from app.models import Product, User

@pytest.fixture
def app():
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test",
        "RATELIMIT_ENABLED": False,
        "CACHE_TYPE": "NullCache",
        "APP_ADMIN_EMAIL": "admin@example.com",
        "APP_ADMIN_PASSWORD": "password"
    }
    app = create_app(test_config)
    with app.app_context():
        db.create_all()
        setup_database(app)
        yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_client(client, app):
    with app.app_context():
        # Ensure admin exists
        pass
    client.post('/login', data={'email': 'admin@example.com', 'password': 'password'}, follow_redirects=True)
    return client

def test_soft_delete(auth_client, client, app):
    sku = "SOFT-DELETE-TEST"

    # 1. Create a product
    with app.app_context():
        p = Product(product_sku=sku, name="Soft Delete Item", base_price_cents=1000, status='published')
        db.session.add(p)
        db.session.commit()

    # 2. Check it appears in public list
    res = client.get('/api/products')
    data = res.json
    assert any(p['product_sku'] == sku for p in data['products']), "Product should be visible initially"

    # 3. Soft delete via Admin API
    res = auth_client.delete(f'/api/admin/products/{sku}')
    assert res.status_code == 200
    assert "soft delete" in res.json['message'].lower()

    # Verify DB state directly
    with app.app_context():
        p = Product.query.filter_by(product_sku=sku).first()
        print(f"DEBUG: DB is_active = {p.is_active}")
        assert p.is_active is False, "Product is_active should be False in DB"

    # 4. Check it is GONE from public list
    res = client.get('/api/products')
    data = res.json

    found = [p for p in data['products'] if p['product_sku'] == sku]
    if found:
        print(f"DEBUG: Found product in public list: {found[0]}")
        print(f"DEBUG: Found product is_active: {found[0].get('is_active')}")

    assert not any(p['product_sku'] == sku for p in data['products']), "Product should NOT be visible after soft delete"

    # 5. Check it is STILL in Admin list
    res = auth_client.get('/api/admin/products')
    data = res.json
    assert any(p['product_sku'] == sku for p in data), "Product should still be visible to Admin"

    # 6. Verify status in Admin list
    deleted_prod = next(p for p in data if p['product_sku'] == sku)
    assert deleted_prod['is_active'] is False, "Product should be marked inactive"

    # 7. Reactivate
    res = auth_client.put(f'/api/admin/products/{sku}', json={'is_active': True})
    assert res.status_code == 200

    # 8. Check visible again
    res = client.get('/api/products')
    data = res.json
    assert any(p['product_sku'] == sku for p in data['products']), "Product should be visible after reactivation"
