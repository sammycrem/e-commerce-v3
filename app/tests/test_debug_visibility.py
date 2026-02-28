import pytest
from app.app import create_app, db
from app.models import Product, User, Order, OrderItem, Variant
from werkzeug.security import generate_password_hash
import os

@pytest.fixture
def app():
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test",
        "WTF_CSRF_ENABLED": False,
        "APP_SESSION_TYPE": None
    }
    if not os.environ.get('ENCRYPTION_KEY'):
        os.environ['ENCRYPTION_KEY'] = 'testkey123456789012345678901234567890='
    app = create_app(test_config)
    with app.app_context():
        db.create_all()
        u = User(username='buyer', email='buyer@e.com', user_id='b1', password=generate_password_hash('p'), encrypted_password='e')
        db.session.add(u)
        db.session.flush()
        p = Product(product_sku='P1', name='P1', base_price_cents=100, status='published')
        db.session.add(p)
        db.session.flush()
        v = Variant(sku='V1', product_id=p.id, stock_quantity=10)
        db.session.add(v)
        db.session.flush()
        o = Order(user_id=u.id, status='PAID', total_cents=100)
        db.session.add(o)
        db.session.flush()
        oi = OrderItem(order_id=o.id, variant_sku='V1', quantity=1, unit_price_cents=100, product_snapshot={})
        db.session.add(oi)
        db.session.commit()
    return app

def test_visibility(app):
    client = app.test_client()
    # Login
    client.post('/login', data={'email': 'buyer@e.com', 'password': 'p'})
    # Check page
    res = client.get('/product/P1')
    assert res.status_code == 200
    assert b'id="review-form-container"' in res.data
