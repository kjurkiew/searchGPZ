# test_unit_helpers.py
import pytest
from unittest.mock import patch, MagicMock, mock_open
import pandas as pd
from io import StringIO # Do mockowania odczytu CSV
from app import geokoduj_adres, znajdz_najblizsze_gpz, load_gpz_data, app

# --- Testy dla geokoduj_adres ---

@patch('app.Nominatim') # Mockuj klasę Nominatim w module app
def test_geokoduj_adres_success(MockNominatim):
    """Testuje geokodowanie z poprawnym wynikiem."""
    # Przygotuj mock geolocatora i jego metody geocode
    mock_geolocator = MockNominatim.return_value
    mock_location = MagicMock()
    mock_location.latitude = 52.123
    mock_location.longitude = 21.456
    mock_geolocator.geocode.return_value = mock_location

    adres = "Warszawa, ul. Testowa 1"
    result = geokoduj_adres(adres)

    assert result == (52.123, 21.456)
    MockNominatim.assert_called_once_with(user_agent="gpz-finder")
    mock_geolocator.geocode.assert_called_once_with(adres + ", Polska")

@patch('app.Nominatim')
def test_geokoduj_adres_not_found(MockNominatim):
    """Testuje geokodowanie, gdy adres nie zostanie znaleziony."""
    mock_geolocator = MockNominatim.return_value
    mock_geolocator.geocode.return_value = None # Symulacja braku wyniku

    result = geokoduj_adres("Nieistniejacy Adres 123")
    assert result is None
    mock_geolocator.geocode.assert_called_once_with("Nieistniejacy Adres 123, Polska")

@patch('app.Nominatim')
def test_geokoduj_adres_exception(MockNominatim, capsys):
    """Testuje geokodowanie, gdy wystąpi wyjątek."""
    mock_geolocator = MockNominatim.return_value
    mock_geolocator.geocode.side_effect = Exception("API Error") # Symulacja błędu

    result = geokoduj_adres("Adres Błędny")
    assert result is None

    # Sprawdź, czy błąd został zalogowany (jeśli app.py używa print lub logging)
    captured = capsys.readouterr()
    assert "Błąd geokodowania: API Error" in captured.out or "Błąd geokodowania: API Error" in captured.err


# --- Testy dla load_gpz_data ---

@patch('app.pd.read_csv') # Mockuj odczyt CSV w module app
@patch('app.os.path.exists') # Mockuj sprawdzanie istnienia pliku
def test_load_gpz_data_success(mock_exists, mock_read_csv):
    """Testuje poprawne wczytanie danych GPZ z mockowanego CSV."""
    mock_exists.return_value = True # Symuluj, że plik istnieje
    
    # Tworzę DataFrame bezpośrednio, bez wywoływania pd.read_csv
    mock_read_csv.return_value = pd.DataFrame([
        {'nazwa': 'GPZ Test 1', 'adres': 'ul. CSV 1', 'miasto': 'Miasto Test', 'kod_pocztowy': '11-111', 
         'latitude': 50.1, 'longitude': 20.1, 'dostepna_moc': 10.0, 'dystrybutor': 'Dist A',
         'moc_2025': 10.1, 'moc_2026': 10.2, 'moc_2027': 10.3, 'moc_2028': 10.4, 'moc_2029': 10.5, 'moc_2030': 10.6},
        {'nazwa': 'GPZ Test 2', 'adres': 'ul. CSV 2', 'miasto': 'Miasto Test', 'kod_pocztowy': '22-222', 
         'latitude': 50.2, 'longitude': 20.2, 'dostepna_moc': 12.5, 'dystrybutor': 'Dist B',
         'moc_2025': 12.6, 'moc_2026': 12.7, 'moc_2027': 12.8, 'moc_2028': 12.9, 'moc_2029': 13.0, 'moc_2030': 13.1}
    ])

    # Użyj kontekstu aplikacji, aby uzyskać dostęp do app.config['GPZ_CSV_PATH']
    with app.app_context():
        app.config['GPZ_CSV_PATH'] = 'test_gpz.csv'  # Ustaw ścieżkę testową
        gpz_data = load_gpz_data()

        mock_exists.assert_called_once_with(app.config['GPZ_CSV_PATH'])
        mock_read_csv.assert_called_once_with(app.config['GPZ_CSV_PATH'])

        assert isinstance(gpz_data, list)
        assert len(gpz_data) == 2
        assert gpz_data[0]['nazwa'] == 'GPZ Test 1'
        assert gpz_data[0]['latitude'] == 50.1
        assert gpz_data[0]['dostepna_moc'] == 10.0
        assert gpz_data[0]['moc_2030'] == 10.6
        assert gpz_data[1]['nazwa'] == 'GPZ Test 2'
        assert gpz_data[1]['dystrybutor'] == 'Dist B'
        assert 'pelny_adres' in gpz_data[0]
        assert gpz_data[0]['pelny_adres'] == 'ul. CSV 1, Miasto Test, 11-111'

@patch('app.os.path.exists')
@patch('builtins.open', new_callable=mock_open) # Mockuj otwieranie/pisanie pliku
@patch('app.csv.DictWriter') # Mockuj zapis CSV
@patch('app.pd.read_csv')
def test_load_gpz_data_creates_file_if_not_exists(mock_read_csv, mock_csv_writer, mock_open_func, mock_exists):
    """Testuje, czy plik CSV jest tworzony, gdy nie istnieje."""
    mock_exists.return_value = False # Symuluj brak pliku

    # Mock read_csv, aby zwrócił pusty DataFrame po utworzeniu pliku
    mock_read_csv.return_value = pd.DataFrame(columns=[
        'nazwa', 'adres', 'miasto', 'kod_pocztowy', 'latitude', 'longitude', 'dostepna_moc',
        'dystrybutor', 'moc_2025', 'moc_2026', 'moc_2027', 'moc_2028', 'moc_2029', 'moc_2030'
    ])

    # Tworzymy mock dla DictWriter.writeheader i writerow
    mock_writer_instance = mock_csv_writer.return_value
    mock_writer_instance.writeheader = MagicMock()
    mock_writer_instance.writerow = MagicMock()

    with app.app_context():
        app.config['GPZ_CSV_PATH'] = 'test_gpz.csv'  # Ustaw ścieżkę testową
        gpz_data = load_gpz_data()

    assert mock_exists.call_count == 1 # Sprawdzono raz
    # Sprawdź, czy próbowano otworzyć plik do zapisu ('w')
    mock_open_func.assert_called_once_with('test_gpz.csv', 'w', newline='', encoding='utf-8')
    # Sprawdź, czy DictWriter został użyty do zapisania nagłówka i danych domyślnych
    assert mock_writer_instance.writeheader.call_count == 1
    assert mock_writer_instance.writerow.call_count == 3  # Trzy domyślne wpisy w pliku CSV
    # Sprawdź, czy read_csv zostało wywołane po utworzeniu pliku
    assert mock_read_csv.call_count == 1
    assert isinstance(gpz_data, list)


# --- Testy dla znajdz_najblizsze_gpz ---

@patch('app.load_gpz_data') # Mockuj ładowanie danych, aby kontrolować dane wejściowe
@patch('app.geodesic')    # Mockuj obliczanie odległości
def test_znajdz_najblizsze_gpz_finds_correct_limit(mock_geodesic, mock_load_data):
    """Testuje znajdowanie najbliższych GPZ z mockowanymi danymi i odległościami."""
    # Przygotuj mockowane dane GPZ
    mock_data = [
        {'nazwa': 'GPZ A', 'latitude': 50.0, 'longitude': 20.0, 'dostepna_moc': 1, 'dystrybutor': 'X', 'adres': 'A1', 'miasto': 'M', 'kod_pocztowy': '', 'moc_2025': 1, 'moc_2026': 1, 'moc_2027': 1, 'moc_2028': 1, 'moc_2029': 1, 'moc_2030': 1},
        {'nazwa': 'GPZ B', 'latitude': 51.0, 'longitude': 21.0, 'dostepna_moc': 2, 'dystrybutor': 'Y', 'adres': 'B1', 'miasto': 'M', 'kod_pocztowy': '', 'moc_2025': 2, 'moc_2026': 2, 'moc_2027': 2, 'moc_2028': 2, 'moc_2029': 2, 'moc_2030': 2},
        {'nazwa': 'GPZ C', 'latitude': 52.0, 'longitude': 22.0, 'dostepna_moc': 3, 'dystrybutor': 'Z', 'adres': 'C1', 'miasto': 'M', 'kod_pocztowy': '', 'moc_2025': 3, 'moc_2026': 3, 'moc_2027': 3, 'moc_2028': 3, 'moc_2029': 3, 'moc_2030': 3},
        {'nazwa': 'GPZ D', 'latitude': 53.0, 'longitude': 23.0, 'dostepna_moc': 4, 'dystrybutor': 'W', 'adres': 'D1', 'miasto': 'M', 'kod_pocztowy': '', 'moc_2025': 4, 'moc_2026': 4, 'moc_2027': 4, 'moc_2028': 4, 'moc_2029': 4, 'moc_2030': 4},
    ]
    mock_load_data.return_value = mock_data

    # Skonfiguruj mock geodesic, aby zwracał różne odległości
    # Symulujemy, że punkt (lat=50.0, lon=20.0) jest najbliższy GPZ A, potem B, C, D
    def geodesic_side_effect(point1, point2):
        mock_dist = MagicMock()
        if point2 == (50.0, 20.0): mock_dist.kilometers = 10.0 # A
        elif point2 == (51.0, 21.0): mock_dist.kilometers = 20.0 # B
        elif point2 == (52.0, 22.0): mock_dist.kilometers = 30.0 # C
        elif point2 == (53.0, 23.0): mock_dist.kilometers = 40.0 # D
        else: mock_dist.kilometers = 999.0
        return mock_dist

    mock_geodesic.side_effect = geodesic_side_effect

    user_lat, user_lon = 50.0, 20.0
    limit = 3
    najblizsze = znajdz_najblizsze_gpz(user_lat, user_lon, limit=limit)
    
    assert len(najblizsze) == limit
    # Sprawdź kolejność i zwrócone dane
    assert najblizsze[0][0]['nazwa'] == 'GPZ A'
    assert najblizsze[0][1] == 10.0 # Odległość
    assert najblizsze[1][0]['nazwa'] == 'GPZ B'
    assert najblizsze[1][1] == 20.0
    assert najblizsze[2][0]['nazwa'] == 'GPZ C'
    assert najblizsze[2][1] == 30.0

    # Sprawdź, ile razy wywołano geodesic - raz dla każdego GPZ w mock_data
    assert mock_geodesic.call_count == len(mock_data)