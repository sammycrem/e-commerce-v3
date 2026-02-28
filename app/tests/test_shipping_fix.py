import pytest
from app.app import app, db
from app.models import Product, Variant, ShippingZone, Country
from app.utils import calculate_totals_internal

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    # Disable automatic seeding from app.py if possible,
    # but since it's called at module level it already ran.
    # Actually, setup_database uses app.app_context() which might use the default DB if not careful.

    with app.app_context():
        db.create_all()
        # Use a country NOT in the Country table to test ShippingZone fallback
        Country.query.filter_by(iso_code='ZZ').delete()

        # Clear existing zones for clean test
        ShippingZone.query.delete()

        zone_eu = ShippingZone(
            name='Europe',
            countries_json=['ZZ'],
            base_cost_cents=1000,
            cost_per_kg_cents=2000,
            volumetric_divisor=5000,
            free_shipping_threshold_cents=10000 # €100
        )
        db.session.add(zone_eu)

        # Clear products and variants
        from app.models import Variant
        Variant.query.delete()
        Product.query.delete()

        p = Product(
            product_sku='P1',
            name='Test Product',
            base_price_cents=5000, # €50
            weight_grams=1000, # 1kg
            status='published'
        )
        db.session.add(p)
        db.session.flush()

        v = Variant(sku='V1', product_id=p.id, stock_quantity=10, price_modifier_cents=0)
        db.session.add(v)
        db.session.commit()

        yield app.test_client()

def test_shipping_calculation(client):
    with app.app_context():
        # 1. Standard shipping, below threshold
        # Subtotal: €50. Weight: 1kg. Base cost: €10 + €20*1 = €30. Total: €50 + €30 + VAT.
        items = [{'sku': 'V1', 'quantity': 1}]
        res = calculate_totals_internal(items, shipping_country_iso='ZZ', shipping_method='standard')
        assert res['subtotal_cents'] == 5000
        assert res['base_shipping_cost_cents'] == 3000
        assert res['shipping_cost_cents'] == 3000

        # 2. Standard shipping, above threshold
        # Subtotal: €150 (> €100). Shipping should be 0.
        items = [{'sku': 'V1', 'quantity': 3}]
        res = calculate_totals_internal(items, shipping_country_iso='ZZ', shipping_method='standard')
        assert res['subtotal_cents'] == 15000
        assert res['shipping_cost_cents'] == 0

        # 3. Express shipping, above threshold
        # Subtotal: €150. Shipping should NOT be 0.
        # Base cost for 3kg: €10 + €20*3 = €70. Express modifier: *1.25 = €87.50 -> 8750 cents.
        res = calculate_totals_internal(items, shipping_country_iso='ZZ', shipping_method='express')
        assert res['subtotal_cents'] == 15000
        assert res['shipping_cost_cents'] == 8750

        # 4. Economic shipping, below threshold
        items = [{'sku': 'V1', 'quantity': 1}]
        # Base: €30. Economic: *0.9 = €27 -> 2700 cents.
        res = calculate_totals_internal(items, shipping_country_iso='ZZ', shipping_method='economic')
        assert res['shipping_cost_cents'] == 2700
