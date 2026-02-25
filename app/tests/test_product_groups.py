import pytest
from app.models import ProductGroup, Product
from app.extensions import db

def test_create_product_group(authenticated_client, app):
    """Test creating a product group via API"""
    res = authenticated_client.post('/api/admin/product-groups', json={
        'name': 'New Group'
    })
    assert res.status_code == 201
    assert res.json['name'] == 'New Group'
    assert res.json['slug'] == 'new-group'

    with app.app_context():
        group = ProductGroup.query.filter_by(name='New Group').first()
        assert group is not None

def test_add_product_to_group(authenticated_client, app):
    """Test adding a product to a group"""
    with app.app_context():
        group = ProductGroup(name='Test Group')
        db.session.add(group)
        db.session.commit()
        group_id = group.id

        product = Product.query.filter_by(product_sku='TEST-SHIRT').first()
        sku = product.product_sku

    res = authenticated_client.post(f'/api/admin/product-groups/{group_id}/add-product-sku', json={
        'sku': sku
    })
    assert res.status_code == 200
    assert len(res.json['products']) == 1
    assert res.json['products'][0]['product_sku'] == sku

def test_list_product_groups(authenticated_client, app):
    """Test listing product groups"""
    with app.app_context():
        db.session.add(ProductGroup(name='Group 1'))
        db.session.add(ProductGroup(name='Group 2'))
        db.session.commit()

    res = authenticated_client.get('/api/admin/product-groups')
    assert res.status_code == 200
    assert len(res.json) >= 2

def test_delete_product_group(authenticated_client, app):
    """Test deleting a product group"""
    with app.app_context():
        group = ProductGroup(name='To Delete')
        db.session.add(group)
        db.session.commit()
        group_id = group.id

    res = authenticated_client.delete(f'/api/admin/product-groups/{group_id}')
    assert res.status_code == 200

    with app.app_context():
        assert db.session.get(ProductGroup, group_id) is None
