import sys
from datetime import date, timedelta

import dlt
import requests

VILLES = {
    "Paris": (48.85, 2.35),
    "Lyon": (45.76, 4.84),
    "Marseille": (43.30, 5.37),
}

URL_RECENT = "https://api.open-meteo.com/v1/forecast"
URL_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


@dlt.resource(
    name="meteo_horaire",
    write_disposition="merge",
    primary_key=["ville", "heure"],
)
def meteo(jour: str):
    """Météo horaire d'une journée (AAAA-MM-JJ) pour plusieurs villes."""
    # Les jours récents ne sont pas encore dans l'archive : on change d'API.
    ancien = (date.today() - date.fromisoformat(jour)).days > 7
    url = URL_ARCHIVE if ancien else URL_RECENT

    for ville, (lat, lon) in VILLES.items():
        r = requests.get(
            url,
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": jour,
                "end_date": jour,
                "hourly": "temperature_2m,precipitation,wind_speed_10m",
                "timezone": "Europe/Paris",
            },
            timeout=30,
        )
        r.raise_for_status()
        h = r.json()["hourly"]
        yield [
            {
                "ville": ville,
                "heure": heure,
                "temperature_2m": temp,
                "precipitation": pluie,
                "wind_speed_10m": vent,
            }
            for heure, temp, pluie, vent in zip(
                h["time"], h["temperature_2m"], h["precipitation"], h["wind_speed_10m"]
            )
        ]


if __name__ == "__main__":
    jour = sys.argv[1] if len(sys.argv) > 1 else (date.today() - timedelta(days=1)).isoformat()
    pipeline = dlt.pipeline(
        pipeline_name="energie",
        destination="duckdb",
        dataset_name="raw",
    )
    print(pipeline.run(meteo(jour)))