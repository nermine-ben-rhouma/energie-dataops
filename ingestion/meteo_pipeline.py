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
def meteo(debut: str, fin: str):
    """Météo horaire (en UTC) de plusieurs villes, entre deux dates AAAA-MM-JJ."""
    # Les jours récents ne sont pas encore dans l'archive : on change d'API.
    ancien = (date.today() - date.fromisoformat(fin)).days > 7
    url = URL_ARCHIVE if ancien else URL_RECENT

    for ville, (lat, lon) in VILLES.items():
        r = requests.get(
            url,
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": debut,
                "end_date": fin,
                "hourly": "temperature_2m,precipitation,wind_speed_10m",
                "timezone": "GMT",
            },
            timeout=120,
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
    # python ingestion/meteo_pipeline.py                      -> hier
    # python ingestion/meteo_pipeline.py 2026-10-20           -> un jour
    # python ingestion/meteo_pipeline.py 2021-01-01 2026-08-31 -> une période
    if len(sys.argv) >= 3:
        debut, fin = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 2:
        debut = fin = sys.argv[1]
    else:
        debut = fin = (date.today() - timedelta(days=1)).isoformat()

    pipeline = dlt.pipeline(
        pipeline_name="energie",
        destination="duckdb",
        dataset_name="raw",
    )
    print(pipeline.run(meteo(debut, fin)))