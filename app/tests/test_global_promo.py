import pytest
from app.models import GlobalSetting
from app.extensions import db
from flask import current_app

def test_global_promo_feature(client, app):
    """Test the global promotion banner functionality"""

    # 1. Check default state (disabled)
    res = client.get('/')
    assert b"TEST PROMO 123" not in res.data

    # Login as admin
    with app.app_context():
        admin_email = app.config.get('APP_ADMIN_EMAIL', 'admin@nomail.local')
        # In test config, we might not have set password explicitly, but app loads from config.txt
        # setup_database creates user with that password.
        admin_password = app.config.get('APP_ADMIN_PASSWORD', 'xyz14')

    # Attempt login
    res = client.post('/login', data={'email': admin_email, 'password': admin_password}, follow_redirects=True)
    assert res.status_code == 200
    if b"Admin" not in res.data and b"Dashboard" not in res.data:
         # Print response to debug login failure
         print("Login failed. Response:", res.data)
         pytest.fail("Could not log in as admin")

    # 2. Enable promo via API
    # Ensure clean state
    with app.app_context():
        # Clean existing settings first if any
        GlobalSetting.query.filter_by(key='global_promo_enabled').delete()
        GlobalSetting.query.filter_by(key='global_promo_message').delete()
        db.session.commit()

    payload = {
        "global_promo_enabled": True,
        "global_promo_message": "TEST PROMO 123"
    }

    res = client.post('/api/admin/settings', json=payload)
    assert res.status_code == 200

    # 3. Check if enabled on home page
    res = client.get('/')
    assert b"TEST PROMO 123" in res.data

    # 4. Disable promo
    payload["global_promo_enabled"] = False
    res = client.post('/api/admin/settings', json=payload)
    assert res.status_code == 200

    # 5. Check if disabled on home page
    res = client.get('/')
    assert b"TEST PROMO 123" not in res.data
