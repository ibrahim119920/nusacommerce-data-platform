"""Day 14 capstone DAG. Logic stays in the independently testable package."""

from datetime import datetime, timedelta, timezone
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

PREFIX = "cd /opt/nusa-project && /opt/nusa-venv/bin/python -m nusacommerce.cli "

with DAG(
    dag_id="nusacommerce_batch",
    start_date=datetime(2026, 9, 28, tzinfo=timezone.utc),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(seconds=10)},
    tags=["reference", "day14"],
) as dag:
    bootstrap = BashOperator(task_id="bootstrap", bash_command=PREFIX + "bootstrap")
    orders = BashOperator(
        task_id="orders",
        bash_command=PREFIX + "orders --cutoff '{{ data_interval_end.isoformat() }}'",
    )
    payments = BashOperator(task_id="payments", bash_command=PREFIX + "payments")
    warehouse = BashOperator(task_id="warehouse", bash_command=PREFIX + "dbt")
    quality = BashOperator(task_id="quality", bash_command=PREFIX + "quality")
    lake = BashOperator(
        task_id="lake", bash_command=PREFIX + "lake-export --snapshot-id-only"
    )
    spark = BashOperator(
        task_id="spark",
        bash_command=PREFIX
        + "spark-build --snapshot-id '{{ ti.xcom_pull(task_ids=\"lake\") }}'",
    )
    monitor = BashOperator(task_id="monitor", bash_command=PREFIX + "monitor")
    bootstrap >> [orders, payments] >> warehouse >> quality
    quality >> lake >> spark >> monitor
