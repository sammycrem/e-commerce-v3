import pytest
from app.models import GlobalSetting, Promotion, Order, User
from app.extensions import db
from datetime import datetime, timezone
import os
from werkzeug.security import generate_password_hash
from app.utils import encrypt_password

def test_admin_accounting_route(client, app, authenticated_client):
    with app.app_context():
        # Test basic route existence
        resp = authenticated_client.get('/admin/accounting')
        assert resp.status_code == 200
        assert b'Reports' in resp.data
        assert b'active tab-button' in resp.data  # Should check if reports tab is active

def test_loyalty_trigger_on_admin_update(client, app, authenticated_client):
    with app.app_context():
        # Setup settings
        db.session.query(GlobalSetting).delete()
        db.session.add(GlobalSetting(key='loyalty_enabled', value='True'))
        db.session.add(GlobalSetting(key='loyalty_percentage', value='10'))
        db.session.commit()

        # Setup User for Order
        enc_key = os.environ.get('ENCRYPTION_KEY') or 'VMzJvnz8S36yhK0CTx08v63hx4Py_yTTs85xHE6usFo='
        u = User(username='test_user_loy', email='test_loy@test.com', user_id='uid_loy', password=generate_password_hash('pass'), encrypted_password=encrypt_password('pass', enc_key))
        db.session.add(u)
        db.session.commit()

        # Create Order (PENDING)
        o = Order(
            public_order_id='ORD-TEST-LOY-TRIGGER',
            user_id=u.id,
            status='PENDING',
            subtotal_cents=10000,
            total_cents=12000,
            vat_cents=2000,
            shipping_cost_cents=0,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(o)
        db.session.commit()

        # Verify no reward yet
        assert Promotion.query.filter_by(code='LOYALTY-ORD-TEST-LOY-TRIGGER').count() == 0

        # Admin Update to PAID
        resp = authenticated_client.put(f'/api/admin/orders/{o.public_order_id}/status', json={'status': 'PAID'})
        assert resp.status_code == 200

        # Verify reward created
        promo = Promotion.query.filter_by(code='LOYALTY-ORD-TEST-LOY-TRIGGER').first()
        assert promo is not None
        # Reward = 10% of (12000 - 2000 - 0) = 10000 * 0.1 = 1000 cents
        assert promo.discount_value == 1000

        # Test Idempotency (Update again)
        resp = authenticated_client.put(f'/api/admin/orders/{o.public_order_id}/status', json={'status': 'DELIVERED'})
        assert resp.status_code == 200
        assert Promotion.query.filter_by(code='LOYALTY-ORD-TEST-LOY-TRIGGER').count() == 1
