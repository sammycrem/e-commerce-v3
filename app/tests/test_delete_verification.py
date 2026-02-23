import pytest
from app.app import create_app, setup_database
from app.extensions import db
from app.models import Product, Order, OrderItem, Variant
from flask import json

@pytest.fixture
def app():
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test",
        "RATELIMIT_ENABLED": False
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
    # Authenticate via login endpoint to ensure session is correctly set
    from app.models import User
    with app.app_context():
        # Ensure admin exists (it should via setup_database)
        admin = User.query.filter_by(username='admin').first()
        # Verify password is 'password' (default in seeder)

    client.post('/login', data={'email': 'admin@example.com', 'password': 'adminpass'}, follow_redirects=True)
    return client

def test_delete_product_with_order(auth_client, app):
    # 1. Create a product with a variant
    product_sku = "DEL-TEST-PROD"
    variant_sku = "DEL-TEST-VAR"

    with app.app_context():
        p = Product(product_sku=product_sku, name="Delete Test", base_price_cents=1000)
        db.session.add(p)
        db.session.flush()
        v = Variant(product_id=p.id, sku=variant_sku, stock_quantity=10)
        db.session.add(v)
        db.session.commit()

        # 2. Create an order with this product
        o = Order(user_id=1, total_cents=1000)
        db.session.add(o)
        db.session.flush()
        item = OrderItem(
            order_id=o.id,
            variant_sku=variant_sku,
            quantity=1,
            unit_price_cents=1000,
            product_snapshot={"name": "Delete Test"}
        )
        db.session.add(item)
        db.session.commit()
        order_id = o.public_order_id

    # 3. Delete the product via API
    res = auth_client.delete(f'/api/admin/products/{product_sku}')
    assert res.status_code == 200, f"Delete failed: {res.json}"

    # 4. Verify product is soft deleted
    with app.app_context():
        p = Product.query.filter_by(product_sku=product_sku).first()
        assert p is not None
        assert p.is_active is False
        # Variants remain but are effectively inactive via parent
        assert Variant.query.filter_by(sku=variant_sku).first() is not None

    # 5. Verify Order still exists and has items
    with app.app_context():
        o = Order.query.filter_by(public_order_id=order_id).first()
        assert o is not None
        assert len(o.items) == 1
        assert o.items[0].variant_sku == variant_sku
        print("\nVerification Successful: Product deleted, Order remains intact.")
