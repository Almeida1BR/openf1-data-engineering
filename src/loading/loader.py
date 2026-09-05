import argparse
import json
from pathlib import Path
import re

import pandas as pd
from sqlalchemy import MetaData, Table, create_engine, delete, inspect, text
from sqlalchemy.dialects.postgresql import JSONB

from config.settings import load_settings
from src.utils.logger import configure_logging, get_logger


def _safe_table_name(name):
    value = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()

    if not value:
        raise ValueError("Nome de tabela vazio")

    return value


def _json_value(value):
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return None if pd.isna(value) else value


def _serialize_nested_values(df):
    result = df.copy()

    for column in result.columns:
        if result[column].dtype != "object":
            continue

        result[column] = result[column].map(
            lambda value: json.dumps(_json_value(value), ensure_ascii=False, allow_nan=False)
            if hasattr(value, "tolist") or isinstance(value, (list, dict))
            else value
        )

    return result


def _schema_for(engine, schema):
    if engine.dialect.name == "sqlite":
        return None

    return schema


def load_gold(gold_root, database_url, schema="analytics", logger=None):
    if not database_url:
        raise ValueError("database_url é obrigatório")

    log = logger or get_logger(__name__)
    gold_root = Path(gold_root)
    files = sorted(gold_root.glob("*.parquet"))

    if not files:
        raise FileNotFoundError(f"Nenhum Parquet Gold encontrado em {gold_root}")

    engine = create_engine(database_url, future=True, hide_parameters=True)
    database_schema = _schema_for(engine, schema)
    loaded = {}
    manifest_path = gold_root / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if set(manifest.get("datasets", {})) != {path.stem for path in files}:
            raise ValueError("Arquivos Gold divergem dos datasets do manifesto")

    if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
        raise ValueError("Schema inválido")

    with engine.begin() as connection:
        if database_schema is not None:
            if database_schema != "analytics":
                raise ValueError("O contrato PostgreSQL usa o schema analytics")
            connection.execute(text("SELECT pg_advisory_xact_lock(9158)"))
            ddl = Path(__file__).resolve().parents[2] / "sql/ddl/001_create_analytics.sql"
            for statement in ddl.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    connection.execute(text(statement))

        for file_path in files:
            table_name = _safe_table_name(file_path.stem)
            if database_schema is not None and not inspect(connection).has_table(table_name, schema=database_schema):
                raise ValueError(f"Tabela sem migração SQL: {table_name}")
            dataframe = _serialize_nested_values(pd.read_parquet(file_path))
            for column in dataframe.columns:
                if column in {"date_start", "date_end", "generated_at", "telemetry_start", "telemetry_end", "first_radio_at", "last_radio_at"}:
                    dataframe[column] = pd.to_datetime(dataframe[column], utc=True)
            if "session_key" not in dataframe or dataframe["session_key"].isna().any():
                raise ValueError(f"Sessão obrigatória na tabela {table_name}")
            sessions = dataframe["session_key"].unique().tolist()
            manifest_path = gold_root / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                selected = manifest.get("session_key")
                if selected is not None:
                    if any(str(value) != str(selected) for value in sessions):
                        raise ValueError("Sessões divergem do manifesto Gold")
                    sessions = [int(selected)]
            if inspect(connection).has_table(table_name, schema=database_schema):
                table = Table(table_name, MetaData(), schema=database_schema, autoload_with=connection)
                connection.execute(delete(table).where(table.c.session_key.in_(sessions)))
            json_columns = {
                name: JSONB
                for name in dataframe.columns
                if name.startswith("segments_sector_") and database_schema is not None
            }
            for name in json_columns:
                dataframe[name] = dataframe[name].map(
                    lambda value: json.loads(value) if isinstance(value, str) else value
                )
            dataframe.to_sql(
                name=table_name,
                con=connection,
                schema=database_schema,
                if_exists="append",
                dtype=json_columns,
                index=False,
                chunksize=1000,
                method="multi",
            )
            loaded[table_name] = len(dataframe)
            log.info(
                "Tabela carregada | table=%s | rows=%s | schema=%s",
                table_name,
                len(dataframe),
                database_schema or "main",
            )

    return {
        "gold_root": str(gold_root),
        "database_schema": database_schema or "main",
        "tables": loaded,
        "status": "success",
    }


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Carrega os datasets Gold em um banco relacional"
    )
    parser.add_argument("--gold-root", default=None)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--schema", default="analytics")
    return parser.parse_args(args)


def main(args=None):
    parsed = parse_args(args)
    settings = load_settings()
    configure_logging(log_path=settings.logs_root / "loading.log")
    load_gold(
        gold_root=parsed.gold_root or settings.gold_root,
        database_url=parsed.database_url or settings.postgres_url,
        schema=parsed.schema,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
