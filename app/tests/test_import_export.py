import unittest
import json
import io
import csv
from app.app import create_app, db
from app.models import Product, Variant, ProductImage, VariantImage
from app.product_service import products_to_csv

class TestImportExport(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'WTF_CSRF_ENABLED': False,
            'CACHE_TYPE': 'NullCache'
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Create admin user
        from app.models import User
        from werkzeug.security import generate_password_hash
        admin_user = User(username='admin', email='admin@test.com', user_id='admin1', password=generate_password_hash('password'), encrypted_password='enc')
        db.session.add(admin_user)
        db.session.commit()

        # Configure app admin
        self.app.config['APP_ADMIN_USER'] = 'admin'

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login_admin(self):
        self.client.post('/login', data={'email': 'admin@test.com', 'password': 'password'})

    def test_export_csv(self):
        self.login_admin()
        # Create a product
        p = Product(product_sku='SKU1', name='P1', base_price_cents=1000, category='Cat1')
        db.session.add(p)
        db.session.commit()

        res = self.client.get('/api/admin/products/export?format=csv')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'product_sku', res.data)
        self.assertIn(b'SKU1', res.data)

    def test_import_override(self):
        self.login_admin()
        # Existing product
        p = Product(product_sku='OLD', name='Old', base_price_cents=100)
        db.session.add(p)
        db.session.commit()

        # CSV to import
        csv_content = """product_sku,name,base_price_cents
NEW,New Product,2000
"""
        data = {
            'file': (io.BytesIO(csv_content.encode('utf-8')), 'import.csv'),
            'mode': 'override'
        }
        res = self.client.post('/api/admin/products/import', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)

        # Verify
        old = Product.query.filter_by(product_sku='OLD').first()
        self.assertIsNone(old)
        new = Product.query.filter_by(product_sku='NEW').first()
        self.assertIsNotNone(new)
        self.assertEqual(new.name, 'New Product')

    def test_import_skip(self):
        self.login_admin()
        p = Product(product_sku='EXISTING', name='Original Name', base_price_cents=100)
        db.session.add(p)
        db.session.commit()

        csv_content = """product_sku,name,base_price_cents
EXISTING,New Name,2000
NEW,Brand New,3000
"""
        data = {
            'file': (io.BytesIO(csv_content.encode('utf-8')), 'import.csv'),
            'mode': 'skip'
        }
        res = self.client.post('/api/admin/products/import', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)

        existing = Product.query.filter_by(product_sku='EXISTING').first()
        self.assertEqual(existing.name, 'Original Name') # Should not change

        new = Product.query.filter_by(product_sku='NEW').first()
        self.assertIsNotNone(new)

    def test_import_update(self):
        self.login_admin()
        p = Product(product_sku='EXISTING', name='Original Name', base_price_cents=100)
        db.session.add(p)
        db.session.commit()

        # Add variant to verify replacement
        v = Variant(product_id=p.id, sku='VAR-OLD', stock_quantity=5)
        db.session.add(v)
        db.session.commit()

        variants_json = json.dumps([{"sku": "VAR-NEW", "stock_quantity": 10}])

        csv_content = f"""product_sku,name,base_price_cents,variants_json
EXISTING,Updated Name,2000,"{variants_json.replace('"', '""')}"
NEW,Brand New,3000,[]
"""
        data = {
            'file': (io.BytesIO(csv_content.encode('utf-8')), 'import.csv'),
            'mode': 'update'
        }
        res = self.client.post('/api/admin/products/import', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)

        existing = Product.query.filter_by(product_sku='EXISTING').first()
        self.assertEqual(existing.name, 'Updated Name')
        self.assertEqual(existing.base_price_cents, 2000)

        # Verify variant replacement
        self.assertEqual(len(existing.variants), 1)
        self.assertEqual(existing.variants[0].sku, 'VAR-NEW')

        new = Product.query.filter_by(product_sku='NEW').first()
        self.assertIsNotNone(new)

if __name__ == '__main__':
    unittest.main()
