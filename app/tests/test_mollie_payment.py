import pytest
from unittest.mock import MagicMock, patch
from app.app import create_app
from app.extensions import db
from app.models import User, Order, Product, Variant, Address, Country
from flask import session

@pytest.fixture
def app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        db.create_all()
        # Seed necessary data
        country = Country(name="Testland", iso_code="TL", default_vat_rate=0.2, currency_code="EUR")
        db.session.add(country)

        user = User(username="testuser", email="test@example.com", user_id="testuser123", password="password", encrypted_password="encrypted")
        db.session.add(user)

        # Add Address
        address = Address(
            user=user,
            address_type='shipping',
            first_name='Test',
            last_name='User',
            address_line_1='123 Test St',
            city='Test City',
            postal_code='12345',
            country_iso_code='TL'
        )
        db.session.add(address)

        product = Product(product_sku="SKU1", name="Product 1", base_price_cents=1000)
        db.session.add(product)
        variant = Variant(product=product, sku="SKU1-V1", stock_quantity=10, price_modifier_cents=0)
        db.session.add(variant)

        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_checkout_mollie_redirect(client, app):
    with client.session_transaction() as sess:
        sess['_user_id'] = '1' # Mock login
        sess['cart'] = {'SKU1-V1': 1}
        sess['shipping_method'] = 'standard'
        sess['payment_method'] = 'mollie'

    # Mock get_mollie_client
    with patch('app.blueprints.checkout.get_mollie_client') as mock_get_client:
        mock_client_instance = MagicMock()
        mock_get_client.return_value = mock_client_instance

        mock_payment = MagicMock()
        mock_payment.checkout_url = "https://www.mollie.com/payscreen/select-method/7UhSN1zuXS"
        mock_payment.id = "tr_7UhSN1zuXS"
        mock_client_instance.payments.create.return_value = mock_payment

        # Trigger checkout summary POST
        response = client.post('/checkout/summary', data={'comment': 'Test order'}, follow_redirects=False)

        # Verify redirect
        assert response.status_code == 302
        assert response.location == "https://www.mollie.com/payscreen/select-method/7UhSN1zuXS"

        # Verify order created and payment ID stored
        order = Order.query.first()
        assert order is not None
        assert order.payment_transaction_id == "tr_7UhSN1zuXS"
        assert order.payment_method == "mollie"

def test_mollie_webhook_paid(client, app):
    # Create an order
    order = Order(public_order_id="ORD-123", status="PENDING", total_cents=1000)
    db.session.add(order)
    db.session.commit()

    with patch('app.blueprints.checkout.get_mollie_client') as mock_get_client:
        mock_client_instance = MagicMock()
        mock_get_client.return_value = mock_client_instance

        mock_payment = MagicMock()
        mock_payment.metadata = {'order_id': 'ORD-123'}
        mock_payment.is_paid.return_value = True
        mock_payment.is_canceled.return_value = False
        mock_payment.is_expired.return_value = False
        mock_payment.is_failed.return_value = False

        mock_client_instance.payments.get.return_value = mock_payment

        response = client.post('/webhooks/mollie', data={'id': 'tr_123'})

        assert response.status_code == 200

        # Verify order status updated
        db.session.refresh(order)
        assert order.status == "PAID"
