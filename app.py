from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tajny-klucz-aplikacji'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///baza.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

# Model GPZ
class GPZ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazwa = db.Column(db.String(100), nullable=False)
    adres = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    dostepna_moc = db.Column(db.Float, nullable=False)  # w MW

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Inicjalizacja bazy danych
with app.app_context():
    db.create_all()
    
    # Sprawdź czy mamy już dane GPZ w bazie, jeśli nie - dodaj przykładowe
    if GPZ.query.count() == 0:
        przykładowe_gpz = [
            GPZ(nazwa="GPZ Centrum", adres="ul. Przykładowa 1, Warszawa", latitude=52.2297, longitude=21.0122, dostepna_moc=10.5),
            GPZ(nazwa="GPZ Wschód", adres="ul. Wschodnia 15, Warszawa", latitude=52.2360, longitude=21.0212, dostepna_moc=8.2),
            GPZ(nazwa="GPZ Zachód", adres="ul. Zachodnia 7, Warszawa", latitude=52.2299, longitude=20.9762, dostepna_moc=12.0),
            # Tutaj dodaj więcej GPZ z Twojej listy
        ]
        db.session.add_all(przykładowe_gpz)
        db.session.commit()

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
    wszystkie_gpz = GPZ.query.all()
    
    # Oblicz odległość dla każdego GPZ
    gpz_z_odlegloscia = []
    for gpz in wszystkie_gpz:
        odleglosc = geodesic((lat, lon), (gpz.latitude, gpz.longitude)).kilometers
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
                    wyniki.append({
                        'nazwa': gpz.nazwa,
                        'adres': gpz.adres,
                        'odleglosc': f"{odleglosc:.2f} km",
                        'dostepna_moc': f"{gpz.dostepna_moc} MW",
                        'latitude': gpz.latitude,
                        'longitude': gpz.longitude
                    })
            else:
                flash('Nie udało się odnaleźć podanego adresu.')
    
    return render_template('wyszukaj.html', wyniki=wyniki, user_lat=user_lat, user_lng=user_lng, user_address=user_address)

if __name__ == '__main__':
    app.run(debug=True)