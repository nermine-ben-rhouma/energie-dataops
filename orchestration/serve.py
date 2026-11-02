from flows import ingestion_quotidienne

if __name__ == "__main__":
    # Tous les jours à 07:00 (heure UTC)
    ingestion_quotidienne.serve(
        name="ingestion-quotidienne-7h",
        cron="0 7 * * *",
    )