from app.app import create_app, db
from app.models import Order, User, Address, OrderItem
from app.utils import generate_invoice_pdf
from datetime import datetime, timezone

def test_invoice_bytes():
    app = create_app()
    with app.app_context():
        # Create a dummy order
        user = User.query.first()
        if not user:
             user = User(username='test', email='test@test.com', user_id='U1', password='pw', encrypted_password='epw')
             db.session.add(user)
             db.session.flush()

        order = Order(
            public_order_id='TEST-INV-123',
            user_id=user.id,
            status='PAID',
            subtotal_cents=1000,
            vat_cents=200,
            total_cents=1200,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(order)
        db.session.flush()

        item = OrderItem(
            order_id=order.id,
            variant_sku='V1',
            quantity=1,
            unit_price_cents=1000,
            product_snapshot={'name': 'Test Item'}
        )
        db.session.add(item)

        # Test generate_invoice_pdf
        pdf_content = generate_invoice_pdf(order)
        print(f"Type of pdf_content: {type(pdf_content)}")
        assert isinstance(pdf_content, bytes), f"Expected bytes, got {type(pdf_content)}"
        print("Verification successful: generate_invoice_pdf returns bytes.")

if __name__ == "__main__":
    test_invoice_bytes()
