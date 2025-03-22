# searchGPZ
[![searchGPZ CI](https://github.com/kjurkiew/searchGPZ/actions/workflows/ci.yml/badge.svg)](https://github.com/kjurkiew/searchGPZ/actions/workflows/ci.yml)

An application for finding the nearest GPZ with available power, facilitating the installation of electrical systems such as solar panels, wind turbines, and biogas plants.

## Overview

searchGPZ is an application that solves the problem of finding a suitable location to connect to the electrical grid, especially when GPZ networks are overloaded. Users can enter an address and receive information about the three nearest GPZs along with their available power.

## Features

- **Registration and Login** – Users can create accounts and log in to the application.  
- **Address Search** – Functionality allowing users to enter an address and find the nearest GPZs.  
- **Power Availability** – Displays information about the available power at each GPZ.
- **Future Capacity Projections** - Shows power capacity forecasts for years 2025-2030.
- **Monthly Query Limit** - Users have a limit of 100 queries per month.
- **Admin Panel** - Administrators can manage GPZ data through a dedicated interface.  

## Technologies Used

- **Python** – The primary programming language.  
- **Flask** – The web framework used to build the application.  
- **Geopy** – A library for geolocation and geographic data processing.
- **SQLAlchemy** - ORM for database management.
- **Pandas** - For data processing and CSV handling.
- **HTML** – Used for creating the user interface.  

## Installation

To install the application, follow these steps:

```bash
git clone https://github.com/kjurkiew/searchGPZ.git
cd searchGPZ
pip install -r requirements.txt
python app.py
```
## Usage

To use the application, follow these steps:

1. **Run the application**  
   ```bash
   python app.py
2. **Register or log in**
Enter a location to find the nearest GPZs.

## Future Plans
We plan to introduce a token system, which will allow users to access the application for a fee. Each entry to the site will require a certain number of tokens.

## License
Copyright © 2025. All Rights Reserved.
