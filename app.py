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

# Funkcja do wczytania danych GPZ z pliku CSV
def load_gpz_data():
    gpz_data = []
    
    # Sprawdź czy plik CSV istnieje, jeśli nie - utwórz przykładowy plik
    if not os.path.exists(app.config['GPZ_CSV_PATH']):
        with open(app.config['GPZ_CSV_PATH'], 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['nazwa', 'adres', 'miasto', 'kod_pocztowy', 'latitude', 'longitude', 'dostepna_moc']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            writer.writerow({
                'nazwa': 'GPZ Centrum', 
                'adres': 'ul. Przykładowa 1', 
                'miasto': 'Warszawa', 
                'kod_pocztowy': '00-001',
                'latitude': 52.2297, 
                'longitude': 21.0122, 
                'dostepna_moc': 10.5
            })
            writer.writerow({
                'nazwa': 'GPZ Wschód', 
                'adres': 'ul. Wschodnia 15', 
                'miasto': 'Warszawa', 
                'kod_pocztowy': '00-123',
                'latitude': 52.2360, 
                'longitude': 21.0212, 
                'dostepna_moc': 8.2
            })
            writer.writerow({
                'nazwa': 'GPZ Zachód', 
                'adres': 'ul. Zachodnia 7', 
                'miasto': 'Warszawa', 
                'kod_pocztowy': '00-456',
                'latitude': 52.2299, 
                'longitude': 20.9762, 
                'dostepna_moc': 12.0
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
    
    if request.method == 'POST':
        adres = request.form.get('adres')
        if adres:
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
                        'longitude': gpz['longitude']
                    })
            else:
                flash('Nie udało się odnaleźć podanego adresu.')
    
    return render_template('wyszukaj.html', wyniki=wyniki, user_lat=user_lat, user_lng=user_lng, user_address=user_address)

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
            
            # Geokodowanie adresu
            pelny_adres = f"{adres}, {miasto}, {kod_pocztowy}"
            wspolrzedne = geokoduj_adres(pelny_adres)
            
            if wspolrzedne:
                lat, lon = wspolrzedne
                dostepna_moc = float(request.form.get('dostepna_moc', 0))
                
                # Dodanie nowego GPZ do pliku CSV
                df = pd.read_csv(app.config['GPZ_CSV_PATH'])
                nowy_wpis = pd.DataFrame([{
                    'nazwa': nazwa,
                    'adres': adres,
                    'miasto': miasto,
                    'kod_pocztowy': kod_pocztowy,
                    'latitude': lat,
                    'longitude': lon,
                    'dostepna_moc': dostepna_moc
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