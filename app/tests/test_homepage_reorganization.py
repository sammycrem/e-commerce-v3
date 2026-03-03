import pytest
from app.app import create_app
from app.extensions import db
from app.models import Category, Product

@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_homepage_reorganization(client, app):
    with app.app_context():
        # Create categories
        c1 = Category(name='Cat 1', slug='cat-1')
        c2 = Category(name='Cat 2', slug='cat-2')
        db.session.add_all([c1, c2])

        # Create 6 products for Cat 1
        for i in range(6):
            p = Product(
                product_sku=f'SKU1-{i}',
                name=f'Prod 1-{i}',
                category='Cat 1',
                base_price_cents=1000,
                status='published'
            )
            db.session.add(p)

        # Create 3 products for Cat 2
        for i in range(3):
            p = Product(
                product_sku=f'SKU2-{i}',
                name=f'Prod 2-{i}',
                category='Cat 2',
                base_price_cents=2000,
                status='published'
            )
            db.session.add(p)

        db.session.commit()

    response = client.get('/')
    assert response.status_code == 200
    html = response.data.decode()

    # Check for category titles
    assert 'Cat 1' in html
    assert 'Cat 2' in html

    # Check for View All links
    assert '/shop/category/cat-1' in html
    assert '/shop/category/cat-2' in html

    # Check for product names
    # Cat 1 should only have 5 products displayed
    assert 'Prod 1-5' in html # Latest
    assert 'Prod 1-4' in html
    assert 'Prod 1-3' in html
    assert 'Prod 1-2' in html
    assert 'Prod 1-1' in html
    assert 'Prod 1-0' not in html # 6th product should be hidden

    # Cat 2 should have all 3
    assert 'Prod 2-2' in html
    assert 'Prod 2-1' in html
    assert 'Prod 2-0' in html
