FROM astrocrpublic.azurecr.io/runtime:3.3-9

# dbt lives in its own virtualenv so its dependencies can never clash with Airflow's.
# The DAG's dbt_build task calls /usr/local/airflow/dbt_venv/bin/dbt.
RUN python -m venv /usr/local/airflow/dbt_venv && \
    /usr/local/airflow/dbt_venv/bin/pip install --no-cache-dir "dbt-core~=1.12.0" "dbt-bigquery~=1.12.0"

# Install dbt packages (dbt_utils) at build time so runs don't download anything.
RUN cd /usr/local/airflow/dbt && /usr/local/airflow/dbt_venv/bin/dbt deps
