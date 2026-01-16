"""
Extract AI Action Plan PDF Submissions

Manual/triggered DAG to extract text from PDF submissions.
Use this for:
- Initial bulk load of all PDFs
- Reprocessing specific documents
- Adding new priority companies
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    'owner': 'kouverk',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}

AIRFLOW_HOME = os.environ.get('AIRFLOW_HOME', '/usr/local/airflow')


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
        bash_command=f'python {AIRFLOW_HOME}/include/scripts/extraction/extract_pdf_submissions.py',
    )
