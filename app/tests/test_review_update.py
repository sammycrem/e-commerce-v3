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

        # Add initial review
        review = Review(
            user_id=1, # assuming ID 1
            product_id=1,
            rating=3,
            comment="Initial review"
        )
        db.session.add(review)
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

def test_update_review(auth_client, app):
    """Test updating an existing review via PUT"""

    # 1. Update review
    res = auth_client.put('/api/products/TEST-SKU/reviews', json={
        'rating': 5,
        'comment': 'Updated review!'
    })

    assert res.status_code == 200
    data = res.json
    assert data['rating'] == 5
    assert data['comment'] == 'Updated review!'

    # 2. Verify DB
    with app.app_context():
        r = Review.query.first()
        assert r.rating == 5
        assert r.comment == 'Updated review!'

def test_update_nonexistent_review(auth_client, app):
    """Test updating a review that doesn't exist (should fail or create? Logic says fail for PUT usually, or we might restrict it)"""
    # But wait, my implementation finds by user_id+product_id.
    # If I delete the review first...
    with app.app_context():
        Review.query.delete()
        db.session.commit()

    res = auth_client.put('/api/products/TEST-SKU/reviews', json={
        'rating': 5,
        'comment': 'New review via PUT'
    })

    assert res.status_code == 404 # My impl returns 404 if review not found
