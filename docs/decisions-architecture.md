# Décisions d'architecture

Chaque décision indique le contexte, ce qui a été choisi, les alternatives écartées et les conséquences.

## 0. Niveau 1 : entrepôt ELT

- **Contexte** : le sujet prévoit un socle obligatoire (entrepôt ELT) et des briques avancées.
- **Décision** : dlt charge le brut dans DuckDB (couche `raw`), dbt le transformera ensuite en couches staging, intermediate et marts.
- **Alternatives** : le niveau 2 (lakehouse avec Parquet et Iceberg sur MinIO), réservé aux briques avancées.
- **Conséquences** : l'architecture reste simple à lancer et à tester. Le niveau 2 pourra être ajouté sans réécrire l'ingestion.

## 1. DuckDB comme entrepôt

- **Contexte** : un entrepôt analytique pour environ 1,2 million de lignes, sans serveur à administrer.
- **Décision** : DuckDB, dans un seul fichier (`data/energie.duckdb`).
- **Alternatives** : PostgreSQL (plus lourd à installer et à lancer pour ce volume).
- **Conséquences** : très simple à lancer et à sauvegarder, bon pour les requêtes analytiques. Limite : un seul processus peut écrire à la fois, ce qui impose de ne pas lancer deux chargements en parallèle (voir le postmortem du game day).

## 2. dlt pour l'ingestion

- **Contexte** : charger des API paginées de façon répétable et sans doublon.
- **Décision** : dlt, avec écriture par fusion (`merge`) et clé primaire.
- **Alternatives** : scripts Python écrivant directement dans DuckDB.
- **Conséquences** : un chargement relancé sur la même période ne crée pas de doublon (idempotence), ce qui rend le backfill et le rattrapage sûrs. Le postmortem l'a vérifié : 192 lignes pour 192 dates-heures distinctes, malgré deux chargements du même jour.

## 3. Prefect pour l'orchestration

- **Contexte** : exécution quotidienne, relances, historique des exécutions.
- **Décision** : Prefect 3, avec 3 relances par tâche (10 s, 1 min, 5 min) et une alerte Discord en cas d'échec définitif.
- **Alternatives** : Airflow (plus lourd à lancer pour deux tâches).
- **Conséquences** : le flux accepte un paramètre `jour`, ce qui donne un backfill par date. Le déploiement tourne dans Docker Compose.

## 4. Silo à la place de MinIO

- **Contexte** : le sujet cite MinIO. L'image `quay.io/minio/minio` que nous avions choisie a fini par répondre `401 Unauthorized` au téléchargement, car les images officielles ne sont plus publiées.
- **Décision** : utiliser Silo (`pgsty/silo`), un fork compatible qui garde les mêmes variables d'environnement.
- **Alternatives** : Chainguard MinIO (sans shell, permissions plus délicates), SeaweedFS.
- **Conséquences** : le service est déployé, comme l'exige le socle. Les pipelines n'y déposent pas encore de fichiers : le niveau 1 charge directement dans DuckDB, et l'usage de MinIO comme stockage des données (Parquet puis Iceberg) correspond au niveau 2, avancé.

## 5. Journal SQLite pour Grafana

- **Contexte** : Grafana ne peut pas lire DuckDB pendant qu'un chargement y écrit (un seul écrivain à la fois).
- **Décision** : chaque exécution écrit une ligne (source, durée, lignes, rejets, fraîcheur) dans un petit fichier SQLite, monté en lecture seule dans Grafana avec le plugin SQLite.
- **Alternatives** : plugin DuckDB pour Grafana (conflits de verrou), Prometheus (trop lourd pour ce besoin).
- **Conséquences** : le tableau de bord est indépendant de l'entrepôt. Le journal n'est pas versionné, mais son schéma est défini dans le code (`orchestration/metriques.py`).

## 6. Python 3.12

- **Contexte** : sur Python 3.14, l'installation de Prefect et de dlt a échoué (conflit de dépendances).
- **Décision** : Python 3.12, dans le Dockerfile et dans l'environnement local.
- **Conséquences** : installation reproductible. Dans Docker, la version est fixée par l'image `python:3.12-slim`.

## 7. Heures en UTC

- **Contexte** : la météo avait d'abord été demandée en heure de Paris. Au changement d'heure d'hiver, une même heure locale existe deux fois, ce qui ferait entrer deux lignes en collision sur la clé (`ville`, `heure`).
- **Décision** : tout stocker en UTC, comme eCO2mix.
- **Conséquences** : pas de collision, et jointure directe entre énergie et météo.

## 8. Historique chargé par exports mensuels

- **Contexte** : l'API de recherche ne livre qu'environ 100 lignes par appel, et le jeu impose un quota d'appels par utilisateur.
- **Décision** : l'historique régional est chargé par l'endpoint d'export, mois par mois (68 appels pour 1,19 million de lignes).
- **Alternatives** : boucle de pagination jour par jour (des dizaines de milliers d'appels).
- **Conséquences** : chaque mois prend 5 à 10 secondes, et une interruption se reprend sans doublon.

## 9. Installation du plugin Grafana

- **Contexte** : la variable `GF_INSTALL_PLUGINS` est dépréciée depuis Grafana 12.1 ; notre premier essai l'utilisait et le plugin n'a pas été installé.
- **Décision** : `GF_PLUGINS_PREINSTALL_SYNC`.
- **Conséquences** : `docker compose up` installe le plugin sans action manuelle.