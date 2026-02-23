import pytest
from app.models import Order, User, Product, Promotion, GlobalSetting
from app.extensions import db
from app.utils import process_loyalty_reward, encrypt_password
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone
import os

def test_loyalty_program(client, app):
    with app.app_context():
        # 1. Setup Settings
        s1 = GlobalSetting(key='loyalty_enabled', value='True')
        s2 = GlobalSetting(key='loyalty_percentage', value='10') # 10%
        db.session.add_all([s1, s2])

        # Setup User
        # Need encryption key for encrypt_password
        enc_key = os.environ.get('ENCRYPTION_KEY') or 'VMzJvnz8S36yhK0CTx08v63hx4Py_yTTs85xHE6usFo=' # Default from conftest logic?

        u = User(
            username='loyalty_user',
            email='loyalty@test.com',
            user_id='loyalty_u1',
            password=generate_password_hash('pass'),
            encrypted_password=encrypt_password('pass', enc_key)
        )
        db.session.add(u)
        db.session.commit()

        # Setup Order
        # Net = 120 - 20 - 10 = 90.00
        # 10% of 90 = 9.00 -> 900 cents.

        o = Order(
            public_order_id='ORD-LOYALTY-1',
            user_id=u.id,
            status='PAID',
            total_cents=12000,
            vat_cents=2000,
            shipping_cost_cents=1000,
            subtotal_cents=9000,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(o)
        db.session.commit()

        # 2. Process Reward
        process_loyalty_reward(o)

        # 3. Verify
        promos = Promotion.query.filter_by(user_id=u.id).all()
        assert len(promos) == 1
        p = promos[0]
        assert p.code == 'LOYALTY-ORD-LOYALTY-1'
        assert p.discount_type == 'FIXED'
        assert p.discount_value == 900

        # 4. Idempotency check
        process_loyalty_reward(o)
        promos = Promotion.query.filter_by(user_id=u.id).all()
        assert len(promos) == 1

def test_loyalty_disabled(client, app):
    with app.app_context():
        s1 = GlobalSetting(key='loyalty_enabled', value='False')
        db.session.add(s1)

        enc_key = os.environ.get('ENCRYPTION_KEY') or 'VMzJvnz8S36yhK0CTx08v63hx4Py_yTTs85xHE6usFo='

        u = User(
            username='loyalty_user2',
            email='loyalty2@test.com',
            user_id='loyalty_u2',
            password=generate_password_hash('pass'),
            encrypted_password=encrypt_password('pass', enc_key)
        )
        db.session.add(u)
        db.session.commit()

        o = Order(
            public_order_id='ORD-LOYALTY-2',
            user_id=u.id,
            status='PAID',
            total_cents=10000,
            vat_cents=0,
            shipping_cost_cents=0
        )
        db.session.add(o)
        db.session.commit()

        process_loyalty_reward(o)

        promos = Promotion.query.filter_by(user_id=u.id).all()
        assert len(promos) == 0
