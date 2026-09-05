import argparse
from dataclasses import replace
import json
from pathlib import Path

from config.settings import load_settings
from src.gold.build import build_gold
from src.ingestion.ingestion_openf1 import OpenF1Ingestion
from src.loading.loader import load_gold
from src.transformation.transform import ENDPOINT_ORDER, discover_endpoint_paths, run_transformation
from src.utils.logger import configure_logging, get_logger
from src.utils.audit import audited


@audited
def run_pipeline(
    settings,
    session_key=None,
    skip_ingestion=False,
    bronze_root=None,
    silver_root=None,
    gold_root=None,
    database_url=None,
    load_database=False,
):
    logger = get_logger(__name__)
    effective_settings = settings

    if session_key is not None:
        effective_settings = replace(
            effective_settings,
            session_key=str(session_key),
        )

    selected_session = effective_settings.session_key
    if not str(selected_session).isdigit() or int(selected_session) <= 0:
        raise ValueError("Informe uma session_key numérica positiva para uma execução reproduzível")
    selected_silver = Path(silver_root or effective_settings.silver_root)
    selected_gold = Path(gold_root or effective_settings.gold_root)

    if skip_ingestion:
        selected_bronze = Path(bronze_root or effective_settings.bronze_root)
        ingestion_manifest = None
    else:
        ingestion = OpenF1Ingestion(
            settings=effective_settings,
            output_root=bronze_root or effective_settings.bronze_root,
            logger=logger,
        )
        selected_bronze, ingestion_manifest = ingestion.run()

    paths = discover_endpoint_paths(selected_bronze, session_key=selected_session)
    missing = set(ENDPOINT_ORDER) - {path.name for path in paths}
    if missing:
        raise ValueError(f"Bronze incompleta para o pipeline: {sorted(missing)}")
    transformation_manifest = run_transformation(
        bronze_root=selected_bronze,
        silver_root=selected_silver,
        session_key=selected_session,
        partitioned=True,
        logger=logger,
    )
    gold_manifest = build_gold(
        silver_root=selected_silver,
        gold_root=selected_gold,
        session_key=selected_session,
        logger=logger,
    )
    load_manifest = None

    if load_database:
        target_database = database_url or effective_settings.postgres_url

        if not target_database:
            raise ValueError(
                "POSTGRES_URL ou --database-url é obrigatório para carregar o banco"
            )

        load_manifest = load_gold(
            gold_root=Path(gold_manifest["gold_root"]),
            database_url=target_database,
            logger=logger,
        )

    result = {
        "session_key": selected_session,
        "bronze_root": str(selected_bronze),
        "silver_root": str(selected_silver),
        "gold_root": str(selected_gold),
        "ingestion": ingestion_manifest,
        "transformation": transformation_manifest,
        "gold": gold_manifest,
        "load": load_manifest,
    }
    result_path = Path(gold_manifest["gold_root"]) / "pipeline_manifest.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    result["pipeline_manifest"] = str(result_path)
    return result


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Executa o pipeline OpenF1 da Bronze até a Gold"
    )
    parser.add_argument("--session-key", default=None)
    parser.add_argument("--bronze-root", default=None)
    parser.add_argument("--silver-root", default=None)
    parser.add_argument("--gold-root", default=None)
    parser.add_argument("--skip-ingestion", action="store_true")
    parser.add_argument("--load-database", action="store_true")
    parser.add_argument("--database-url", default=None)
    return parser.parse_args(args)


def main(args=None):
    parsed = parse_args(args)
    settings = load_settings()
    configure_logging(log_path=settings.logs_root / "pipeline.log")
    run_pipeline(
        settings=settings,
        session_key=parsed.session_key,
        skip_ingestion=parsed.skip_ingestion,
        bronze_root=parsed.bronze_root,
        silver_root=parsed.silver_root,
        gold_root=parsed.gold_root,
        database_url=parsed.database_url,
        load_database=parsed.load_database,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
