import pytest
from app.models import GlobalSetting

def test_global_promo_dynamic_update(authenticated_client, app):
    """
    Verify that updating the global promo settings via the API immediately
    reflects on the home page without requiring a server restart.
    """
    with app.app_context():
        # 1. Initially, no promo message (or whatever default is)
        # Ensure it's clean first
        authenticated_client.post('/api/admin/settings', json={
            'global_promo_enabled': False,
            'global_promo_message': ''
        })

        response = authenticated_client.get('/')
        assert b'F0RYOU10' not in response.data

        # 2. Update settings via API
        response = authenticated_client.post('/api/admin/settings', json={
            'global_promo_enabled': True,
            'global_promo_message': '10% OFF everything. Code: F0RYOU10'
        })
        assert response.status_code == 200

        # 3. Verify it appears on home page
        response = authenticated_client.get('/')
        assert b'F0RYOU10' in response.data, "Promo message not found on home page after update"

        # 4. Disable it
        response = authenticated_client.post('/api/admin/settings', json={
            'global_promo_enabled': False,
            'global_promo_message': '10% OFF everything. Code: F0RYOU10'
        })
        assert response.status_code == 200

        # 5. Verify it disappears
        response = authenticated_client.get('/')
        assert b'F0RYOU10' not in response.data, "Promo message found on home page after disable"
