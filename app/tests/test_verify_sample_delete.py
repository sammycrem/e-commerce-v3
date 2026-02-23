import pytest
from app.app import create_app, db
from app.models import Product, User
from werkzeug.security import generate_password_hash
import os

@pytest.fixture
def app():
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "CACHE_TYPE": "NullCache",
        "WTF_CSRF_ENABLED": False,
        "APP_ADMIN_USER": "admin",
        "APP_SECRET_KEY": "test",
        "APP_SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "APP_SESSION_TYPE": "filesystem",
        "APP_SESSION_PERMANENT": "False",
        "APP_PERMANENT_SESSION_LIFETIME": "3600",
        "APP_ADMIN_EMAIL": "admin@example.com",
        "APP_ADMIN_PASSWORD": "admin"
    }
    app = create_app(test_config)

    if not os.environ.get('ENCRYPTION_KEY'):
        os.environ['ENCRYPTION_KEY'] = 'testkey123456789012345678901234567890='

    with app.app_context():
        db.create_all()
        # Create Admin User
        admin = User(
            username='admin',
            email='admin@example.com',
            user_id='admin_id_1',
            password=generate_password_hash('admin'),
            encrypted_password='encrypted_dummy'
        )
        db.session.add(admin)

        # Create Sample Product
        p = Product(
            product_sku='SAMPLE-SKU',
            name='Sample Product',
            base_price_cents=12345,
            is_active=True
        )
        db.session.add(p)
        db.session.commit()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_client(client):
    client.post('/login', data={'email': 'admin@example.com', 'password': 'admin'})
    return client

def test_delete_sample_product(auth_client, app):
    """
    Verify that the Admin Dashboard DELETE action (API endpoint)
    correctly soft-deletes the SAMPLE-SKU product.
    """

    # 1. Verify it exists and is active initially
    with app.app_context():
        p = Product.query.filter_by(product_sku='SAMPLE-SKU').first()
        assert p is not None
        assert p.is_active is True

    # 2. Perform Delete
    res = auth_client.delete('/api/admin/products/SAMPLE-SKU')

    # 3. Assert Response
    assert res.status_code == 200, f"Delete failed with status {res.status_code}: {res.text}"
    data = res.json
    assert "soft delete" in data.get("message", "").lower()

    # 4. Verify DB State (Soft Deleted)
    with app.app_context():
        p = Product.query.filter_by(product_sku='SAMPLE-SKU').first()
        assert p is not None
        assert p.is_active is False, "Product should be inactive (soft deleted)"
