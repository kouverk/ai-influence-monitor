"""
Extract Senate LDA Lobbying Data

Manual/triggered DAG to fetch lobbying disclosures from Senate LDA API.
Use this for:
- Weekly refresh of lobbying data
- Initial load for new companies
- Backfilling historical data

Fetches data for priority companies, filtered by:
- Year: 2023+
- Issue codes: CPI, SCI, CPT, CSP, DEF, HOM (AI-relevant)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    'owner': 'kouverk',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

SCRIPT_PATH = '/Users/kouverbingham/development/data-expert-analytics/ai-influence-monitor'
PYTHON_PATH = f'{SCRIPT_PATH}/venv/bin/python'


def get_env_exports():
    return f"export $(grep -v '^#' {SCRIPT_PATH}/.env | grep -v '^$' | grep -v AIRFLOW | xargs)"


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
        bash_command=f"""
            cd {SCRIPT_PATH} && \
            {get_env_exports()} && \
            {PYTHON_PATH} include/scripts/extraction/extract_lda_filings.py
        """,
    )
