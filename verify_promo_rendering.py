import sys
import os
import unittest
from flask import template_rendered
from contextlib import contextmanager
from app.app import create_app, db
from app.models import GlobalSetting, Product, User

# Ensure we can import app
sys.path.append(os.getcwd())

class TestPromoRendering(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        test_config = {
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'WTF_CSRF_ENABLED': False
        }
        self.app = create_app(test_config)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed minimal data
        self.promo_msg = "Test Promo Message"
        db.session.add(GlobalSetting(key='global_promo_message', value=self.promo_msg))
        db.session.add(GlobalSetting(key='global_promo_enabled', value='true'))

        # Seed a product for product page test
        self.product = Product(
            product_sku='TEST-SKU',
            name='Test Product',
            base_price_cents=1000,
            status='published'
        )
        db.session.add(self.product)
        db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_home_page_banner(self):
        """Verify banner appears on home page."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')

        # Check for banner content
        self.assertIn(self.promo_msg, content)
        # Check for banner container class
        self.assertIn('bg-dark text-white text-center', content)

    def test_product_page_no_banner_but_inline(self):
        """Verify banner is ABSENT on product page, but inline message IS PRESENT."""
        response = self.client.get(f'/product/{self.product.product_sku}')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')

        # 1. Verify Inline Message is PRESENT
        self.assertIn('badge bg-danger', content)
        # Check that the message is inside the badge (loose check for HTML structure)
        self.assertIn(self.promo_msg, content)

        # 2. Verify Banner is ABSENT
        # The banner has class "bg-dark text-white text-center py-2"
        # We can check that this class string is NOT in the content
        # Note: The footer also has "bg-dark text-white", so be specific
        # Banner: <div class="bg-dark text-white text-center py-2 fw-bold small">
        self.assertNotIn('bg-dark text-white text-center py-2 fw-bold small', content)

        # Also double check count of message
        self.assertEqual(content.count(self.promo_msg), 1, "Promo message should appear exactly once (inline only).")

if __name__ == '__main__':
    unittest.main()
