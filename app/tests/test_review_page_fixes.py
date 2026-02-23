import pytest
from app.app import create_app, db
from app.models import Product, ProductImage, User, Order, OrderItem
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

        # Product with image
        p = Product(product_sku='P-1', name='Prod 1', base_price_cents=100, is_active=True)
        db.session.add(p)
        db.session.flush()
        img = ProductImage(product_id=p.id, url='/static/img.webp', display_order=0)
        db.session.add(img)
        db.session.commit()

        # Legacy Order: Snapshot has NO images
        o = Order(public_order_id='ORD-LEGACY', user_id=user.id, total_cents=100)
        db.session.add(o)
        db.session.flush()

        # Item snapshot intentionally missing 'images'
        item_snapshot = {
            "product_sku": "P-1",
            "name": "Prod 1",
            "variants": [{"color_name": "Red", "size": "M"}]
            # No images here
        }

        oi = OrderItem(order_id=o.id, variant_sku='P-1-VAR', quantity=1, unit_price_cents=100, product_snapshot=item_snapshot)
        db.session.add(oi)
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

def test_legacy_order_image_augmentation(auth_client):
    """Test that the review page augments legacy orders with current product images"""
    res = auth_client.get('/account/orders/ORD-LEGACY/reviews')
    assert res.status_code == 200
    # The template renders <img src="..."> if image is found.
    # My logic adds the image from DB to the snapshot.
    # So we expect to see the image URL in the response HTML.
    assert b'/static/img_icon.webp' in res.data or b'/static/img.webp' in res.data
    # Logic uses utils.serialize_image -> utils.icon_url filter -> "img_icon.webp" usually
