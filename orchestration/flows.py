import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Permet d'importer les dossiers ingestion/ et orchestration/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dlt
import requests
from dotenv import load_dotenv
from prefect import flow, task

from ingestion.eco2mix_pipeline import eco2mix
from ingestion.meteo_pipeline import meteo
from orchestration.metriques import enregistrer

load_dotenv()  # lit le fichier .env


def alerter_discord(flow, flow_run, state):
    """Appelée automatiquement par Prefect quand le flux échoue."""
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        print("DISCORD_WEBHOOK_URL absent : alerte non envoyée")
        return
    jour = flow_run.parameters.get("jour") or "hier"
    message = (
        f"❌ Le flux **{flow.name}** a échoué "
        f"(jour : {jour}, exécution : {flow_run.name})."
    )
    requests.post(url, json={"content": message}, timeout=10)


def nouveau_pipeline():
    return dlt.pipeline(
        pipeline_name="energie",
        destination="duckdb",
        dataset_name="raw",
    )


def en_epoch(valeur):
    """Convertit une date en secondes depuis 1970 (UTC), ou None."""
    if valeur is None:
        return None
    if isinstance(valeur, str):
        valeur = datetime.fromisoformat(valeur)
    if valeur.tzinfo is None:
        valeur = valeur.replace(tzinfo=timezone.utc)
    return int(valeur.timestamp())


def executer_et_mesurer(source, jour, table, colonne_temps, lancer):
    """Lance un chargement et écrit ses chiffres dans le journal."""
    debut = time.time()
    pipeline = nouveau_pipeline()
    try:
        info = lancer(pipeline)
    except Exception:
        enregistrer(source, jour, "echec", round(time.time() - debut, 1))
        raise
    duree = round(time.time() - debut, 1)

    try:
        lignes = pipeline.last_trace.last_normalize_info.row_counts.get(table)
    except Exception:
        lignes = None

    try:
        with pipeline.sql_client() as client:
            requete = f"select max({colonne_temps}) from raw.{table}"
            derniere = en_epoch(client.execute_sql(requete)[0][0])
    except Exception:
        derniere = None

    enregistrer(source, jour, "ok", duree, lignes, 0, derniere)
    return str(info)


@task(retries=3, retry_delay_seconds=[10, 60, 300])
def charger_eco2mix(jour: str):
    return executer_et_mesurer(
        "eco2mix", jour, "eco2mix_national", "date_heure",
        lambda p: p.run(eco2mix(jour)),
    )


@task(retries=3, retry_delay_seconds=[10, 60, 300])
def charger_meteo(jour: str):
    return executer_et_mesurer(
        "meteo", jour, "meteo_horaire", "heure",
        lambda p: p.run(meteo(jour, jour)),
    )


@flow(name="ingestion-quotidienne", log_prints=True, on_failure=[alerter_discord])
def ingestion_quotidienne(jour: str | None = None, echec_test: bool = False):
    """Charge eCO2mix puis la météo pour un jour (par défaut : hier)."""
    jour = jour or (date.today() - timedelta(days=1)).isoformat()
    print(f"Ingestion du {jour}")
    if echec_test:
        raise RuntimeError("Échec volontaire pour tester l'alerte")
    charger_eco2mix(jour)
    charger_meteo(jour)


if __name__ == "__main__":
    # python orchestration/flows.py             -> hier
    # python orchestration/flows.py 2026-10-28  -> un jour précis
    # python orchestration/flows.py --echec     -> test de l'alerte
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ingestion_quotidienne(args[0] if args else None, echec_test="--echec" in sys.argv)