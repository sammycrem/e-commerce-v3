import pytest
from app.app import create_app, db
from app.models import Product, User, Review, Order, OrderItem, Variant
from werkzeug.security import generate_password_hash
import os

@pytest.fixture
def app():
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "CACHE_TYPE": "NullCache",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test",
        "APP_SESSION_TYPE": None
    }
    if not os.environ.get('ENCRYPTION_KEY'):
        os.environ['ENCRYPTION_KEY'] = 'l5AiZmyB1v_A6bu-drJ6AhxynGNjj5rlWA8gx3K-29U='

    app = create_app(test_config)
    with app.app_context():
        db.create_all()
        # Visitor (ID 1)
        visitor = User(username='visitor', email='visitor@e.com', user_id='visitor', password=generate_password_hash('p'), encrypted_password='e')
        db.session.add(visitor)
        # Buyer (ID 2)
        buyer = User(username='buyer', email='buyer@e.com', user_id='buyer', password=generate_password_hash('p'), encrypted_password='e')
        db.session.add(buyer)
        db.session.commit()

        p = Product(product_sku='P-1', name='Prod 1', base_price_cents=100, is_active=True, status='published')
        db.session.add(p)
        db.session.flush()

        v = Variant(product_id=p.id, sku='P-1-VAR', stock_quantity=10)
        db.session.add(v)
        db.session.flush()

        o = Order(public_order_id='ORD-1', user_id=buyer.id, total_cents=100, status='PAID')
        db.session.add(o)
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
    res = client.post('/login', data={'email': 'buyer@e.com', 'password': 'p'})
    assert res.status_code == 302
    return client

@pytest.fixture
def visitor_client(app):
    client = app.test_client()
    res = client.post('/login', data={'email': 'visitor@e.com', 'password': 'p'})
    assert res.status_code == 302
    return client

def test_review_permission_allowed(buyer_client):
    res = buyer_client.post('/api/products/P-1/reviews', json={'rating': 5, 'comment': 'Good'})
    assert res.status_code == 201

def test_review_permission_denied(visitor_client):
    res = visitor_client.post('/api/products/P-1/reviews', json={'rating': 5, 'comment': 'Fake'})
    assert res.status_code == 403

def test_product_page_visibility(app):
    client = app.test_client()
    # Login buyer
    res_login = client.post('/login', data={'email': 'buyer@e.com', 'password': 'p'})
    assert res_login.status_code == 302

    res = client.get('/product/P-1')
    assert res.status_code == 200
    assert b'review-form-container' in res.data

    # Login visitor
    res_login_v = client.post('/login', data={'email': 'visitor@e.com', 'password': 'p'})
    assert res_login_v.status_code == 302
    res = client.get('/product/P-1')
    assert res.status_code == 200
    assert b'must purchase' in res.data
    assert b'review-form-container' not in res.data
