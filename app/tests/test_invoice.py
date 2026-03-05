import pytest
import io
from app.models import Order, User, OrderItem
from app.extensions import db

def test_download_invoice_permission_and_status(app, client):
    """
    Test that only the owner can download the invoice and only for paid orders.
    """
    with app.app_context():
        # Create a user
        user = User(username='testuser', email='test@example.com', password='pw', encrypted_password='pw', user_id='USR123')
        db.session.add(user)
        db.session.commit()

        # Create a paid order
        order = Order(
            public_order_id='ORD-PAID-001',
            user_id=user.id,
            status='PAID',
            subtotal_cents=1000,
            total_cents=1200
        )
        db.session.add(order)
        db.session.commit()

        # Create a pending order
        order_pending = Order(
            public_order_id='ORD-PENDING-001',
            user_id=user.id,
            status='PENDING',
            subtotal_cents=1000,
            total_cents=1200
        )
        db.session.add(order_pending)
        db.session.commit()

        user_id = user.id

    # 1. Log in
    with client.session_transaction() as sess:
        sess['_user_id'] = user_id
        sess['_fresh'] = True

    # 2. Try to download paid order invoice
    res = client.get(f'/account/orders/ORD-PAID-001/invoice')
    assert res.status_code == 200
    assert res.mimetype == 'application/pdf'
    assert 'attachment' in res.headers['Content-Disposition']

    # 3. Try to download pending order invoice (should fail/redirect)
    res = client.get(f'/account/orders/ORD-PENDING-001/invoice')
    assert res.status_code == 302
    assert '/account/orders/ORD-PENDING-001' in res.location

def test_download_invoice_unauthorized(app, client):
    """
    Test that a user cannot download someone else's invoice.
    """
    with app.app_context():
        # Create user A
        user_a = User(username='usera', email='a@example.com', password='pw', encrypted_password='pw', user_id='USRA')
        db.session.add(user_a)

        # Create user B
        user_b = User(username='userb', email='b@example.com', password='pw', encrypted_password='pw', user_id='USRB')
        db.session.add(user_b)
        db.session.commit()

        # Create order for A
        order_a = Order(
            public_order_id='ORD-A-001',
            user_id=user_a.id,
            status='PAID',
            total_cents=1000
        )
        db.session.add(order_a)
        db.session.commit()

        user_b_id = user_b.id

    # Log in as B
    with client.session_transaction() as sess:
        sess['_user_id'] = user_b_id
        sess['_fresh'] = True

    # Try to download A's invoice
    res = client.get(f'/account/orders/ORD-A-001/invoice')
    assert res.status_code == 404
