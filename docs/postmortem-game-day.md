# Postmortem : game day du 1er novembre 2026

Document sans recherche de coupable : on décrit ce qui s'est passé, comment le système a réagi, et ce qu'on améliore.

## Résumé

Pour tester notre détection de pannes, nous avons rendu volontairement injoignable l'API eCO2mix (`odre.opendatasoft.com`) depuis le conteneur d'ingestion. Deux exécutions du flux `ingestion-quotidienne` ont échoué après leurs relances. L'alerte Discord est partie environ 6 minutes après le premier échec pour chacune, et le tableau de bord Grafana est passé au rouge (8 échecs). Après le retour à la normale, un nouveau chargement de la même journée a réussi sans créer de doublon.

## Impact

- Aucune donnée corrompue, perdue ou manquante : la journée du 31 octobre 2026 avait été chargée à 14:18, avant la panne, et les deux exécutions échouées essayaient de la recharger.
- Les deux exécutions ont échoué dès l'extraction, avant toute écriture dans l'entrepôt.
- Incident simulé : aucun utilisateur réel n'a été touché.

## Déroulement du test

| Heure (locale) | Événement |
| --- | --- |
| 14:18 | Chargement normal du 31 octobre (eCO2mix puis météo), avant la panne |
| ≈ 14:22 | Injection de la panne : le nom `odre.opendatasoft.com` est redirigé vers `127.0.0.1` pour le conteneur `ingestion` (fichier `docker-compose.panne.yml`) |
| 14:22:59 | Premier échec de l'exécution `free-mule` (eCO2mix, jour 2026-10-31) : `Connection refused` |
| 14:23:09 | Relance 1/3 de `free-mule`, 10 s après |
| 14:23:46 | Début d'une seconde exécution, `rose-leech`, lancée par un double déclenchement manuel |
| 14:24:09 | Relance 2/3 de `free-mule`, 60 s après |
| 14:29:09 | Relance 3/3 de `free-mule` : échec définitif |
| 14:29 | Alerte Discord pour `free-mule` |
| ≈ 14:30 | Échec définitif de `rose-leech` et seconde alerte Discord |
| 14:30:48 | Fin de la panne : `docker compose up -d` sans le fichier de panne |
| 14:31 | Nouveau chargement du 31 octobre avec `flows.py 2026-10-31` : les deux tâches réussissent |

Une première tentative de test, interrompue par la fermeture de Docker, avait déjà laissé 2 lignes d'échec dans le journal. Elles ont été effacées avant de recommencer, pour partir d'un état propre.

## Détection

- **Automatique.** Chaque exécution a relancé sa tâche 3 fois (délais de 10 s, 1 min et 5 min), puis a envoyé un message sur Discord.
- **Délai de détection : environ 6 minutes** après le premier échec, ce qui correspond à la somme des délais de relance.
- Le tableau de bord Grafana a affiché des échecs en rouge dès les premières tentatives.
- Les journaux Prefect donnent la cause : `Connection refused` sur l'URL de l'API eCO2mix.

## Cause

Panne simulée : l'API eCO2mix ne répondait plus pour le conteneur d'ingestion.

## Résolution

1. Retrait du fichier de panne et redémarrage : `docker compose up -d`.
2. Contrôle de la source : réponse HTTP 200.
3. Nouveau chargement de la journée du 31 octobre : `python /app/orchestration/flows.py 2026-10-31`. Il a réussi, ce qui confirme la reprise.
4. Vérification de la fraîcheur : dernière mesure eCO2mix au 31 octobre à 23:45 (heure locale), dernière heure de météo au 31 octobre à 23:00 UTC.

Le nouveau chargement n'a créé aucun doublon, car l'ingestion est idempotente (clé primaire et écriture par fusion). Vérification faite après le rattrapage : la table `eco2mix_national` contient 192 lignes pour 192 dates-heures distinctes (2 journées de 96 mesures), alors que le 31 octobre a été chargé deux fois.

## Ce qui a bien fonctionné

- Les relances ont respecté les délais prévus (10 s, 60 s, 300 s) pour les deux exécutions.
- Chaque exécution en échec a déclenché sa propre alerte (2 messages pour 2 exécutions), sans intervention humaine.
- Le journal d'exécutions a conservé toutes les tentatives avec leur heure, ce qui a permis de reconstituer la chronologie.
- La reprise après réparation a été immédiate (25 secondes entre le redémarrage et le chargement réussi), sans doublon.

## Ce qui nous a surpris

- **Deux exécutions simultanées.** Le flux a été lancé deux fois à 47 secondes d'écart (double déclenchement manuel). Les deux ont tourné en parallèle sur la même base DuckDB. Ici, elles échouaient avant d'écrire, mais DuckDB n'accepte qu'un écrivain à la fois : en fonctionnement normal, cela aurait pu bloquer un chargement.
- **L'indicateur « Échecs » compte des tentatives, pas des incidents.** Il affiche 8 pour 2 incidents (2 exécutions × 4 tentatives) et reste rouge pendant 7 jours.
- **Le message d'alerte est peu informatif** : il indique « jour : hier » au lieu de la date réelle et ne donne pas la cause de l'erreur.
- **La fraîcheur n'a pas évolué pendant les 7 minutes de la panne.** C'est normal, l'indicateur se compte en heures, mais il ne réagirait qu'à une panne de plus d'une journée.

## Actions pour éviter la répétition

| Action | Pourquoi |
| --- | --- |
| Limiter le déploiement à une seule exécution à la fois (limite de concurrence Prefect) | Éviter deux écrivains sur DuckDB |
| Enrichir le message Discord : date réelle du jour traité et début de l'erreur | Diagnostiquer sans ouvrir Prefect |
| Compter les échecs par exécution plutôt que par tentative | Un indicateur qui reflète les incidents |
| Ajouter une alerte Grafana quand la fraîcheur dépasse 36 heures | Détecter les pannes silencieuses de longue durée |
| Tester le nombre de lignes de l'entrepôt après chaque démarrage | Voir immédiatement une base vide ou recréée |
| Sauvegarder régulièrement `data/energie.duckdb` hors du dépôt | Voir l'incident ci-dessous |

## Incident réel de la veille : base recréée à vide

Pendant la mise en place de Docker Compose, la grosse base `energie.duckdb` (1,19 million de lignes) n'a pas été déplacée dans le dossier `data/`, que le conteneur utilise. Le conteneur a créé une base neuve de 3,9 Mo. Le symptôme était déroutant (« la table `eco2mix_regional` n'existe pas »). L'ancienne base n'a pas été retrouvée.

- **Résolution** : rechargement complet par les scripts de backfill (68 mois régionaux de 5 à 10 secondes chacun, météo en environ 11 secondes), sans doublon grâce à l'idempotence. Le total retrouvé est identique : 1 191 576 lignes, 12 régions.
- **Prévention** : copie de sécurité de la base hors du dépôt (77,6 Mo), et le contrôle de comptage ci-dessus.

## Comment rejouer le scénario

```powershell
docker compose -f docker-compose.yml -f docker-compose.panne.yml up -d ingestion   # casser
# lancer un Quick run dans Prefect, observer pendant environ 7 minutes
docker compose up -d                                                                # réparer
docker compose exec ingestion python /app/orchestration/flows.py 2026-10-31         # relancer le chargement
```