"""
Extract Senate LDA Lobbying Data

Fetches lobbying disclosures from Senate LDA API.
Filters: 2023+, AI-relevant issue codes, priority companies.
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    'owner': 'kouverk',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

AIRFLOW_HOME = os.environ.get('AIRFLOW_HOME', '/usr/local/airflow')


with DAG(
    'extract_lda_lobbying',
    default_args=default_args,
    description='Fetch lobbying data from Senate LDA API',
    schedule_interval='@weekly',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['ai-influence', 'extract', 'lda'],
) as dag:

    extract_lda = BashOperator(
        task_id='extract_lda_filings',
        bash_command=f'python {AIRFLOW_HOME}/include/scripts/extraction/extract_lda_filings.py',
    )
