"""
Snowflake Sync DAG

Syncs data from Iceberg to Snowflake and runs dbt models.
Use this after any extraction or LLM processing to update the analytics layer.

Steps:
1. Export Iceberg tables → Snowflake RAW tables (full refresh)
2. Run dbt to build staging views and mart tables
3. Run dbt tests to validate data quality

Trigger manually after running extraction DAGs, or schedule daily.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    'owner': 'kouverk',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}

SCRIPT_PATH = '/Users/kouverbingham/development/data-expert-analytics/ai-influence-monitor'
PYTHON_PATH = f'{SCRIPT_PATH}/venv/bin/python'


def get_env_exports():
    return f"export $(grep -v '^#' {SCRIPT_PATH}/.env | grep -v '^$' | grep -v AIRFLOW | xargs)"


with DAG(
    'snowflake_sync',
    default_args=default_args,
    description='Sync Iceberg to Snowflake and run dbt',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['ai-influence', 'snowflake', 'dbt'],
) as dag:

    export_to_snowflake = BashOperator(
        task_id='export_to_snowflake',
        bash_command=f"""
            cd {SCRIPT_PATH} && \
            {get_env_exports()} && \
            {PYTHON_PATH} include/scripts/utils/export_to_snowflake.py
        """,
    )

    run_dbt = BashOperator(
        task_id='run_dbt',
        bash_command=f"""
            cd {SCRIPT_PATH} && \
            {get_env_exports()} && \
            cd dbt/ai_influence && \
            {SCRIPT_PATH}/venv/bin/dbt run
        """,
    )

    test_dbt = BashOperator(
        task_id='test_dbt',
        bash_command=f"""
            cd {SCRIPT_PATH} && \
            {get_env_exports()} && \
            cd dbt/ai_influence && \
            {SCRIPT_PATH}/venv/bin/dbt test
        """,
    )

    export_to_snowflake >> run_dbt >> test_dbt
