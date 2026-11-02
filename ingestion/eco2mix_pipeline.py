import sys
from datetime import date, timedelta

import dlt
import requests

URL = (
    "https://odre.opendatasoft.com/api/explore/v2.1/catalog/"
    "datasets/eco2mix-national-tr/records"
)


@dlt.resource(
    name="eco2mix_national",
    write_disposition="merge",   # relancer = mettre à jour, pas dupliquer
    primary_key="date_heure",
)
def eco2mix(jour: str):
    """Mesures eCO2mix d'une journée (format AAAA-MM-JJ)."""
    offset = 0
    while True:
        r = requests.get(
            URL,
            params={
                "where": f'date = "{jour}"',
                "order_by": "date_heure asc",
                "limit": 100,
                "offset": offset,
            },
            timeout=30,
        )
        r.raise_for_status()
        page = r.json()["results"]
        if not page:
            break
        yield page
        offset += 100


if __name__ == "__main__":
    # Sans argument : hier. Sinon : python ingestion/eco2mix_pipeline.py 2026-10-28
    jour = sys.argv[1] if len(sys.argv) > 1 else (date.today() - timedelta(days=1)).isoformat()
    pipeline = dlt.pipeline(
        pipeline_name="energie",
        destination="duckdb",
        dataset_name="raw",
    )
    print(pipeline.run(eco2mix(jour)))