# Énergie DataOps

Plateforme de données sur l'électricité en France : on collecte la production et la consommation d'électricité (eCO2mix de RTE) et la météo (Open-Meteo), on les charge dans un entrepôt DuckDB, et on orchestre le tout avec Prefect.

## Sources de données

| Source | Contenu | Clé API |
| --- | --- | --- |
| eCO2mix (RTE, via le portail ODRÉ) | Production par filière et consommation, par région, toutes les 30 minutes (historique 2021 à 2026) et au niveau national, toutes les 15 minutes (données récentes) | Non |
| Open-Meteo | Température, précipitations et vent, heure par heure, pour Paris, Lyon et Marseille | Non |

Toutes les heures sont stockées en **UTC**.

## Architecture

```
Sources (eCO2mix, Open-Meteo)
   -> dlt (ingestion idempotente)
   -> DuckDB, schéma raw
   -> dbt (staging, intermediate, marts)
   -> tableau de bord

Orchestration : Prefect (relances, exécution quotidienne)
Alertes : Discord en cas d'échec
Stockage objet : MinIO (Docker Compose)
```

## Prérequis

- Git
- **Python 3.12** (Prefect et dlt ne s'installent pas correctement avec Python 3.14)
- Docker Desktop

## Installation

```powershell
git clone https://github.com/nermine-ben-rhouma/energie-dataops.git
cd energie-dataops
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configuration

Copier `.env.example` en `.env`, puis renseigner les valeurs :

| Variable | Rôle |
| --- | --- |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Identifiants de MinIO (mot de passe de 8 caractères minimum) |
| `DISCORD_WEBHOOK_URL` | Adresse du webhook pour les alertes (facultative) |

Le fichier `.env` contient des secrets : il ne doit **jamais** être envoyé sur GitHub.

## Lancer le projet

**Stockage MinIO**

```powershell
docker compose up -d
```

Console web : http://localhost:9001

**Ingestion à la main** (la base `energie.duckdb` est créée à la racine)

```powershell
python ingestion/eco2mix_pipeline.py                # hier
python ingestion/eco2mix_pipeline.py 2026-10-28     # un jour précis
python ingestion/meteo_pipeline.py 2021-01-01 2026-08-31   # une période
python ingestion/regional_backfill.py 2021-01 2026-08      # historique régional, mois par mois
```

Relancer une même période ne crée pas de doublons : l'ingestion est idempotente.

**Orchestration avec Prefect** (deux terminaux)

```powershell
prefect server start                       # terminal 1, interface sur http://127.0.0.1:4200
python orchestration/serve.py              # terminal 2, exécution quotidienne à 07:00 UTC
python orchestration/flows.py 2026-10-28   # un jour précis, sans serveur
python orchestration/flows.py --echec      # test de l'alerte Discord
```

## Structure du dépôt

```
ingestion/       scripts dlt (eCO2mix national et régional, météo)
orchestration/   flux Prefect et déploiement programmé
docker-compose.yml   MinIO
requirements.txt     dépendances Python
```

## Points d'attention sur les données

- Dans eCO2mix régional, la colonne `eolien` arrive parfois en texte : elle est convertie en nombre à l'ingestion.
- La colonne `column_30` est vide : elle n'est pas chargée.
- Environ 0,01 % des mesures régionales manquent sur la période : un test de complétude est prévu côté dbt.
- L'image de MinIO n'est plus publiée officiellement depuis septembre 2026 : le projet utilise le fork Silo (voir les décisions d'architecture).

## Équipe

À compléter.