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
        # Create User
        user = User(
            username='user1',
            email='user1@example.com',
            user_id='user_1',
            password=generate_password_hash('password'),
            encrypted_password='encrypted_dummy'
        )
        db.session.add(user)

        # Create Product
        p = Product(
            product_sku='TEST-SKU',
            name='Test Product',
            base_price_cents=1000,
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
    client.post('/login', data={'email': 'user1@example.com', 'password': 'password'})
    return client

def test_add_review(auth_client, app):
    """Test adding a review"""
    res = auth_client.post('/api/products/TEST-SKU/reviews', json={
        'rating': 5,
        'comment': 'Great product!'
    })
    assert res.status_code == 201
    data = res.json
    assert data['rating'] == 5
    assert data['comment'] == 'Great product!'
    assert data['user_name'] == 'user1'

    # Check DB
    with app.app_context():
        r = Review.query.first()
        assert r is not None
        assert r.rating == 5
        assert r.comment == 'Great product!'

def test_get_reviews(client, auth_client, app):
    """Test retrieving reviews"""
    # First add a review
    auth_client.post('/api/products/TEST-SKU/reviews', json={
        'rating': 4,
        'comment': 'Pretty good'
    })

    # Get reviews (public)
    res = client.get('/api/products/TEST-SKU/reviews')
    assert res.status_code == 200
    data = res.json
    assert len(data) == 1
    assert data[0]['rating'] == 4
    assert data[0]['comment'] == 'Pretty good'

def test_duplicate_review(auth_client, app):
    """Test preventing duplicate reviews from same user"""
    res1 = auth_client.post('/api/products/TEST-SKU/reviews', json={'rating': 5, 'comment': 'First'})
    assert res1.status_code == 201

    res2 = auth_client.post('/api/products/TEST-SKU/reviews', json={'rating': 1, 'comment': 'Second'})
    assert res2.status_code == 409 # Conflict
    assert "already reviewed" in res2.json['error']

def test_invalid_rating(auth_client, app):
    """Test rating validation"""
    res = auth_client.post('/api/products/TEST-SKU/reviews', json={'rating': 6, 'comment': 'Bad'})
    assert res.status_code == 400
    assert "between 1 and 5" in res.json['error']
