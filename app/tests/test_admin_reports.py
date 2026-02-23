import pytest
from app.models import Order, OrderItem, Product, Variant, User
from app.extensions import db
from datetime import datetime, timedelta, timezone

# We use authenticated_client from conftest.py which gives us a client logged in as admin
# conftest.py's authenticated_client fixture relies on the admin user existing (created by setup_database)

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def authenticated_client(client, app):
    # Ensure admin user exists
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', email='admin@example.com')
            admin.set_password('password')
            db.session.add(admin)
            db.session.commit()

        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True
    return client

def create_order(status='PAID', created_at=None, total_cents=1000, subtotal_cents=800, vat_cents=100, shipping_cost_cents=100, discount_cents=0, items=[]):
    if not created_at:
        created_at = datetime.now(timezone.utc)

    # Ensure a user exists for the order
    user = User.query.first() # Get any user, likely admin from fixture
    if not user:
        user = User(username='customer', email='customer@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

    order = Order(
        public_order_id=f"ORD-{datetime.now().timestamp()}-{total_cents}-{discount_cents}",
        status=status,
        created_at=created_at,
        total_cents=total_cents,
        subtotal_cents=subtotal_cents,
        vat_cents=vat_cents,
        shipping_cost_cents=shipping_cost_cents,
        discount_cents=discount_cents,
        user_id=user.id
    )

    db.session.add(order)
    db.session.flush()

    for item in items:
        oi = OrderItem(
            order_id=order.id,
            variant_sku=item.get('sku', 'TEST-SKU'),
            quantity=item.get('quantity', 1),
            unit_price_cents=item.get('price', 100),
            product_snapshot={}
        )
        db.session.add(oi)

    db.session.commit()
    return order

def test_admin_reports_summary(authenticated_client, app):
    with app.app_context():
        # Clear orders first to avoid contamination from other tests?
        # But app fixture usually resets DB or uses transaction rollback.
        # Assuming clean DB.
        db.session.query(Order).delete()
        db.session.commit()

        # Create some orders
        create_order(status='PAID', total_cents=1200, subtotal_cents=1000, vat_cents=100, shipping_cost_cents=100)
        create_order(status='SHIPPED', total_cents=2400, subtotal_cents=2000, vat_cents=200, shipping_cost_cents=200)
        create_order(status='CANCELLED', total_cents=500) # Should be ignored
        create_order(status='RETURNED', total_cents=1200, subtotal_cents=1000, vat_cents=100, shipping_cost_cents=100) # Should count as return

    response = authenticated_client.get('/api/admin/reports?type=summary')
    assert response.status_code == 200
    data = response.json[0]

    # Gross: 1000 + 2000 + 1000 = 4000
    assert data['gross_sales'] == 4000
    assert data['shipping'] == 400 # 100 + 200 + 100
    assert data['vat'] == 400 # 100 + 200 + 100

    # Updated expectations based on new logic (Returns = Subtotal)
    assert data['returns'] == 1000 # Subtotal of returned order

    # Net Sales = Gross - Discounts (0) - Returns (1000) = 3000
    assert data['net_sales'] == 3000

    assert data['orders_count'] == 3 # All non-cancelled orders (3)

def test_admin_reports_daily(authenticated_client, app):
    with app.app_context():
        db.session.query(Order).delete()
        db.session.commit()

        today = datetime.now(timezone.utc)
        yesterday = today - timedelta(days=1)

        # Today:
        # 1. Gross 800, Discount 0
        # 2. Gross 1600, Discount 200 (Total = 1600 - 200 + 200 + 400 = 2000)
        create_order(created_at=today, total_cents=1000, subtotal_cents=800, vat_cents=100, shipping_cost_cents=100)
        create_order(created_at=today, total_cents=2000, subtotal_cents=1600, vat_cents=200, shipping_cost_cents=200, discount_cents=200)

        # Yesterday:
        # 1. Gross 1200, Discount 0
        create_order(created_at=yesterday, total_cents=1500, subtotal_cents=1200, vat_cents=150, shipping_cost_cents=150)

    response = authenticated_client.get('/api/admin/reports?type=daily')
    assert response.status_code == 200
    data = response.json

    # Sort by date desc
    today_str = today.strftime('%Y-%m-%d')
    yesterday_str = yesterday.strftime('%Y-%m-%d')

    today_entry = next((d for d in data if d['date'] == today_str), None)
    assert today_entry is not None
    assert today_entry['orders_count'] == 2
    assert today_entry['gross_sales'] == 2400 # 800 + 1600
    assert today_entry['discounts'] == 200    # Added verification for discounts
    # Net = 2400 - 200 - 0 = 2200
    assert today_entry['net_sales'] == 2200

    yesterday_entry = next((d for d in data if d['date'] == yesterday_str), None)
    assert yesterday_entry is not None
    assert yesterday_entry['gross_sales'] == 1200
    assert yesterday_entry['discounts'] == 0
    assert yesterday_entry['net_sales'] == 1200

def test_admin_reports_items(authenticated_client, app):
    with app.app_context():
        db.session.query(Order).delete()
        db.session.query(Product).delete()
        db.session.commit()

        # Need products and variants
        p = Product(name="Test Product", product_sku="TEST_P", base_price_cents=1000, status='published')
        db.session.add(p)
        db.session.commit()

        v = Variant(product_id=p.id, sku="TEST_V", price_modifier_cents=0, stock_quantity=100)
        db.session.add(v)
        db.session.commit()

        create_order(items=[{'sku': 'TEST_V', 'quantity': 2, 'price': 1000}])

    response = authenticated_client.get('/api/admin/reports?type=items')
    assert response.status_code == 200
    data = response.json

    item = next((d for d in data if d['sku'] == "TEST_V"), None)
    assert item is not None
    assert item['sold'] == 2
    assert item['revenue'] == 2000

def test_admin_reports_csv(authenticated_client, app):
    with app.app_context():
        create_order()

    response = authenticated_client.get('/api/admin/reports?type=summary&format=csv')
    assert response.status_code == 200
    assert response.headers['Content-Type'].startswith('text/csv')
    assert b'Gross Sales' in response.data
