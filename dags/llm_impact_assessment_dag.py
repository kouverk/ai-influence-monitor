"""
LLM Lobbying Impact Assessment DAG

Uses Claude API to assess public interest implications of corporate lobbying.
Compares policy positions to lobbying activity and generates concern scores.

This is the key analysis that produces the "hypocrite detector" scores.

Trigger with:
- {"limit": 1} to process only 1 company
- {"dry_run": true} to preview matches without API calls
- {} for full processing

Depends on:
- ai_positions table (from llm_extract_positions DAG)
- lda_filings/activities tables (from extract_lda_lobbying DAG)
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    'owner': 'kouverk',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=10),
}

AIRFLOW_HOME = os.environ.get('AIRFLOW_HOME', '/usr/local/airflow')


with DAG(
    'llm_assess_impact',
    default_args=default_args,
    description='Assess lobbying impact using Claude API',
    schedule_interval=None,  # Manual trigger - costs money
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['ai-influence', 'llm', 'agentic'],
) as dag:

    assess_impact = BashOperator(
        task_id='assess_lobbying_impact',
        bash_command=f'python {AIRFLOW_HOME}/include/scripts/agentic/assess_lobbying_impact.py',
        execution_timeout=timedelta(hours=1),
    )
