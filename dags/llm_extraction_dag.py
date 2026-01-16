"""
LLM Position Extraction DAG

Uses Claude API to extract policy positions from document chunks.
This is the "agentic" part of the pipeline.

Trigger with:
- {"limit": 10} to process only 10 chunks
- {"fresh": true} to re-extract all positions from scratch
- {} for incremental processing

Rate limits: ~25 chunks/minute with claude-sonnet-4-20250514
Cost: ~$0.05-0.10 per chunk
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    'owner': 'kouverk',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=10),  # Longer delay for API rate limits
}

SCRIPT_PATH = '/Users/kouverbingham/development/data-expert-analytics/ai-influence-monitor'
PYTHON_PATH = f'{SCRIPT_PATH}/venv/bin/python'


def get_env_exports():
    return f"export $(grep -v '^#' {SCRIPT_PATH}/.env | grep -v '^$' | grep -v AIRFLOW | xargs)"


with DAG(
    'llm_extract_positions',
    default_args=default_args,
    description='Extract policy positions using Claude API',
    schedule_interval=None,  # Manual trigger - costs money
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['ai-influence', 'llm', 'agentic'],
) as dag:

    extract_positions = BashOperator(
        task_id='extract_positions',
        bash_command=f"""
            cd {SCRIPT_PATH} && \
            {get_env_exports()} && \
            {PYTHON_PATH} include/scripts/agentic/extract_positions.py
        """,
        execution_timeout=timedelta(hours=2),  # LLM extraction can take a while
    )
