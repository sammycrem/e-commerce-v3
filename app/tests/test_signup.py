import pytest
from app.app import create_app
from app.extensions import db
from app.models import User
import os

@pytest.fixture
def app():
    os.environ['ENCRYPTION_KEY'] = 'test_key_must_be_url_safe_base64_encoded_32_bytes_at_least'
    # Generate a valid Fernet key for testing
    from cryptography.fernet import Fernet
    os.environ['ENCRYPTION_KEY'] = Fernet.generate_key().decode()

    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_signup_success_redirect(client, app):
    # This test asserts that the signup actually redirects (success) rather than rendering the page again (failure/error caught)
    # The previous test was too lenient because the error handler in signup() renders the template with 200 OK.

    response = client.post('/signup', data={
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'password123'
    })

    # Expect redirect to login page
    assert response.status_code == 302
    assert '/login' in response.location

    with app.app_context():
        user = User.query.filter_by(username='newuser').first()
        assert user is not None
        assert user.encrypted_password is not None
