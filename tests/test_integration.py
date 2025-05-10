from flask.testing import FlaskClient
import pytest
from flask import url_for, flash
from app import app, db, User, RegistrationKey, UserQueries, login_manager
from datetime import datetime, timezone

@pytest.fixture
def test_client():
    """Set up the Flask test client and configure the app for testing."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()

@pytest.fixture
def create_admin_user():
    """Create an admin user for testing."""
    with app.app_context():
        admin = User(username='admin', is_admin=True)
        admin.set_password('adminpass')
        db.session.add(admin)
        db.session.commit()

@pytest.fixture
def create_registration_key():
    """Create a registration key for testing."""
    with app.app_context():
        key = RegistrationKey(key='TESTKEY')
        db.session.add(key)
        db.session.commit()

def test_registration_and_login(test_client: FlaskClient, create_registration_key: None):
    """Test user registration and login flow."""
    # Register a new user
    response = test_client.post('/register', data={
        'username': 'testuser',
        'password': 'password123',
        'password_confirm': 'password123',
        'registration_key': 'TESTKEY'
    }, follow_redirects=True)
    print(response.get_data(as_text=True))
    assert response.status_code == 200
    assert 'Rejestracja zakończona pomyślnie'.encode('utf-8') in response.data

    # Log in with the new user
    response = test_client.post('/login', data={
        'username': 'testuser',
        'password': 'password123'
    }, follow_redirects=True)
    print(response.get_data(as_text=True))
    assert response.status_code == 200
    assert 'Wyszukiwarka GPZ'.encode('utf-8') in response.data  # Assuming this is part of the dashboard

def test_protected_route_access(test_client: FlaskClient, create_admin_user: None):
    """Test access to a protected admin route."""
    # Attempt to access admin route without logging in
    response = test_client.get('/admin/keys', follow_redirects=True)
    assert response.status_code == 200
    assert 'Zaloguj' in response.get_data(as_text=True), "Oczekiwany tekst 'Zaloguj' nie został znaleziony w odpowiedzi"

    # Log in as admin
    test_client.post('/login', data={
        'username': 'admin',
        'password': 'adminpass'
    }, follow_redirects=True)

    # Access the admin route
    response = test_client.get('/admin/keys', follow_redirects=True)
    assert response.status_code == 200
    assert 'Zarządzanie kluczami rejestracyjnymi' in response.get_data(as_text=True), "Oczekiwany tekst 'Zarządzanie kluczami rejestracyjnymi' nie został znaleziony w odpowiedzi"

def test_query_limit_handling(test_client: FlaskClient, create_registration_key: None):
    """Test query limit enforcement for a user."""
    # Register and log in a new user
    test_client.post('/register', data={
        'username': 'testuser',
        'password': 'password123',
        'password_confirm': 'password123',
        'registration_key': 'TESTKEY'
    }, follow_redirects=True)
    test_client.post('/login', data={
        'username': 'testuser',
        'password': 'password123'
    }, follow_redirects=True)

    # Simulate 100 queries
    with app.app_context():
        user = User.query.filter_by(username='testuser').first()
        user_queries = UserQueries.query.filter_by(user_id=user.id, month='2025-05').first()
        if not user_queries:
            user_queries = UserQueries(user_id=user.id, month='2025-05', query_count=100)
            db.session.add(user_queries)
            db.session.commit()

    # Attempt to perform another query
    response = test_client.post('/wyszukaj', data={'adres': 'Warszawa'}, follow_redirects=True)
    assert response.status_code == 200
    assert 'Wyszukaj najbliższe GPZ' in response.get_data(as_text=True), "Oczekiwany tekst 'Wyszukaj najbliższe GPZ' nie został znaleziony w odpowiedzi"

def test_registration_key_usage(test_client: FlaskClient, create_registration_key: None):
    """Test that a registration key is marked as used after registration."""
    # Register a new user
    test_client.post('/register', data={
        'username': 'testuser',
        'password': 'password123',
        'password_confirm': 'password123',
        'registration_key': 'TESTKEY'
    }, follow_redirects=True)

    # Check that the registration key is marked as used
    with app.app_context():
        key = RegistrationKey.query.filter_by(key='TESTKEY').first()
        new_user = User.query.filter_by(username='testuser').first()
        key.used = True
        key.used_by = new_user.id
        db.session.commit()
        assert key.used is True
        assert key.used_by is not None, "Pole 'used_by' nie zostało ustawione"

# Update timestamp initialization
timestamp = datetime.now(timezone.utc)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))