import pytest
from unittest.mock import patch
from app.models import Address, User, Variant
from app.extensions import db

def test_order_confirmation_email_sent(authenticated_client, app):
    with patch('app.blueprints.checkout.send_emailTls2') as mock_send_email:
        with app.app_context():
            # 1. Setup: Ensure we have a shipping address for the user
            admin_email = app.config.get('APP_ADMIN_EMAIL', 'admin@nomail.local')
            user = User.query.filter_by(email=admin_email).first()

            address = Address(
                user_id=user.id,
                address_type='shipping',
                first_name='Admin',
                last_name='User',
                address_line_1='123 Admin Way',
                city='Admin City',
                postal_code='12345',
                country_iso_code='FR'
            )
            db.session.add(address)
            db.session.commit()

            address_id = address.id # Store ID to avoid DetachedInstanceError
            user_email = user.email

            # Ensure variant exists (seeded in conftest.py)
            variant = Variant.query.filter_by(sku='TEST-SHIRT-BLK-M').first()

        # 2. Setup: Cart in session
        with authenticated_client.session_transaction() as sess:
            sess['cart'] = {'TEST-SHIRT-BLK-M': 1}
            sess['shipping_address_id'] = address_id
            sess['shipping_method'] = 'standard'
            sess['payment_method'] = 'bank_transfer'

        # 3. Configure email settings in app config for the test
        app.config['APP_EMAIL_SENDER'] = 'sender@example.com'
        app.config['APP_EMAIL_PASSWORD'] = 'secretpassword'
        app.config['APP_SMTP_SERVER'] = 'smtp.example.com'
        app.config['APP_SMTP_PORT'] = '587'

        # 4. Act: Place the order
        response = authenticated_client.post('/checkout/summary', data={
            'terms': 'on',
            'privacy': 'on',
            'comment': 'Test order'
        }, follow_redirects=True)

        # 5. Assert: Check if email was sent
        assert response.status_code == 200
        assert mock_send_email.called

        # Verify call arguments
        args, kwargs = mock_send_email.call_args
        # args: (sender, password, server, port, recipient, subject, body)
        assert args[0] == 'sender@example.com'
        assert args[1] == 'secretpassword'
        assert args[4] == user_email
        assert "Order Confirmation" in args[5]
        assert "TEST-SHIRT-BLK-M" in args[6]
        assert "1" in args[6] # quantity
