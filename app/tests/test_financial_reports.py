
import pytest
from app.models import Order, OrderItem
from app.extensions import db
from datetime import datetime, timezone

def test_financial_report_calculations(authenticated_client, app):
    """
    Verify that financial reports correctly calculate Gross Sales, Returns, and Net Sales.
    Specifically, 'Returns' should be based on subtotal_cents (product value), not total_cents.
    """
    with app.app_context():
        # 1. Create a PAID order (Valid Sale)
        order_paid = Order(
            public_order_id='ORD-PAID-001',
            user_id=1, # Assuming admin user id 1 exists from seed
            status='PAID',
            subtotal_cents=10000,
            shipping_cost_cents=500,
            vat_cents=2000,
            total_cents=12500,
            discount_cents=0,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(order_paid)

        # 2. Create a RETURNED order
        # Gross Sales includes this (since it's not CANCELLED), but Returns subtracts it.
        # If Returns uses total_cents (6500), Net Sales will be lower than expected.
        # Expected Returns should use subtotal_cents (5000).
        order_returned = Order(
            public_order_id='ORD-RET-001',
            user_id=1,
            status='RETURNED',
            subtotal_cents=5000,
            shipping_cost_cents=500,
            vat_cents=1000,
            total_cents=6500,
            discount_cents=0,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(order_returned)

        # 3. Create a CANCELLED order (Should be ignored)
        order_cancelled = Order(
            public_order_id='ORD-CAN-001',
            user_id=1,
            status='CANCELLED',
            subtotal_cents=20000,
            total_cents=20000,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(order_cancelled)

        db.session.commit()

        # Fetch the report
        response = authenticated_client.get('/api/admin/reports?type=summary')
        assert response.status_code == 200
        data = response.get_json()[0]

        # Expected Calculations
        # Gross Sales: 10000 (Paid) + 5000 (Returned) = 15000
        expected_gross = 15000

        # Returns: Should be 5000 (Returned Subtotal).
        # Fails if code uses total_cents (6500).
        expected_returns = 5000

        # Net Sales: Gross - Returns - Discounts
        # 15000 - 5000 - 0 = 10000
        expected_net = 10000

        print(f"DEBUG: Report Data: {data}")

        assert data['gross_sales'] == expected_gross, f"Gross Sales mismatch. Got {data['gross_sales']}, expected {expected_gross}"
        assert data['returns'] == expected_returns, f"Returns mismatch. Got {data['returns']}, expected {expected_returns}"
        assert data['net_sales'] == expected_net, f"Net Sales mismatch. Got {data['net_sales']}, expected {expected_net}"
