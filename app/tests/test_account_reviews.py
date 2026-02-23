import pytest
from app.app import create_app, db
from app.models import Product, User, Order, OrderItem
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
        user = User(
            username='user1',
            email='user1@example.com',
            user_id='user_1',
            password=generate_password_hash('password'),
            encrypted_password='encrypted_dummy'
        )
        db.session.add(user)

        product = Product(
            product_sku='TEST-SKU',
            name='Test Product',
            base_price_cents=1000,
            is_active=True
        )
        db.session.add(product)
        db.session.commit()

        # Create Order
        order = Order(
            public_order_id='ORD-TEST-123',
            user_id=user.id,
            status='DELIVERED',
            total_cents=1000
        )
        db.session.add(order)
        db.session.flush()

        item = OrderItem(
            order_id=order.id,
            variant_sku='TEST-SKU-VAR',
            quantity=1,
            unit_price_cents=1000,
            product_snapshot={'product_sku': 'TEST-SKU', 'name': 'Test Product', 'variants': [{'color_name': 'Red', 'size': 'M'}]}
        )
        db.session.add(item)
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
    client.post('/login', data={'email': 'user1@example.com', 'password': 'password'})
    return client

def test_review_order_page_access(auth_client, app):
    """Test accessing the review page for an order"""
    res = auth_client.get('/account/orders/ORD-TEST-123/reviews')
    assert res.status_code == 200
    assert b"Review Items" in res.data
    assert b"Test Product" in res.data

def test_review_submission_integration(auth_client, app):
    """Simulate the review submission flow from the page"""
    # Verify we can reach the review endpoint via the page's logic
    # (API itself was tested in test_reviews.py, this checks route availability)
    res = auth_client.post('/api/products/TEST-SKU/reviews', json={
        'rating': 5,
        'comment': 'Review from order page'
    })
    assert res.status_code == 201
