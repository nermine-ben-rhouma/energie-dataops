FROM python:3.12-slim
WORKDIR /dbt
RUN pip install --no-cache-dir "dbt-duckdb>=1.9,<2"
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
ENV DBT_PROFILES_DIR=/dbt
ENTRYPOINT ["dbt"]