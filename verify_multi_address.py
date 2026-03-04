import unittest
from app.app import create_app, db
from app.models import User, Address, Product, Category, Variant, Country
from app.utils import encrypt_password
from playwright.sync_api import sync_playwright
import time
import os
from werkzeug.security import generate_password_hash
import subprocess

def setup_test_data():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Create test user
        encryption_key = os.environ.get('ENCRYPTION_KEY')
        user = User(
            username='testuser',
            email='testuser@example.com',
            user_id='TEST001',
            password=generate_password_hash('password123'),
            encrypted_password=encrypt_password('password123', encryption_key)
        )
        db.session.add(user)
        db.session.flush()

        # Add addresses
        addr1 = Address(
            user_id=user.id,
            address_type='shipping',
            first_name='Test',
            last_name='One',
            address_line_1='123 Main St',
            city='London',
            country_iso_code='GB',
            postal_code='E1 6AN',
            is_default=True
        )
        addr2 = Address(
            user_id=user.id,
            address_type='shipping',
            first_name='Test',
            last_name='Two',
            address_line_1='456 Side St',
            city='Manchester',
            country_iso_code='GB',
            postal_code='M1 1AA',
            is_default=False
        )
        db.session.add(addr1)
        db.session.add(addr2)

        # Ensure a country exists
        db.session.add(Country(name='United Kingdom', iso_code='GB', currency_code='GBP', shipping_cost_cents=500))

        # Ensure a product exists
        cat = Category(name='Test Cat', slug='test-cat')
        db.session.add(cat)
        db.session.flush()
        prod = Product(product_sku='TEST-PROD', name='Test Product', category=cat.name, status='published', base_price_cents=1000)
        db.session.add(prod)
        db.session.flush()
        variant = Variant(product_id=prod.id, sku='TEST-PROD-V1', stock_quantity=100)
        db.session.add(variant)

        db.session.commit()
    return app

def run_verification():
    setup_test_data()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        # Start server in background
        subprocess.run("kill $(lsof -t -i :5000) 2>/dev/null || true", shell=True)
        process = subprocess.Popen(['python3', '-m', 'app.app'])
        time.sleep(5)

        try:
            # Login
            page.goto('http://127.0.0.1:5000/login')
            page.fill('input[name="email"]', 'testuser@example.com')
            page.fill('input[name="password"]', 'password123')
            page.click('button[type="submit"]')
            time.sleep(2)

            # Go to product page directly
            page.goto('http://127.0.0.1:5000/product/TEST-PROD')
            time.sleep(2)
            page.click('#add-to-cart')
            time.sleep(2)

            # Go to checkout
            page.goto('http://127.0.0.1:5000/checkout/shipping-address')
            time.sleep(2)
            page.screenshot(path='/home/jules/verification/shipping_address_multi.png', full_page=True)
            print("Screenshot saved to /home/jules/verification/shipping_address_multi.png")

        finally:
            process.terminate()
            browser.close()

if __name__ == '__main__':
    run_verification()
