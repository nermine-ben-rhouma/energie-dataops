# Runbook

Que faire quand quelque chose ne va pas. Chaque cas indique le symptôme, comment vérifier et comment réparer. Toutes les commandes se lancent à la racine du projet, dans PowerShell.

## Vérifications de base

```powershell
docker compose ps                              # les 4 conteneurs doivent être « Up », prefect-server « healthy »
docker compose logs ingestion --tail 50        # derniers messages du conteneur d'ingestion
```

Interfaces : Prefect http://localhost:4200, Grafana http://localhost:3000, MinIO http://localhost:9001.

## 1. Alerte Discord : « Le flux ingestion-quotidienne a échoué »

**Vérifier**
1. Ouvrir Prefect, menu **Runs**, cliquer sur l'exécution en échec, onglet **Logs** : la cause est dans le message d'erreur.
2. Tester la source :
```powershell
docker compose exec ingestion python -c "import requests; print(requests.get('https://odre.opendatasoft.com', timeout=10).status_code)"
```
Résultat attendu : `200`.

**Réparer**
- Si la source répond `200` : relancer le jour concerné (cas 3).
- Si la source ne répond pas : attendre son retour. Les données ne sont pas perdues, le jour sera rattrapé ensuite.
- Si une panne simulée est restée active (fichier `docker-compose.panne.yml`) : `docker compose up -d`.

## 2. Fraîcheur rouge dans Grafana (données de plus de 46 heures)

**Vérifier** : le flux quotidien tourne-t-il ? Dans Prefect, **Deployments**, `ingestion-quotidienne-7h` doit être **Ready**, avec le planning **Active** à 07:00. Les exécutions récentes doivent être **Completed**.

**Réparer**
- Conteneur arrêté : `docker compose up -d`.
- Exécution manquée : relancer les jours manquants (cas 3).

## 3. Rejouer un jour (backfill par date)

Un chargement répété ne crée pas de doublon, on peut relancer sans risque.

```powershell
docker compose exec ingestion python /app/orchestration/flows.py 2026-10-31
```
Vérifier la présence de lignes `Completed` pour les deux tâches. Autre méthode : dans Prefect, déploiement `ingestion-quotidienne-7h`, **Run**, **Custom run**, paramètre `jour`.

Pour recharger une période :
```powershell
docker compose exec ingestion python /app/ingestion/regional_backfill.py 2021-01 2026-08
docker compose exec ingestion python /app/ingestion/meteo_pipeline.py 2021-01-01 2026-08-31
```
Le régional prend 5 à 10 secondes par mois.

## 4. Une table n'existe pas, ou la base est vide

**Symptôme** : une erreur du type « Table with name eco2mix_regional does not exist ». Cause fréquente : une base neuve a été créée à la place de l'ancienne.

**Vérifier** : la taille de `data/energie.duckdb` (environ 77 Mo avec tout l'historique) et le nombre de lignes :
```powershell
dir data
python -c "import duckdb; print(duckdb.connect('data/energie.duckdb', read_only=True).sql('select count(*) from raw.eco2mix_regional'))"
```
Attendu : 1 191 576 lignes pour la période 2021-01 à 2026-08.

**Réparer**
- **Avec la sauvegarde** (copie hors du dépôt) :
```powershell
docker compose stop ingestion
Copy-Item ..\energie-sauvegarde.duckdb data\energie.duckdb -Force
docker compose start ingestion
```
- **Sans sauvegarde** : recharger l'historique avec les commandes du cas 3. C'est long mais sans risque.

**Faire une sauvegarde** (à refaire après chaque gros chargement) :
```powershell
docker compose stop ingestion
Copy-Item data/energie.duckdb ..\energie-sauvegarde.duckdb
docker compose start ingestion
```

## 5. Le conteneur ingestion redémarre en boucle

```powershell
docker compose logs ingestion --tail 30
```
- `can't open file ... serve.py` : vérifier la dernière ligne du Dockerfile, elle doit être `CMD ["python", "/app/orchestration/serve.py"]`.
- `All connection attempts failed` au démarrage : le serveur Prefect n'est pas encore prêt. Attendre une minute. Si le problème persiste, vérifier que `prefect-server` est `healthy`.

## 6. Grafana : la source « Journal » est absente ou sans données

**Vérifier que le plugin est installé** :
```powershell
docker exec energie-grafana grafana cli plugins ls
```
`frser-sqlite-datasource` doit apparaître. Sinon, vérifier que `docker-compose.yml` contient `GF_PLUGINS_PREINSTALL_SYNC` (et non l'ancienne variable `GF_INSTALL_PLUGINS`), puis :
```powershell
docker compose up -d --force-recreate grafana
```

**Vérifier que le journal contient des lignes** :
```powershell
python -c "import sqlite3; print(sqlite3.connect('monitoring/monitoring.sqlite').execute('select statut, count(*) from runs group by statut').fetchall())"
```

## 7. Nettoyer le journal après un test

Exemple : effacer les lignes d'une tentative interrompue (aucune ligne chargée) :
```powershell
python -c "import sqlite3; c = sqlite3.connect('monitoring/monitoring.sqlite'); c.execute('delete from runs where lignes_chargees is null'); c.commit()"
```
Regarder d'abord ce qu'on efface (`select ... where lignes_chargees is null`), et ne pas supprimer d'échecs réels.

## 8. Deux exécutions en même temps

DuckDB n'accepte qu'un écrivain à la fois. Ne pas déclencher deux fois le même flux (éviter le double clic sur **Quick run**). Si deux exécutions tournent, attendre la fin de la première.

## 9. Secrets

Le fichier `.env` ne doit jamais être envoyé sur GitHub. En cas de fuite de l'adresse du webhook Discord : supprimer le webhook dans Discord (Modifier le salon, Intégrations, Webhooks), en créer un nouveau, mettre à jour `.env`, puis `docker compose up -d --force-recreate ingestion`.