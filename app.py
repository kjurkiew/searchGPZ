from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import os
import csv
import pandas as pd
from functools import wraps
from datetime import datetime, timedelta
import re
import secrets
import string
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tajny-klucz-aplikacji')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///baza.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['GPZ_CSV_PATH'] = 'gpz_database.csv'  # Ścieżka do pliku CSV
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Model użytkownika
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # Dodane pole roli
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Dodaj model UserQueries do śledzenia limitów zapytań użytkownika.
class UserQueries(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # Format: YYYY-MM
    query_count = db.Column(db.Integer, default=0)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'month', name='unique_user_month'),
    )

# Model dla kluczy rejestracyjnych
class RegistrationKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(16), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    def __repr__(self):
        return f'<RegistrationKey {self.key}>'
    
# Funkcja do wczytania danych GPZ z pliku CSV
def load_gpz_data():
    gpz_data = []
    
    # Sprawdź czy plik CSV istnieje, jeśli nie - utwórz przykładowy plik
    if not os.path.exists(app.config['GPZ_CSV_PATH']):
        with open(app.config['GPZ_CSV_PATH'], 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['nazwa', 'adres', 'miasto', 'kod_pocztowy', 'latitude', 'longitude', 'dostepna_moc', 
                         'dystrybutor', 'moc_2025', 'moc_2026', 'moc_2027', 'moc_2028', 'moc_2029', 'moc_2030']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            writer.writerow({
                'nazwa': 'GPZ Centrum', 
                'adres': 'ul. Przykładowa 1', 
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
            })
            writer.writerow({
                'nazwa': 'GPZ Wschód', 
                'adres': 'ul. Wschodnia 15', 
                'miasto': 'Warszawa', 
                'kod_pocztowy': '00-123',
                'latitude': 52.2360, 
                'longitude': 21.0212, 
                'dostepna_moc': 8.2,
                'dystrybutor': 'Tauron',
                'moc_2025': 8.2,
                'moc_2026': 8.5,
                'moc_2027': 9.0,
                'moc_2028': 9.5,
                'moc_2029': 10.0,
                'moc_2030': 10.5
            })
            writer.writerow({
                'nazwa': 'GPZ Zachód', 
                'adres': 'ul. Zachodnia 7', 
                'miasto': 'Warszawa', 
                'kod_pocztowy': '00-456',
                'latitude': 52.2299, 
                'longitude': 20.9762, 
                'dostepna_moc': 12.0,
                'dystrybutor': 'Enea',
                'moc_2025': 12.0,
                'moc_2026': 12.5,
                'moc_2027': 13.0,
                'moc_2028': 13.5,
                'moc_2029': 14.0,
                'moc_2030': 14.5
            })
    
    # Wczytaj dane z pliku CSV
    try:
        df = pd.read_csv(app.config['GPZ_CSV_PATH'])
        for _, row in df.iterrows():
            gpz_data.append({
                'nazwa': row['nazwa'],
                'adres': row['adres'],
                'miasto': row['miasto'],
                'kod_pocztowy': row['kod_pocztowy'] if 'kod_pocztowy' in row and pd.notna(row['kod_pocztowy']) else '',
                'pelny_adres': f"{row['adres']}, {row['miasto']}{', ' + row['kod_pocztowy'] if 'kod_pocztowy' in row and pd.notna(row['kod_pocztowy']) else ''}",
                'latitude': float(row['latitude']),
                'longitude': float(row['longitude']),
                'dostepna_moc': float(row['dostepna_moc']),
                'dystrybutor': row['dystrybutor'] if 'dystrybutor' in row and pd.notna(row['dystrybutor']) else 'Nieznany',
                'moc_2025': float(row['moc_2025']) if 'moc_2025' in row and pd.notna(row['moc_2025']) else 0.0,
                'moc_2026': float(row['moc_2026']) if 'moc_2026' in row and pd.notna(row['moc_2026']) else 0.0,
                'moc_2027': float(row['moc_2027']) if 'moc_2027' in row and pd.notna(row['moc_2027']) else 0.0,
                'moc_2028': float(row['moc_2028']) if 'moc_2028' in row and pd.notna(row['moc_2028']) else 0.0,
                'moc_2029': float(row['moc_2029']) if 'moc_2029' in row and pd.notna(row['moc_2029']) else 0.0,
                'moc_2030': float(row['moc_2030']) if 'moc_2030' in row and pd.notna(row['moc_2030']) else 0.0
            })
    except Exception as e:
        print(f"Błąd wczytywania danych GPZ: {e}")
    
    return gpz_data
    
# Inicjalizacja bazy danych i tworzenie konta administratora
with app.app_context():
    db.create_all()
    
    # Sprawdź czy istnieje konto administratora, jeśli nie - utwórz je
    admin_user = User.query.filter_by(username='GPZadmin').first()
    if not admin_user:
        admin_user = User(username='GPZadmin', is_admin=True)
        admin_user.set_password('GPZ202%')
        db.session.add(admin_user)
        try:
            db.session.commit()
            print('Konto administratora zostało utworzone. Zmień hasło przy pierwszym użyciu')
        except Exception as e:
            db.session.rollback()
            print(f'Błąd podczas tworzenia konta administratora: {e}')

# Funkcja do geokodowania adresu (zamiana adresu na współrzędne)
def geokoduj_adres(adres):
    # Walidacja danych wejściowych
    if not adres or not isinstance(adres, str):
        return None
        
    # Usunięcie potencjalnie niebezpiecznych znaków
    adres = re.sub(r'[<>\'";]', '', adres)
    
    geolocator = Nominatim(user_agent="gpz-finder")
    try:
        location = geolocator.geocode(adres + ", Polska")
        if location:
            return (location.latitude, location.longitude)
        return None
    except Exception as e:
        print(f"Błąd geokodowania: {e}")
        return None
    
# Funkcja znajdująca najbliższe GPZ
def znajdz_najblizsze_gpz(lat, lon, limit=3):
    wszystkie_gpz = load_gpz_data()
    
    # Oblicz odległość dla każdego GPZ
    gpz_z_odlegloscia = []
    for gpz in wszystkie_gpz:
        odleglosc = geodesic((lat, lon), (gpz['latitude'], gpz['longitude'])).kilometers
        gpz_z_odlegloscia.append((gpz, odleglosc))
    
    # Posortuj po odległości i zwróć 3 najbliższe
    gpz_z_odlegloscia.sort(key=lambda x: x[1])
    return gpz_z_odlegloscia[:limit]

# Dekorator do sprawdzania uprawnień administratora
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Brak dostępu. Ta strona jest dostępna tylko dla administratorów.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Strona główna
@app.route('/', methods=['GET', 'POST'])
def index():
    if current_user.is_authenticated:
        return redirect(url_for('wyszukaj_gpz'))
    return render_template('index.html')

# Logowanie
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Regeneracja ID sesji przy logowaniu dla bezpieczeństwa
        session.clear()
        
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Walidacja danych wejściowych
        if not username or not password:
            flash('Proszę wypełnić wszystkie pola.')
            return render_template('login.html')
            
        # Usunięcie potencjalnie niebezpiecznych znaków
        username = re.sub(r'[<>\'";]', '', username)
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            session.permanent = True  # Włącz timeout sesji
            
            # Przekierowanie do żądanej strony lub domyślnie do wyszukiwarki
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('wyszukaj_gpz')
                
            return redirect(next_page)
        else:
            flash('Nieprawidłowa nazwa użytkownika lub hasło.')
            
    return render_template('login.html')

# Rejestracja
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        registration_key = request.form.get('registration_key')
        
        # Walidacja danych wejściowych
        if not username or not password or not password_confirm or not registration_key:
            flash('Proszę wypełnić wszystkie pola.')
            return render_template('register.html')
            
        # Sprawdzenie hasła
        if password != password_confirm:
            flash('Hasła nie pasują do siebie.')
            return render_template('register.html')
            
        # Usunięcie potencjalnie niebezpiecznych znaków
        username = re.sub(r'[<>\'";]', '', username)
        registration_key = re.sub(r'[<>\'";]', '', registration_key)
        
        # Sprawdzenie długości nazwy użytkownika
        if len(username) < 3 or len(username) > 50:
            flash('Nazwa użytkownika musi mieć od 3 do 50 znaków.')
            return render_template('register.html')
            
        # Sprawdzenie, czy klucz rejestracyjny jest ważny
        key = RegistrationKey.query.filter_by(key=registration_key, used=False).first()
        if not key:
            flash('Nieprawidłowy lub już wykorzystany klucz rejestracyjny.')
            return render_template('register.html')
            
        existing_user = User.query.filter_by(username=username).first()
        
        if existing_user:
            flash('Nazwa użytkownika jest już zajęta.')
        else:
            try:
                new_user = User(username=username)
                new_user.set_password(password)
                db.session.add(new_user)
                
                # Oznacz klucz jako wykorzystany
                key.used = True
                key.used_by = new_user.id
                
                db.session.commit()
                flash('Rejestracja zakończona pomyślnie. Możesz się teraz zalogować.')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash(f'Wystąpił błąd podczas rejestracji: {str(e)}')
                
    return render_template('register.html')

# Dodaj trasę do zmiany hasła
@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        new_password_confirm = request.form.get('new_password_confirm')
        
        # Walidacja danych wejściowych
        if not current_password or not new_password or not new_password_confirm:
            flash('Proszę wypełnić wszystkie pola.')
            return render_template('change_password.html')
            
        # Sprawdzenie, czy hasło jest poprawne
        if not current_user.check_password(current_password):
            flash('Aktualne hasło jest niepoprawne.')
            return render_template('change_password.html')
            
        # Sprawdzenie, czy nowe hasło jest takie samo w obu polach
        if new_password != new_password_confirm:
            flash('Nowe hasła nie pasują do siebie.')
            return render_template('change_password.html')
            
        # Sprawdzenie, czy nowe hasło jest inne niż stare
        if current_password == new_password:
            flash('Nowe hasło musi różnić się od aktualnego.')
            return render_template('change_password.html')
            
        try:
            # Ustaw nowe hasło
            current_user.set_password(new_password)
            db.session.commit()
            flash('Hasło zostało zmienione pomyślnie.')
            return redirect(url_for('wyszukaj_gpz'))
        except Exception as e:
            db.session.rollback()
            flash(f'Wystąpił błąd podczas zmiany hasła: {str(e)}')
            
    return render_template('change_password.html')

# Dodaj trasę do zarządzania kluczami rejestracyjnymi
@app.route('/admin/keys', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_keys():
    # Można dodać sprawdzenie, czy użytkownik jest administratorem
    
    if request.method == 'POST' and 'generate_keys' in request.form:
        try:
            key_count = int(request.form.get('key_count', 10))
            key_count = min(max(1, key_count), 100)  # Ograniczenie do 1-100 kluczy
            
            for _ in range(key_count):
                # Generuj unikalny 16-znakowy klucz
                while True:
                    key = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
                    if not RegistrationKey.query.filter_by(key=key).first():
                        break
                
                new_key = RegistrationKey(key=key)
                db.session.add(new_key)
                
            db.session.commit()
            flash(f'Wygenerowano {key_count} nowych kluczy rejestracyjnych.')
        except Exception as e:
            db.session.rollback()
            flash(f'Wystąpił błąd podczas generowania kluczy: {str(e)}')
    
    # Pobierz wszystkie klucze
    keys = RegistrationKey.query.order_by(RegistrationKey.created_at.desc()).all()
    
    return render_template('admin_keys.html', keys=keys)

# Wylogowanie
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Wyszukiwanie GPZ
@app.route('/wyszukaj', methods=['GET', 'POST'])
@login_required
def wyszukaj_gpz():
    wyniki = []
    user_lat = None
    user_lng = None
    user_address = None
    
    # Sprawdź czy użytkownik ma dostępne zapytania
    current_month = datetime.now().strftime('%Y-%m')
    
    try:
        user_queries = UserQueries.query.filter_by(user_id=current_user.id, month=current_month).first()
        if not user_queries:
            user_queries = UserQueries(user_id=current_user.id, month=current_month, query_count=0)
            db.session.add(user_queries)
            db.session.commit()
            
        pozostale_zapytania = 100 - user_queries.query_count
    except Exception as e:
        db.session.rollback()
        flash(f'Wystąpił błąd podczas sprawdzania limitów zapytań: {str(e)}')
        pozostale_zapytania = 0
    
    if request.method == 'POST':
        adres = request.form.get('adres')
        
        # Walidacja danych wejściowych
        if not adres:
            flash('Proszę wprowadzić adres.')
            return render_template('wyszukaj.html', wyniki=wyniki, user_lat=user_lat, user_lng=user_lng,
                                  user_address=user_address, pozostale_zapytania=pozostale_zapytania)
                                  
        # Usunięcie potencjalnie niebezpiecznych znaków
        adres = re.sub(r'[<>\'";]', '', adres)
        
        if adres:
            # Sprawdź czy użytkownik ma dostępne zapytania
            if pozostale_zapytania <= 0:
                flash('Wykorzystałeś limit zapytań na ten miesiąc. Limit zostanie odnowiony na początku następnego miesiąca.')
                return render_template('wyszukaj.html', wyniki=wyniki, user_lat=user_lat, user_lng=user_lng,
                                      user_address=user_address, pozostale_zapytania=pozostale_zapytania)
            
            wspolrzedne = geokoduj_adres(adres)
            if wspolrzedne:
                lat, lon = wspolrzedne
                user_lat = lat
                user_lng = lon
                user_address = adres
                
                try:
                    najblizsze_gpz = znajdz_najblizsze_gpz(lat, lon)
                    wyniki = []
                    
                    for gpz, odleglosc in najblizsze_gpz:
                        pelny_adres = f"{gpz['adres']}, {gpz['miasto']}"
                        if gpz['kod_pocztowy']:
                            pelny_adres += f", {gpz['kod_pocztowy']}"
                            
                        wyniki.append({
                            'nazwa': gpz['nazwa'],
                            'adres': pelny_adres,
                            'odleglosc': f"{odleglosc:.2f} km",
                            'dostepna_moc': f"{gpz['dostepna_moc']} MW",
                            'latitude': gpz['latitude'],
                            'longitude': gpz['longitude'],
                            'dystrybutor': gpz['dystrybutor'],
                            'moc_2025': gpz['moc_2025'],
                            'moc_2026': gpz['moc_2026'],
                            'moc_2027': gpz['moc_2027'],
                            'moc_2028': gpz['moc_2028'],
                            'moc_2029': gpz['moc_2029'],
                            'moc_2030': gpz['moc_2030']
                        })
                    
                    # Zwiększ licznik zapytań
                    user_queries.query_count += 1
                    db.session.commit()
                    pozostale_zapytania = 100 - user_queries.query_count
                except Exception as e:
                    db.session.rollback()
                    flash(f'Wystąpił błąd podczas wyszukiwania: {str(e)}')
            else:
                flash('Nie udało się odnaleźć podanego adresu.')
    
    return render_template('wyszukaj.html', wyniki=wyniki, user_lat=user_lat, user_lng=user_lng,
                          user_address=user_address, pozostale_zapytania=pozostale_zapytania)

# Panel administracyjny do zarządzania danymi GPZ
@app.route('/admin/gpz', methods=['GET', 'POST'])
@admin_required
@login_required
def admin_gpz():
    # Tutaj można dodać dodatkowe sprawdzenie, czy użytkownik ma uprawnienia administratora
    
    if request.method == 'POST':
        if 'dodaj_gpz' in request.form:
            nazwa = request.form.get('nazwa')
            adres = request.form.get('adres')
            miasto = request.form.get('miasto')
            kod_pocztowy = request.form.get('kod_pocztowy', '')
            dystrybutor = request.form.get('dystrybutor')
            
            # Geokodowanie adresu
            pelny_adres = f"{adres}, {miasto}, {kod_pocztowy}"
            wspolrzedne = geokoduj_adres(pelny_adres)
            
            if wspolrzedne:
                lat, lon = wspolrzedne
                dostepna_moc = float(request.form.get('dostepna_moc', 0))
                moc_2025 = float(request.form.get('moc_2025', 0))
                moc_2026 = float(request.form.get('moc_2026', 0))
                moc_2027 = float(request.form.get('moc_2027', 0))
                moc_2028 = float(request.form.get('moc_2028', 0))
                moc_2029 = float(request.form.get('moc_2029', 0))
                moc_2030 = float(request.form.get('moc_2030', 0))
                
                # Dodanie nowego GPZ do pliku CSV
                df = pd.read_csv(app.config['GPZ_CSV_PATH'])
                nowy_wpis = pd.DataFrame([{
                    'nazwa': nazwa,
                    'adres': adres,
                    'miasto': miasto,
                    'kod_pocztowy': kod_pocztowy,
                    'latitude': lat,
                    'longitude': lon,
                    'dostepna_moc': dostepna_moc,
                    'dystrybutor': dystrybutor,
                    'moc_2025': moc_2025,
                    'moc_2026': moc_2026,
                    'moc_2027': moc_2027,
                    'moc_2028': moc_2028,
                    'moc_2029': moc_2029,
                    'moc_2030': moc_2030
                }])
                
                df = pd.concat([df, nowy_wpis], ignore_index=True)
                df.to_csv(app.config['GPZ_CSV_PATH'], index=False)
                
                flash('Nowy GPZ został dodany pomyślnie.')
            else:
                flash('Nie udało się geokodować podanego adresu.')
    
    # Wczytaj aktualną listę GPZ
    gpz_data = load_gpz_data()
    
    return render_template('admin_gpz.html', gpz_data=gpz_data)

if __name__ == '__main__':
    app.run(debug=True)