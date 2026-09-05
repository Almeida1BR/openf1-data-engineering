import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import re

import pandas as pd

from config.settings import load_settings
from src.quality.quality import (
    ENDPOINT_SCHEMAS,
    NATURAL_KEYS,
    assert_quality,
    validate_dataframe,
)
from src.utils.logger import configure_logging, get_logger


ENDPOINT_ORDER = (
    "sessions",
    "drivers",
    "laps",
    "team_radio",
    "car_data",
)


DATETIME_COLUMNS = {
    "date",
    "date_start",
    "date_end",
}


NUMERIC_COLUMNS = {
    "meeting_key",
    "session_key",
    "driver_number",
    "speed",
    "rpm",
    "n_gear",
    "throttle",
    "brake",
    "drs",
    "lap_number",
    "lap_duration",
    "duration_sector_1",
    "duration_sector_2",
    "duration_sector_3",
    "i1_speed",
    "i2_speed",
    "st_speed",
    "year",
}


def _safe_value(value):
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", str(value)).strip("_")


def _records(data):
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = [data]
    else:
        raise ValueError(f"JSON com tipo inválido: {type(data).__name__}")

    if not all(isinstance(record, dict) for record in records):
        raise ValueError("JSON contém registros que não são objetos")

    return records


def _relative_path(file_path, bronze_root):
    if bronze_root is None:
        return file_path.name

    try:
        return str(file_path.resolve().relative_to(Path(bronze_root).resolve()))
    except ValueError:
        return file_path.name


def _run_id_from_path(file_path):
    for part in file_path.parts:
        if part.startswith("run_id="):
            return part.split("=", 1)[1]

    return "legacy"


def read_json_file(file_path, session_key=None, bronze_root=None):
    with Path(file_path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    records = _records(data)

    if session_key is not None and str(session_key) != "latest":
        expected = str(session_key)
        records = [
            record
            for record in records
            if str(record.get("session_key")) == expected
        ]

    if not records:
        return pd.DataFrame()

    df = pd.json_normalize(records)
    df["source_file"] = Path(file_path).name
    df["source_path"] = _relative_path(file_path, bronze_root)
    df["ingestion_run_id"] = _run_id_from_path(Path(file_path))
    return df


def read_endpoint(endpoint_path, session_key=None, bronze_root=None, logger=None):
    endpoint_path = Path(endpoint_path)
    log = logger or get_logger(__name__)
    dataframes = []
    json_files = sorted(endpoint_path.glob("**/*.json"))

    for file_path in json_files:
        log.info(
            "Lendo Bronze | endpoint=%s | arquivo=%s",
            endpoint_path.name,
            file_path,
        )
        df = read_json_file(
            file_path,
            session_key=session_key,
            bronze_root=bronze_root or endpoint_path.parent,
        )

        if not df.empty:
            dataframes.append(df)

    if not dataframes:
        return pd.DataFrame()

    return pd.concat(dataframes, ignore_index=True, sort=False)


def normalize_columns(df):
    normalized = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9_]+", "_", regex=True)
        .str.replace(r"_+", "_", regex=True)
        .str.strip("_")
    )

    if normalized.duplicated().any():
        duplicated = sorted(set(normalized[normalized.duplicated()].tolist()))
        raise ValueError(f"Colunas duplicadas após normalização: {duplicated}")

    df = df.copy()
    df.columns = normalized
    return df


def clean_strings(df):
    df = df.copy()
    string_columns = df.select_dtypes(include=["object", "string"]).columns

    for column in string_columns:
        df[column] = df[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )
        df[column] = df[column].map(
            lambda value: pd.NA
            if isinstance(value, str) and value.casefold() in {"", "none", "null"}
            else value
        )

    return df


def convert_datetime_columns(df):
    df = df.copy()

    for column in sorted(DATETIME_COLUMNS):
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce", utc=True)

    return df


def convert_numeric_columns(df):
    df = df.copy()

    for column in sorted(NUMERIC_COLUMNS):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


def remove_duplicates(df, endpoint):
    keys = NATURAL_KEYS[endpoint]
    available = [column for column in keys if column in df.columns]

    if len(available) == len(keys):
        return df.drop_duplicates(subset=available, keep="last")

    scalar_columns = []

    for column in df.columns:
        if column in {"source_file", "source_path", "ingestion_run_id"}:
            continue

        values = df[column].dropna()
        has_nested = values.map(lambda value: isinstance(value, (list, dict))).any()

        if not has_nested:
            scalar_columns.append(column)

    if scalar_columns:
        return df.drop_duplicates(subset=scalar_columns, keep="last")

    return df


def _empty_dataframe(endpoint):
    schema = ENDPOINT_SCHEMAS[endpoint]
    columns = sorted(schema["required"] | schema["optional"])
    columns.extend(["source_file", "source_path", "ingestion_run_id"])
    return pd.DataFrame(columns=columns)


def transform_dataframe(df, endpoint, session_key=None):
    if df.empty and not len(df.columns):
        df = _empty_dataframe(endpoint)

    df = normalize_columns(df)
    df = clean_strings(df)
    df = convert_datetime_columns(df)
    df = convert_numeric_columns(df)

    if session_key is not None and str(session_key) != "latest" and "session_key" in df:
        expected = str(session_key)
        df = df[df["session_key"].astype("string") == expected].copy()

    before_count = len(df)
    before_report = validate_dataframe(
        df,
        endpoint,
        session_key=session_key,
    )
    df = remove_duplicates(df, endpoint)
    df = df.reset_index(drop=True)
    report = validate_dataframe(df, endpoint, session_key=session_key)
    report["deduplicated_rows"] = max(0, before_count - len(df))

    if report["deduplicated_rows"]:
        report["warnings"].append(
            f"Linhas removidas por chave natural: {report['deduplicated_rows']}"
        )

    if before_report["errors"] and not report["errors"]:
        report["warnings"].extend(
            error
            for error in before_report["errors"]
            if "duplicadas pela chave" in error
        )

    if report["errors"]:
        report["status"] = "failed"
    elif report["warnings"]:
        report["status"] = "warning"
    else:
        report["status"] = "success"

    assert_quality(report)
    return df, report


def save_silver(endpoint, df, silver_root, session_key=None, partitioned=False):
    silver_root = Path(silver_root)

    if partitioned and session_key is not None:
        endpoint_path = silver_root / f"session_key={_safe_value(session_key)}" / endpoint
    else:
        endpoint_path = silver_root / endpoint

    endpoint_path.mkdir(parents=True, exist_ok=True)
    file_path = endpoint_path / f"{endpoint}.parquet"
    df.to_parquet(file_path, engine="pyarrow", index=False)
    return file_path


def transform_endpoint(
    endpoint_path,
    silver_root,
    bronze_root=None,
    session_key=None,
    partitioned=False,
    logger=None,
):
    endpoint = Path(endpoint_path).name
    log = logger or get_logger(__name__)
    df = read_endpoint(
        endpoint_path,
        session_key=session_key,
        bronze_root=bronze_root,
        logger=log,
    )
    original_rows = len(df)
    df, report = transform_dataframe(
        df,
        endpoint,
        session_key=session_key,
    )
    report["input_rows"] = original_rows
    report["output_rows"] = len(df)
    output_path = save_silver(
        endpoint,
        df,
        silver_root=silver_root,
        session_key=session_key,
        partitioned=partitioned,
    )
    report["output_path"] = str(output_path)
    log.info(
        "Silver concluída | endpoint=%s | entrada=%s | saída=%s | status=%s",
        endpoint,
        original_rows,
        len(df),
        report["status"],
    )
    return report


def discover_endpoint_paths(bronze_root, session_key=None):
    bronze_root = Path(bronze_root)

    if not bronze_root.exists():
        raise FileNotFoundError(f"Bronze não encontrada: {bronze_root}")

    run_paths = sorted(bronze_root.glob("run_id=*"), reverse=True)

    for run_path in run_paths:
        manifest_path = run_path / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") != "success":
                continue
            if session_key is not None and str(manifest.get("session_key")) != str(session_key):
                continue
        paths = [
            run_path / endpoint
            for endpoint in ENDPOINT_ORDER
            if (run_path / endpoint).is_dir()
        ]

        if paths:
            return paths

    paths = [
        bronze_root / endpoint
        for endpoint in ENDPOINT_ORDER
        if (bronze_root / endpoint).is_dir()
    ]

    if not paths:
        raise FileNotFoundError(f"Nenhum endpoint encontrado em {bronze_root}")

    return paths


def _write_report(report, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )


def run_transformation(
    bronze_root,
    silver_root,
    session_key=None,
    partitioned=False,
    logger=None,
):
    log = logger or get_logger(__name__)
    bronze_root = Path(bronze_root)
    silver_root = Path(silver_root)
    reports = []

    for endpoint_path in discover_endpoint_paths(bronze_root, session_key=session_key):
        reports.append(
            transform_endpoint(
                endpoint_path=endpoint_path,
                silver_root=silver_root,
                bronze_root=bronze_root,
                session_key=session_key,
                partitioned=partitioned,
                logger=log,
            )
        )

    report_root = silver_root

    if partitioned and session_key is not None:
        report_root = silver_root / f"session_key={_safe_value(session_key)}"

    report_path = report_root / "quality_report.json"
    if any(item["status"] == "failed" for item in reports):
        overall_status = "failed"
    elif any(item["status"] == "warning" for item in reports):
        overall_status = "warning"
    else:
        overall_status = "success"

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bronze_root": str(bronze_root),
        "silver_root": str(silver_root),
        "session_key": None if session_key is None else str(session_key),
        "datasets": reports,
        "status": overall_status,
    }
    _write_report(result, report_path)
    result["quality_report"] = str(report_path)
    log.info(
        "Transformação concluída | datasets=%s | report=%s",
        len(reports),
        report_path,
    )
    return result


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Transformação das camadas Bronze e Silver da OpenF1"
    )
    parser.add_argument("--bronze-root", default=None)
    parser.add_argument("--silver-root", default=None)
    parser.add_argument("--session-key", default=None)
    parser.add_argument("--partitioned", action="store_true")
    return parser.parse_args(args)


def main(args=None):
    parsed = parse_args(args)
    settings = load_settings()
    configure_logging(log_path=settings.logs_root / "transformation.log")
    run_transformation(
        bronze_root=parsed.bronze_root or settings.bronze_root,
        silver_root=parsed.silver_root or settings.silver_root,
        session_key=parsed.session_key,
        partitioned=parsed.partitioned,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
