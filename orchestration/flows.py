import sys
from datetime import date, timedelta
from pathlib import Path

# Permet d'importer le dossier ingestion/ depuis ce fichier
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dlt
from prefect import flow, task

from ingestion.eco2mix_pipeline import eco2mix
from ingestion.meteo_pipeline import meteo


def nouveau_pipeline():
    return dlt.pipeline(
        pipeline_name="energie",
        destination="duckdb",
        dataset_name="raw",
    )


@task(retries=3, retry_delay_seconds=[10, 60, 300])
def charger_eco2mix(jour: str):
    return str(nouveau_pipeline().run(eco2mix(jour)))


@task(retries=3, retry_delay_seconds=[10, 60, 300])
def charger_meteo(jour: str):
    return str(nouveau_pipeline().run(meteo(jour, jour)))


@flow(name="ingestion-quotidienne", log_prints=True)
def ingestion_quotidienne(jour: str | None = None):
    """Charge eCO2mix puis la météo pour un jour (par défaut : hier)."""
    jour = jour or (date.today() - timedelta(days=1)).isoformat()
    print(f"Ingestion du {jour}")
    charger_eco2mix(jour)
    charger_meteo(jour)


if __name__ == "__main__":
    ingestion_quotidienne(sys.argv[1] if len(sys.argv) > 1 else None)