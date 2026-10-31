# Énergie DataOps

Plateforme de données sur l'électricité en France : on collecte la production et la consommation d'électricité (eCO2mix de RTE) et la météo (Open-Meteo), on les charge dans un entrepôt DuckDB, on les orchestre avec Prefect et on surveille les chargements avec Grafana. Tout se lance avec Docker Compose.

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
   -> DuckDB, schéma raw (data/energie.duckdb)
   -> dbt (staging, intermediate, marts)   [à venir]
   -> tableau de bord métier               [à venir]

Orchestration : Prefect (relances, exécution quotidienne à 07:00 UTC)
Alertes       : Discord en cas d'échec du flux
Surveillance  : journal SQLite (monitoring/) lu par Grafana
Stockage objet: MinIO (fork Silo)
Le tout est lancé par Docker Compose.
```

## Prérequis

- Git
- Docker Desktop

Python n'est pas nécessaire pour lancer la plateforme : tout tourne dans Docker (Python 3.12).

## Démarrage

```powershell
git clone https://github.com/nermine-ben-rhouma/energie-dataops.git
cd energie-dataops
mkdir data
```

Copier `.env.example` en `.env`, puis renseigner les valeurs :

| Variable | Rôle |
| --- | --- |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Identifiants de MinIO (mot de passe de 8 caractères minimum) |
| `GRAFANA_ADMIN_PASSWORD` | Mot de passe de l'utilisateur `admin` de Grafana |
| `DISCORD_WEBHOOK_URL` | Adresse du webhook pour les alertes (facultative) |

Le fichier `.env` contient des secrets : il ne doit **jamais** être envoyé sur GitHub.

Lancer toute la plateforme :

```powershell
docker compose up -d
```

| Service | Adresse | Rôle |
| --- | --- | --- |
| Prefect | http://localhost:4200 | Orchestration, historique des exécutions |
| Grafana | http://localhost:3000 | Surveillance (utilisateur `admin`) |
| MinIO | http://localhost:9001 | Stockage objet |

Le flux `ingestion-quotidienne` s'exécute chaque jour à 07:00 UTC et traite la veille.

## Charger l'historique

Au premier démarrage, la base `data/energie.duckdb` est vide. Pour charger l'historique (environ 1,19 million de lignes) :

```powershell
docker compose exec ingestion python /app/ingestion/regional_backfill.py 2021-01 2026-08
docker compose exec ingestion python /app/ingestion/meteo_pipeline.py 2021-01-01 2026-08-31
```

Chaque mois régional prend de 5 à 10 secondes. Relancer une même période ne crée pas de doublons : l'ingestion est idempotente.

## Lancer un jour précis

Dans l'interface Prefect : déploiement `ingestion-quotidienne-7h`, puis **Run**, **Custom run**, et renseigner le paramètre `jour` (par exemple `2026-10-28`).

## Surveillance

Chaque chargement écrit une ligne dans un journal SQLite (`monitoring/monitoring.sqlite`) : source, durée, nombre de lignes, lignes rejetées, fraîcheur. Le tableau de bord Grafana **Surveillance ingestion** affiche quatre indicateurs :

| Indicateur | Objectif |
| --- | --- |
| Fraîcheur des données | Moins de 36 heures (orange au-delà, rouge à partir de 46 heures) |
| Durée des chargements | Quelques secondes ; une dérive signale un problème |
| Lignes chargées par exécution | 96 pour eCO2mix national, 72 pour la météo |
| Échecs et rejets (7 jours) | 0 |

Le tableau de bord est versionné dans `grafana/dashboards/` et rechargé automatiquement au démarrage.

## Alertes

Si le flux échoue, après les 3 relances de chaque tâche (délais de 10 s, 1 min et 5 min), un message est envoyé sur Discord.

## Structure du dépôt

```
ingestion/       scripts dlt (eCO2mix national et régional, météo)
orchestration/   flux Prefect, déploiement programmé, journal des exécutions
grafana/         configuration et tableau de bord, chargés automatiquement
monitoring/      journal SQLite (non versionné)
data/            base DuckDB (non versionnée)
Dockerfile, docker-compose.yml, requirements.txt
```

## Points d'attention sur les données

- Dans eCO2mix régional, la colonne `eolien` arrive parfois en texte : elle est convertie en nombre à l'ingestion.
- La colonne `column_30` est vide : elle n'est pas chargée.
- Environ 0,01 % des mesures régionales manquent sur la période : un test de complétude est prévu côté dbt.
- L'image de MinIO n'est plus publiée officiellement : le projet utilise le fork Silo (voir les décisions d'architecture).

## Équipe

NERMINE BENRHOUMA
NADINE SNOUSSI
