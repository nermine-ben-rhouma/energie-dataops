import requests

# 1) eCO2mix : les 5 dernières mesures nationales
url_eco2mix = (
    "https://odre.opendatasoft.com/api/explore/v2.1/catalog/"
    "datasets/eco2mix-national-tr/records"
)
r = requests.get(
    url_eco2mix,
    params={"limit": 5, "order_by": "date_heure desc"},
    timeout=30,
)
print("eCO2mix - code HTTP :", r.status_code)
data = r.json()
print("Lignes dans le jeu de données :", data.get("total_count"))
premiere = data["results"][0]
print("Colonnes disponibles :", list(premiere.keys()))
print("Dernière mesure :", premiere.get("date_heure"), "| consommation :", premiere.get("consommation"))

# 2) Open-Meteo : météo horaire de Paris sur une semaine passée
url_meteo = "https://archive-api.open-meteo.com/v1/archive"
r = requests.get(
    url_meteo,
    params={
        "latitude": 48.85,
        "longitude": 2.35,
        "start_date": "2026-10-20",
        "end_date": "2026-10-26",
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
    },
    timeout=30,
)
print("Open-Meteo - code HTTP :", r.status_code)
meteo = r.json()["hourly"]
print("Nombre d'heures reçues :", len(meteo["time"]))
print("Première heure :", meteo["time"][0], "| température :", meteo["temperature_2m"][0])