import pytest
from app.app import create_app, db
from app.models import Product, User, Review, Order, OrderItem
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
        # User who bought
        buyer = User(username='buyer', email='buyer@e.com', user_id='buyer', password=generate_password_hash('p'), encrypted_password='e')
        db.session.add(buyer)

        # User who did NOT buy
        visitor = User(username='visitor', email='visitor@e.com', user_id='visitor', password=generate_password_hash('p'), encrypted_password='e')
        db.session.add(visitor)

        p = Product(product_sku='P-1', name='Prod 1', base_price_cents=100, is_active=True)
        db.session.add(p)
        db.session.flush()

        # Order for buyer
        o = Order(public_order_id='ORD-1', user_id=buyer.id, total_cents=100)
        db.session.add(o)
        db.session.flush()

        # We need a Variant linked to the product for the check to work
        # My logic checks OrderItem.variant_sku in [p.variants.sku]
        from app.models import Variant
        v = Variant(product_id=p.id, sku='P-1-VAR', stock_quantity=10, price_modifier_cents=0)
        db.session.add(v)
        db.session.flush()

        oi = OrderItem(order_id=o.id, variant_sku='P-1-VAR', quantity=1, unit_price_cents=100, product_snapshot={})
        db.session.add(oi)
        db.session.commit()

    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture
def buyer_client(app):
    client = app.test_client()
    client.post('/login', data={'email': 'buyer@e.com', 'password': 'p'})
    return client

@pytest.fixture
def visitor_client(app):
    client = app.test_client()
    client.post('/login', data={'email': 'visitor@e.com', 'password': 'p'})
    return client

def test_review_permission_allowed(buyer_client):
    """Test that a buyer can review"""
    res = buyer_client.post('/api/products/P-1/reviews', json={'rating': 5, 'comment': 'Good'})
    assert res.status_code == 201

def test_review_permission_denied(visitor_client):
    """Test that a non-buyer cannot review"""
    res = visitor_client.post('/api/products/P-1/reviews', json={'rating': 5, 'comment': 'Fake'})
    assert res.status_code == 403
    assert "must purchase" in res.json['error']

def test_product_page_visibility(buyer_client, visitor_client):
    """Test that the review form visibility logic is correct in HTML"""
    # Buyer sees form
    res = buyer_client.get('/product/P-1')
    assert b'Write a Review' in res.data
    assert b'must purchase' not in res.data

    # Visitor sees NOTHING (hidden entirely)
    res = visitor_client.get('/product/P-1')
    assert b'Write a Review' not in res.data
    assert b'must purchase' not in res.data
