from datetime import datetime, timedelta, timezone
import os

from airflow.sdk import Param, dag, task


@dag(
    dag_id="openf1_sessao",
    description="Coleta e análise de telemetria por piloto e sessão",
    schedule=os.getenv("OPENF1_SCHEDULE") or None,
    start_date=datetime(2023, 9, 15, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    params={
        "session_key": Param(9158, type="integer", minimum=1),
        "usar_snapshot": Param(True, type="boolean"),
    },
    tags=["OpenF1", "telemetria"],
)
def openf1_sessao():
    @task
    def executar(params=None):
        from config.settings import load_settings
        from src.pipeline import run_pipeline

        result = run_pipeline(
            load_settings(),
            session_key=params["session_key"],
            skip_ingestion=params["usar_snapshot"],
            load_database=True,
        )
        return result["pipeline_manifest"]

    @task
    def verificar(manifest_path):
        import json
        from pathlib import Path
        from sqlalchemy import create_engine, text
        from config.settings import load_settings

        manifest = json.loads(Path(manifest_path).read_text())
        with create_engine(load_settings().postgres_url).connect() as connection:
            for name, dataset in manifest["gold"]["datasets"].items():
                count = connection.execute(
                    text(f'SELECT count(*) FROM analytics."{name}" WHERE session_key=:session'),
                    {"session": int(manifest["session_key"])},
                ).scalar_one()
                if count != dataset["rows"]:
                    raise ValueError(f"Contagem divergente em {name}")
        return "Contagens SQL conferidas com a Gold"

    verificar(executar())


openf1_sessao()
