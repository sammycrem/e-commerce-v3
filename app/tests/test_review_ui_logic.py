import pytest
from app.app import create_app, db
from app.models import Product, User, Review
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
        user = User(username='u', email='u@e.com', user_id='uid', password=generate_password_hash('p'), encrypted_password='e')
        db.session.add(user)
        p = Product(product_sku='P-1', name='Prod 1', base_price_cents=100, is_active=True)
        db.session.add(p)
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture
def auth_client(app):
    client = app.test_client()
    client.post('/login', data={'email': 'u@e.com', 'password': 'p'})
    return client

def test_product_page_no_review(auth_client):
    """Verify Write Review form is present when no review exists"""
    res = auth_client.get('/product/P-1')
    assert res.status_code == 200
    assert b'Write a Review' in res.data
    assert b'Update Your Review' not in res.data

def test_product_page_with_review(auth_client, app):
    """Verify Update UI is present when review exists"""
    with app.app_context():
        p = Product.query.first()
        u = User.query.first()
        r = Review(user_id=u.id, product_id=p.id, rating=5, comment="Existing")
        db.session.add(r)
        db.session.commit()

    res = auth_client.get('/product/P-1')
    assert res.status_code == 200
    assert b'You have already reviewed this product.' in res.data
    assert b'Edit Review' in res.data
    assert b'Update Your Review' in res.data
    assert b'data-method="PUT"' in res.data
    assert b'Existing' in res.data # Comment pre-filled
