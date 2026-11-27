import sqlite3
import time
from contextlib import closing
from pathlib import Path

DOSSIER = Path(__file__).resolve().parents[1] / "monitoring"
BASE = DOSSIER / "monitoring.sqlite"


def enregistrer(
    source,
    jour,
    statut,
    duree_s,
    lignes_chargees=None,
    lignes_rejetees=0,
    derniere_donnee_ts=None,
):
    """Ajoute une ligne au journal des exécutions (lu ensuite par Grafana)."""
    DOSSIER.mkdir(exist_ok=True)
    with closing(sqlite3.connect(BASE)) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS runs (
                ts INTEGER NOT NULL,
                source TEXT NOT NULL,
                jour TEXT,
                statut TEXT NOT NULL,
                duree_s REAL,
                lignes_chargees INTEGER,
                lignes_rejetees INTEGER,
                derniere_donnee_ts INTEGER
            )"""
        )
        con.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(time.time()),
                source,
                jour,
                statut,
                duree_s,
                lignes_chargees,
                lignes_rejetees,
                derniere_donnee_ts,
            ),
        )
        con.commit()