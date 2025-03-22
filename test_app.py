import unittest
import os
import tempfile
import pandas as pd
from flask_testing import TestCase
from app import app, db, User, UserQueries, load_gpz_data, geokoduj_adres, znajdz_najblizsze_gpz
from datetime import datetime
import json
from unittest.mock import patch, MagicMock
from io import StringIO

class SearchGPZTestCase(TestCase):
    def create_app(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.db_fd, app.config['SQLALCHEMY_DATABASE_URI'] = tempfile.mkstemp()
        app.config['GPZ_CSV_PATH'] = 'test_gpz_database.csv'
        app.config['SECRET_KEY'] = 'test_secret_key'  # Add a secret key for session management
        return app

    def setUp(self):
        with self.app.app_context():  # Ensure we have an app context
            db.create_all()
            # Create test user
            test_user = User(username='testuser')
            test_user.set_password('password123')
            db.session.add(test_user)
            
            # Create test admin user
            admin_user = User(username='admin')
            admin_user.set_password('adminpassword')
            admin_user.is_admin = True  # Make sure this user is actually an admin
            db.session.add(admin_user)
            
            db.session.commit()
        
        # Create test CSV file
        test_data = {
            'nazwa': ['Test GPZ 1', 'Test GPZ 2', 'Test GPZ 3'],
            'adres': ['ul. Testowa 1', 'ul. Testowa 2', 'ul. Testowa 3'],
            'miasto': ['Warszawa', 'Warszawa', 'Warszawa'],
            'kod_pocztowy': ['00-001', '00-002', '00-003'],
            'latitude': [52.2297, 52.2360, 52.2299],
            'longitude': [21.0122, 21.0212, 20.9762],
            'dostepna_moc': [10.5, 8.2, 12.0],
            'dystrybutor': ['PGE', 'Tauron', 'Enea'],
            'moc_2025': [10.5, 8.2, 12.0],
            'moc_2026': [11.2, 8.5, 12.5],
            'moc_2027': [12.0, 9.0, 13.0],
            'moc_2028': [12.8, 9.5, 13.5],
            'moc_2029': [13.5, 10.0, 14.0],
            'moc_2030': [14.2, 10.5, 14.5]
        }
        
        pd.DataFrame(test_data).to_csv('test_gpz_database.csv', index=False)

    def tearDown(self):
        with self.app.app_context():  # Ensure we have an app context
            db.session.remove()
            db.drop_all()
        os.close(self.db_fd)
        os.unlink(app.config['SQLALCHEMY_DATABASE_URI'])
        if os.path.exists('test_gpz_database.csv'):
            os.remove('test_gpz_database.csv')

    def test_index_page(self):
        """Test that the index page loads correctly"""
        response = self.client.get('/')
        self.assert200(response)
        self.assertIn(b'Wyszukiwarka GPZ', response.data)

    def test_login_page(self):
        """Test that the login page loads correctly"""
        response = self.client.get('/login')
        self.assert200(response)
        self.assertIn(b'Logowanie', response.data)

    def test_register_page(self):
        """Test that the register page loads correctly"""
        response = self.client.get('/register')
        self.assert200(response)
        self.assertIn(b'Rejestracja', response.data)

    def test_user_registration(self):
        """Test user registration functionality"""
        response = self.client.post('/register', data={
            'username': 'newuser',
            'password': 'newpassword'
        }, follow_redirects=True)
        self.assert200(response)
        self.assertIn(b'Rejestracja zako', response.data)  # Check for success message
        
        # Verify user was created
        with self.app.app_context():  # Add app context
            user = User.query.filter_by(username='newuser').first()
            self.assertIsNotNone(user)

    def test_user_login(self):
        """Test user login functionality"""
        response = self.client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        }, follow_redirects=True)
        self.assert200(response)
        self.assertIn(b'Wyszukaj GPZ', response.data)

    def test_user_logout(self):
        """Test user logout functionality"""
        # First login
        self.client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        })
        # Then logout
        response = self.client.get('/logout', follow_redirects=True)
        self.assert200(response)
        self.assertIn(b'Wyszukiwarka GPZ', response.data)

    @patch('app.geokoduj_adres')
    @patch('app.znajdz_najblizsze_gpz')
    def test_wyszukaj_gpz(self, mock_znajdz, mock_geokoduj):
        """Test GPZ search functionality"""
        # Mock the geocoding function
        mock_geokoduj.return_value = (52.2297, 21.0122)
        
        # Mock the GPZ finding function
        mock_gpz = {
            'nazwa': 'Test GPZ 1',
            'adres': 'ul. Testowa 1',
            'miasto': 'Warszawa',
            'kod_pocztowy': '00-001',
            'latitude': 52.2297,
            'longitude': 21.0122,
            'dostepna_moc': 10.5,
            'dystrybutor': 'PGE',
            'moc_2025': 10.5,
            'moc_2026': 11.2,
            'moc_2027': 12.0,
            'moc_2028': 12.8,
            'moc_2029': 13.5,
            'moc_2030': 14.2
        }
        # Zwracamy listę krotek (gpz, odległość)
        mock_znajdz.return_value = [(mock_gpz, 0.5)]
        
        # Login
        self.client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        })
        
        # Search for GPZ
        response = self.client.post('/wyszukaj', data={
            'adres': 'Warszawa, Plac Defilad 1'
        })
        
        self.assert200(response)
        self.assertIn(b'Test GPZ 1', response.data)
        self.assertIn(b'10.5 MW', response.data)

    def test_query_limit(self):
        """Test that the query limit functionality works"""
        # Login
        self.client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        })
        
        # Set query count to the limit
        with self.app.app_context():  # Add app context
            user = User.query.filter_by(username='testuser').first()
            current_month = datetime.now().strftime('%Y-%m')
            user_queries = UserQueries(user_id=user.id, month=current_month, query_count=100)
            db.session.add(user_queries)
            db.session.commit()
        
        # Try to search
        response = self.client.post('/wyszukaj', data={
            'adres': 'Warszawa, Plac Defilad 1'
        })
        
        self.assert200(response)
        self.assertIn(b'Wykorzysta', response.data)  # Check for limit message

    @patch('app.geokoduj_adres')
    def test_admin_add_gpz(self, mock_geokoduj):
        """Test adding a new GPZ through the admin panel"""
        # Mock the geocoding function
        mock_geokoduj.return_value = (52.2500, 21.0000)
        
        # Login as admin
        self.client.post('/login', data={
            'username': 'admin',
            'password': 'adminpassword'
        })
        
        # Add new GPZ
        response = self.client.post('/admin/gpz', data={
            'dodaj_gpz': 'true',
            'nazwa': 'New GPZ',
            'adres': 'ul. Nowa 1',
            'miasto': 'Warszawa',
            'kod_pocztowy': '00-999',
            'dystrybutor': 'PGE',
            'dostepna_moc': '15.0',
            'moc_2025': '15.0',
            'moc_2026': '16.0',
            'moc_2027': '17.0',
            'moc_2028': '18.0',
            'moc_2029': '19.0',
            'moc_2030': '20.0'
        }, follow_redirects=True)
        
        self.assert200(response)
        self.assertIn(b'Nowy GPZ zosta', response.data)  # Check for success message
        
        # Verify GPZ was added to the CSV
        df = pd.read_csv('test_gpz_database.csv')
        self.assertIn('New GPZ', df['nazwa'].values)

    def test_load_gpz_data(self):
        """Test loading GPZ data from CSV"""
        # Make sure we're using the test CSV file
        app.config['GPZ_CSV_PATH'] = 'test_gpz_database.csv'
        gpz_data = load_gpz_data()
        self.assertEqual(len(gpz_data), 3)
        self.assertEqual(gpz_data[0]['nazwa'], 'Test GPZ 1')
        self.assertEqual(gpz_data[0]['dostepna_moc'], 10.5)

    @patch('geopy.geocoders.Nominatim.geocode')
    def test_geokoduj_adres(self, mock_geocode):
        """Test address geocoding function"""
        # Mock the Nominatim geocode function
        location_mock = MagicMock()
        location_mock.latitude = 52.2297
        location_mock.longitude = 21.0122
        mock_geocode.return_value = location_mock
        
        result = geokoduj_adres('Warszawa, Plac Defilad 1')
        self.assertEqual(result, (52.2297, 21.0122))

    def test_znajdz_najblizsze_gpz(self):
        """Test finding nearest GPZ function"""
        # Create test data first
        app.config['GPZ_CSV_PATH'] = 'test_gpz_database.csv'
        
        # Test coordinates near the first test GPZ
        result = znajdz_najblizsze_gpz(52.2297, 21.0122)
        self.assertEqual(len(result), 3)
        # Poprawka: sprawdzamy pierwszą krotkę (gpz, odległość)
        gpz, odleglosc = result[0]
        self.assertEqual(gpz['nazwa'], 'Test GPZ 1')
        # Sprawdzamy, czy drugi element krotki jest odległością
        self.assertIsInstance(odleglosc, float)


class APITestCase(TestCase):  # Change to inherit from flask_testing.TestCase
    """
    These tests simulate API endpoints that could be added to the application
    to support additional functionality in the future.
    """
    
    def create_app(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SECRET_KEY'] = 'test_api_key'
        app.config['GPZ_CSV_PATH'] = 'test_api_gpz.csv'
        return app
    
    def setUp(self):
        with self.app.app_context():  # Add app context
            db.create_all()
            
            # Create test user
            test_user = User(username='apiuser')
            test_user.set_password('apipassword')
            db.session.add(test_user)
            db.session.commit()
        
        # Create test CSV file for API tests
        test_data = {
            'nazwa': ['API GPZ 1', 'API GPZ 2'],
            'adres': ['ul. API 1', 'ul. API 2'],
            'miasto': ['Warszawa', 'Kraków'],
            'kod_pocztowy': ['00-001', '30-001'],
            'latitude': [52.2297, 50.0614],
            'longitude': [21.0122, 19.9366],
            'dostepna_moc': [10.5, 8.2],
            'dystrybutor': ['PGE', 'Tauron'],
            'moc_2025': [10.5, 8.2],
            'moc_2026': [11.2, 8.5],
            'moc_2027': [12.0, 9.0],
            'moc_2028': [12.8, 9.5],
            'moc_2029': [13.5, 10.0],
            'moc_2030': [14.2, 10.5]
        }
        
        pd.DataFrame(test_data).to_csv('test_api_gpz.csv', index=False)

    def tearDown(self):
        with self.app.app_context():  # Add app context
            db.session.remove()
            db.drop_all()
        
        if os.path.exists('test_api_gpz.csv'):
            os.remove('test_api_gpz.csv')

    @unittest.skip("API endpoints not implemented yet")
    def test_api_get_gpz_list(self):
        """Test API endpoint to get GPZ list"""
        # Login first to get session cookie
        self.client.post('/login', data={
            'username': 'apiuser',
            'password': 'apipassword'
        })
        
        response = self.client.get('/api/gpz')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    @unittest.skip("API endpoints not implemented yet")
    def test_api_search_gpz(self):
        """Test API endpoint to search for GPZ"""
        # Login first to get session cookie
        self.client.post('/login', data={
            'username': 'apiuser',
            'password': 'apipassword'
        })
        
        response = self.client.post('/api/search', json={
            'adres': 'Warszawa, Plac Defilad 1'
        })
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertLessEqual(len(data), 3)  # Should return max 3 results

if __name__ == '__main__':
    unittest.main()