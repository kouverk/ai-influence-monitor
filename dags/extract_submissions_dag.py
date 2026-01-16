"""
Extract AI Action Plan PDF Submissions

Manual/triggered DAG to extract text from PDF submissions.
Use this for:
- Initial bulk load of all PDFs
- Reprocessing specific documents
- Adding new priority companies

Trigger with:
- {"limit": 10} to process only 10 documents
- {} for full processing
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
    'extract_submissions',
    default_args=default_args,
    description='Extract text from AI Action Plan PDF submissions',
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['ai-influence', 'extract'],
) as dag:

    extract_pdfs = BashOperator(
        task_id='extract_pdf_submissions',
        bash_command=f"""
            cd {SCRIPT_PATH} && \
            {get_env_exports()} && \
            {PYTHON_PATH} include/scripts/extraction/extract_pdf_submissions.py
        """,
    )
