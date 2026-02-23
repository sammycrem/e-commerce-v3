import pytest
from app.models import GlobalSetting, Product, Variant, Country, Promotion
from app.extensions import db
from app.utils import calculate_totals_internal
from datetime import datetime, timezone
import json

def test_loyalty_summary_calculation(client, app):
    with app.app_context():
        # Setup settings
        db.session.query(GlobalSetting).delete()
        db.session.query(Country).delete()
        db.session.add(GlobalSetting(key='loyalty_enabled', value='True'))
        db.session.add(GlobalSetting(key='loyalty_percentage', value='10')) # 10%
        db.session.commit()

        # Create a product and variant
        p = Product(
            product_sku='PROD-LOY-1',
            name='Loyalty Test Product',
            base_price_cents=10000, # 100.00
            status='published'
        )
        db.session.add(p)
        db.session.commit()

        v = Variant(
            sku='PROD-LOY-1-L',
            product_id=p.id,
            price_modifier_cents=0,
            stock_quantity=100
        )
        db.session.add(v)

        # Create a default country for shipping
        c = Country(
            iso_code='US',
            name='United States',
            shipping_cost_cents=1000, # 10.00
            default_vat_rate=0.0, # No VAT for simplicity
            currency_code='USD'
        )
        db.session.add(c)
        db.session.commit()

        # Calculate totals
        items = [{'sku': 'PROD-LOY-1-L', 'quantity': 1}]

        # Scenario 1: No discount
        totals = calculate_totals_internal(items, shipping_country_iso='US')

        # Subtotal = 100.00
        # VAT = 0
        # Shipping = 10.00
        # Total = 110.00
        # Net for loyalty = Subtotal = 100.00
        # Reward = 10% of 100.00 = 10.00 = 1000 cents

        assert totals['subtotal_cents'] == 10000
        assert totals['loyalty_reward_cents'] == 1000

        # Scenario 2: With discount
        # Create a promo
        promo = Promotion(
            code='DISCOUNT10',
            discount_type='PERCENT',
            discount_value=10, # 10% off
            is_active=True,
            valid_to=datetime(2099, 1, 1, tzinfo=timezone.utc)
        )
        db.session.add(promo)
        db.session.commit()

        totals_discounted = calculate_totals_internal(items, shipping_country_iso='US', promo_code='DISCOUNT10')

        # Subtotal = 100.00
        # Discount = 10.00
        # Subtotal After Discount = 90.00
        # Net for loyalty = 90.00
        # Reward = 10% of 90.00 = 9.00 = 900 cents

        assert totals_discounted['subtotal_after_discount_cents'] == 9000
        assert totals_discounted['loyalty_reward_cents'] == 900

def test_loyalty_summary_disabled(client, app):
    with app.app_context():
        db.session.query(GlobalSetting).delete()
        db.session.query(Country).delete()
        db.session.add(GlobalSetting(key='loyalty_enabled', value='False'))
        db.session.commit()

        p = Product(product_sku='PROD-LOY-2', name='P2', base_price_cents=10000, status='published')
        db.session.add(p)
        db.session.commit()
        v = Variant(sku='PROD-LOY-2-L', product_id=p.id, price_modifier_cents=0, stock_quantity=10)
        db.session.add(v)
        c = Country(iso_code='DE', name='Germany', default_vat_rate=0.0)
        db.session.add(c)
        db.session.commit()

        items = [{'sku': 'PROD-LOY-2-L', 'quantity': 1}]
        totals = calculate_totals_internal(items, shipping_country_iso='DE')

        assert totals['loyalty_reward_cents'] == 0
