import pytest
from unittest.mock import patch
from app.models import Order, User, Address
from app.extensions import db
from datetime import datetime, timezone

def test_order_status_update_email_sent(authenticated_client, app):
    with patch('app.utils.send_emailTls2') as mock_send_email:
        with app.app_context():
            # 1. Setup: Create an order for the user
            admin_email = app.config.get('APP_ADMIN_EMAIL', 'admin@nomail.local')
            user = User.query.filter_by(email=admin_email).first()

            order = Order(
                user_id=user.id,
                public_order_id='ORD-TEST-STATUS',
                status='PENDING',
                total_cents=5000
            )
            db.session.add(order)
            db.session.commit()

            order_public_id = order.public_order_id
            user_email = user.email

        # 2. Configure email settings
        app.config['APP_EMAIL_SENDER'] = 'sender@example.com'
        app.config['APP_EMAIL_PASSWORD'] = 'secretpassword'

        # 3. Act: Update order status to SHIPPED via Admin API
        # We need to use the authenticated_client which represents the admin
        response = authenticated_client.put(f'/api/admin/orders/{order_public_id}/status', json={
            'status': 'SHIPPED'
        })

        # 4. Assert: Check if email was sent
        assert response.status_code == 200
        assert mock_send_email.called

        # Verify call arguments
        args, kwargs = mock_send_email.call_args
        # args: (sender, password, server, port, recipient, subject, body)
        assert args[4] == user_email
        assert "Order Update" in args[5]
        assert "Shipped" in args[6]
        assert order_public_id in args[6]

def test_order_shipment_update_email_sent(authenticated_client, app):
    with patch('app.utils.send_emailTls2') as mock_send_email:
        with app.app_context():
            admin_email = app.config.get('APP_ADMIN_EMAIL', 'admin@nomail.local')
            user = User.query.filter_by(email=admin_email).first()

            order = Order(
                user_id=user.id,
                public_order_id='ORD-TEST-SHIPMENT',
                status='PAID',
                total_cents=5000
            )
            db.session.add(order)
            db.session.commit()

            order_public_id = order.public_order_id
            user_email = user.email

        app.config['APP_EMAIL_SENDER'] = 'sender@example.com'
        app.config['APP_EMAIL_PASSWORD'] = 'secretpassword'

        # Act: Update shipment info and mark as shipped
        response = authenticated_client.put(f'/api/admin/orders/{order_public_id}/shipment', json={
            'shipping_provider': 'FedEx',
            'tracking_number': '123456789',
            'mark_as_shipped': True
        })

        assert response.status_code == 200
        assert mock_send_email.called

        args, kwargs = mock_send_email.call_args
        assert args[4] == user_email
        assert "Order Update" in args[5]
        assert "Shipped" in args[6]
