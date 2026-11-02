import sys
import time

import dlt
from dlt.sources.helpers import requests  # même interface, avec relances automatiques

URL = (
    "https://odre.opendatasoft.com/api/explore/v2.1/catalog/"
    "datasets/eco2mix-regional-cons-def/exports/json"
)

COLONNES_TEXTE = ["code_insee_region", "libelle_region", "nature", "date_heure"]
COLONNES_NOMBRE = [
    "consommation", "thermique", "nucleaire", "eolien", "solaire",
    "hydraulique", "pompage", "bioenergies", "ech_physiques",
]


def en_nombre(valeur):
    """Convertit en nombre ; None si la valeur est vide ou invalide."""
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def mois_suivant(annee, mois):
    return (annee + 1, 1) if mois == 12 else (annee, mois + 1)


@dlt.resource(
    name="eco2mix_regional",
    write_disposition="merge",   # relancer = mettre à jour, jamais de doublon
    primary_key=["code_insee_region", "date_heure"],
)
def eco2mix_regional(annee: int, mois: int):
    """Toutes les mesures régionales d'un mois."""
    a2, m2 = mois_suivant(annee, mois)
    debut = f"{annee}-{mois:02d}-01T00:00:00"
    fin = f"{a2}-{m2:02d}-01T00:00:00"
    r = requests.get(
        URL,
        params={
            "where": f'date_heure >= "{debut}" and date_heure < "{fin}"',
            "select": ", ".join(COLONNES_TEXTE + COLONNES_NOMBRE),
        },
        timeout=300,
    )
    r.raise_for_status()
    lignes = []
    for l in r.json():
        if not l.get("date_heure"):
            continue
        ligne = {c: l.get(c) for c in COLONNES_TEXTE}
        ligne.update({c: en_nombre(l.get(c)) for c in COLONNES_NOMBRE})
        lignes.append(ligne)
    yield lignes


def lire_mois(texte):
    annee, mois = texte.split("-")
    return int(annee), int(mois)


if __name__ == "__main__":
    # Exemple : python ingestion/regional_backfill.py 2026-08 2026-08
    debut, fin = lire_mois(sys.argv[1]), lire_mois(sys.argv[2])
    pipeline = dlt.pipeline(
        pipeline_name="energie",
        destination="duckdb",
        dataset_name="raw",
    )
    a, m = debut
    while (a, m) <= fin:
        t0 = time.time()
        pipeline.run(eco2mix_regional(a, m))
        print(f"{a}-{m:02d} chargé en {time.time() - t0:.0f} s", flush=True)
        a, m = mois_suivant(a, m)