# Schéma d'architecture

Tout tourne dans Docker Compose (`docker compose up -d`).

```mermaid
flowchart LR
  S["Sources : eCO2mix, Open-Meteo"] --> D["dlt, ingestion idempotente"]
  D --> W[("DuckDB, couche raw")]
  W --> B["dbt : staging, intermediate, marts (à venir)"]
  P["Prefect : relances, exécution à 07:00 UTC"] -->|orchestre| D
  P -->|écrit| J[("Journal SQLite")]
  J -->|lu par| G["Grafana : 4 indicateurs"]
  P -->|en cas d'échec| X["Discord"]
  M["MinIO : déployé, usage au niveau 2"]
```

## Lecture

- Rangée des données : les sources sont chargées par dlt dans DuckDB (couche `raw`), puis transformées par dbt.
- Rangée du pilotage : Prefect exécute l'ingestion chaque jour, alerte sur Discord en cas d'échec définitif, et alimente le journal SQLite que Grafana affiche.
- Le journal est séparé de l'entrepôt car DuckDB n'accepte qu'un écrivain à la fois (voir `decisions-architecture.md`).
- MinIO est déployé comme l'exige le socle ; les données n'y sont pas encore stockées.