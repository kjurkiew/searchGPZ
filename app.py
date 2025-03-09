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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tajny-klucz-aplikacji'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///baza.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['GPZ_CSV_PATH'] = 'gpz_database.csv'  # Ścieżka do pliku CSV

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Model użytkownika
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Add the UserQueries model to track user query limits
class UserQueries(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # Format: YYYY-MM
    query_count = db.Column(db.Integer, default=0)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'month', name='unique_user_month'),
    )

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
                'dostepna_moc': float(row['dostepna_moc'])
            })
    except Exception as e:
        print(f"Błąd wczytywania danych GPZ: {e}")
    
    return gpz_data

# Inicjalizacja bazy danych
with app.app_context():
    db.create_all()

# Funkcja do geokodowania adresu (zamiana adresu na współrzędne)
def geokoduj_adres(adres):
    geolocator = Nominatim(user_agent="gpz-finder")
    try:
        location = geolocator.geocode(adres + ", Polska")
        if location:
            return (location.latitude, location.longitude)
        return None
    except:
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
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('wyszukaj_gpz'))
        else:
            flash('Nieprawidłowa nazwa użytkownika lub hasło.')
    
    return render_template('login.html')

# Rejestracja
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(username=username).first()
        
        if existing_user:
            flash('Nazwa użytkownika jest już zajęta.')
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('Rejestracja zakończona pomyślnie. Możesz się teraz zalogować.')
            return redirect(url_for('login'))
    
    return render_template('register.html')

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
    from datetime import datetime
    current_month = datetime.now().strftime('%Y-%m')
    
    user_queries = UserQueries.query.filter_by(user_id=current_user.id, month=current_month).first()
    
    if not user_queries:
        user_queries = UserQueries(user_id=current_user.id, month=current_month, query_count=0)
        db.session.add(user_queries)
        db.session.commit()
    
    pozostale_zapytania = 100 - user_queries.query_count
    
    if request.method == 'POST':
        adres = request.form.get('adres')
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
            else:
                flash('Nie udało się odnaleźć podanego adresu.')
    
    return render_template('wyszukaj.html', wyniki=wyniki, user_lat=user_lat, user_lng=user_lng, 
                          user_address=user_address, pozostale_zapytania=pozostale_zapytania)

# Panel administracyjny do zarządzania danymi GPZ
@app.route('/admin/gpz', methods=['GET', 'POST'])
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