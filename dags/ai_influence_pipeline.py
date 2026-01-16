"""
AI Influence Tracker - Main Pipeline DAG

This DAG orchestrates the full data pipeline:
1. Extract PDF submissions → Iceberg
2. Extract LDA lobbying data → Iceberg
3. Run LLM position extraction
4. Assess lobbying impact
5. Sync to Snowflake + run dbt

For initial load, trigger with {"mode": "full"}
For incremental updates, run on schedule (daily)
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup


default_args = {
    'owner': 'kouverk',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Astronomer path (project root is /usr/local/airflow)
AIRFLOW_HOME = os.environ.get('AIRFLOW_HOME', '/usr/local/airflow')


with DAG(
    'ai_influence_pipeline',
    default_args=default_args,
    description='AI Influence Tracker - Full data pipeline',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['ai-influence', 'main'],
) as dag:

    # =========================================================================
    # EXTRACT LAYER
    # =========================================================================

    with TaskGroup('extract') as extract_group:

        extract_pdfs = BashOperator(
            task_id='extract_pdf_submissions',
            bash_command=f'python {AIRFLOW_HOME}/include/scripts/extraction/extract_pdf_submissions.py',
            doc="""
            Extract text from AI Action Plan PDF submissions.
            Writes to Iceberg: ai_submissions_metadata, ai_submissions_text, ai_submissions_chunks
            Idempotent - skips already processed documents.
            """,
        )

        extract_lda = BashOperator(
            task_id='extract_lda_filings',
            bash_command=f'python {AIRFLOW_HOME}/include/scripts/extraction/extract_lda_filings.py',
            doc="""
            Fetch lobbying disclosures from Senate LDA API.
            Writes to Iceberg: lda_filings, lda_activities, lda_lobbyists
            Filters: 2023+, AI-relevant issue codes, priority companies.
            """,
        )

        # PDFs and LDA can run in parallel
        [extract_pdfs, extract_lda]

    # =========================================================================
    # LLM EXTRACTION LAYER (Agentic)
    # =========================================================================

    with TaskGroup('llm_extraction') as llm_group:

        extract_positions = BashOperator(
            task_id='extract_positions',
            bash_command=f'python {AIRFLOW_HOME}/include/scripts/agentic/extract_positions.py',
            doc="""
            Use Claude API to extract policy positions from document chunks.
            Writes to Iceberg: ai_positions
            Idempotent - tracks processed chunk_ids.
            """,
        )

        assess_impact = BashOperator(
            task_id='assess_lobbying_impact',
            bash_command=f'python {AIRFLOW_HOME}/include/scripts/agentic/assess_lobbying_impact.py',
            doc="""
            Use Claude API to assess public interest implications of lobbying.
            Joins positions + LDA data, produces concern scores.
            Writes to Iceberg: lobbying_impact_scores
            """,
        )

        # Positions must be extracted before impact assessment
        extract_positions >> assess_impact

    # =========================================================================
    # LOAD TO SNOWFLAKE + dbt
    # =========================================================================

    with TaskGroup('snowflake_sync') as snowflake_group:

        export_to_snowflake = BashOperator(
            task_id='export_to_snowflake',
            bash_command=f'python {AIRFLOW_HOME}/include/scripts/utils/export_to_snowflake.py',
            doc="""
            Export Iceberg tables to Snowflake RAW tables.
            Full refresh (truncate + reload) for each table.
            """,
        )

        run_dbt = BashOperator(
            task_id='run_dbt',
            bash_command=f'cd {AIRFLOW_HOME}/dbt/ai_influence && dbt run',
            doc="""
            Run dbt models to build staging views and mart tables.
            """,
        )

        test_dbt = BashOperator(
            task_id='test_dbt',
            bash_command=f'cd {AIRFLOW_HOME}/dbt/ai_influence && dbt test',
            doc="""
            Run dbt tests to validate data quality.
            """,
        )

        export_to_snowflake >> run_dbt >> test_dbt

    # =========================================================================
    # PIPELINE FLOW
    # =========================================================================

    # Full pipeline: Extract → LLM → Snowflake
    extract_group >> llm_group >> snowflake_group
