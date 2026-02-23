import pytest
from app.app import create_app
from app.extensions import db
from app.models import ShippingZone
from app.utils import find_shipping_zone_for_country
import json

@pytest.fixture
def app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        db.create_all()

        # Zone 1: Standard JSON list
        z1 = ShippingZone(name="Zone 1", countries_json=["US", "CA"])
        db.session.add(z1)

        # Zone 2: String JSON list
        z2 = ShippingZone(name="Zone 2", countries_json='["GB", "FR"]')
        db.session.add(z2)

        # Zone 3: Invalid JSON (should be ignored)
        z3 = ShippingZone(name="Zone 3", countries_json='invalid-json')
        db.session.add(z3)

        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

def test_find_shipping_zone_json_list(app):
    with app.app_context():
        zone = find_shipping_zone_for_country("US")
        assert zone is not None
        assert zone.name == "Zone 1"

        zone = find_shipping_zone_for_country("ca") # mixed case
        assert zone is not None
        assert zone.name == "Zone 1"

def test_find_shipping_zone_string_json(app):
    with app.app_context():
        zone = find_shipping_zone_for_country("GB")
        assert zone is not None
        assert zone.name == "Zone 2"

        zone = find_shipping_zone_for_country("fr")
        assert zone is not None
        assert zone.name == "Zone 2"

def test_find_shipping_zone_not_found(app):
    with app.app_context():
        zone = find_shipping_zone_for_country("DE") # Not in any zone
        assert zone is None

def test_find_shipping_zone_none_iso(app):
    with app.app_context():
        zone = find_shipping_zone_for_country(None)
        assert zone is None

        zone = find_shipping_zone_for_country("")
        assert zone is None

def test_find_shipping_zone_invalid_json(app):
    with app.app_context():
        # Should gracefully handle the invalid json zone and not crash
        zone = find_shipping_zone_for_country("US")
        assert zone.name == "Zone 1"
