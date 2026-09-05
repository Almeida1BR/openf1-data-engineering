import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import pandas as pd

from config.settings import load_settings
from src.gold.telemetry_laps import telemetry_by_lap
from src.utils.logger import configure_logging, get_logger


DATASETS = (
    "sessions",
    "drivers",
    "laps",
    "team_radio",
    "car_data",
)


DRS_ACTIVE_VALUES = {10, 12, 14}


def _safe_value(value):
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", str(value)).strip("_")


def _dataset_path(silver_root, endpoint, session_key=None):
    silver_root = Path(silver_root)
    candidates = []

    if session_key is not None:
        candidates.append(
            silver_root
            / f"session_key={_safe_value(session_key)}"
            / endpoint
            / f"{endpoint}.parquet"
        )

    candidates.append(silver_root / endpoint / f"{endpoint}.parquet")

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        f"Silver não encontrada para {endpoint}: {', '.join(map(str, candidates))}"
    )


def _read_dataset(silver_root, endpoint, session_key=None):
    path = _dataset_path(silver_root, endpoint, session_key=session_key)
    df = pd.read_parquet(path)

    if session_key is not None and str(session_key) != "latest" and "session_key" in df:
        df = df[df["session_key"].astype("string") == str(session_key)].copy()

    return df


def _minimum(series):
    values = series.dropna()
    return values.min() if not values.empty else pd.NA


def _average(series):
    values = series.dropna()
    return values.mean() if not values.empty else pd.NA


def _driver_info(drivers):
    columns = [
        "session_key",
        "driver_number",
        "full_name",
        "name_acronym",
        "team_name",
        "team_colour",
        "first_name",
        "last_name",
    ]
    available = [column for column in columns if column in drivers.columns]
    return drivers[available].drop_duplicates(
        subset=["session_key", "driver_number"]
    )


def _lap_performance(laps, drivers):
    result = laps.copy()
    sector_columns = [
        "duration_sector_1",
        "duration_sector_2",
        "duration_sector_3",
    ]
    available_sectors = [column for column in sector_columns if column in result]
    result["sector_time_sum_s"] = result[available_sectors].sum(axis=1, min_count=3)
    result["is_complete_lap"] = result["lap_duration"].notna()

    if available_sectors:
        result["is_complete_lap"] &= result[available_sectors].notna().all(axis=1)

    valid_laps = result[
        result["is_complete_lap"] & ~result["is_pit_out_lap"].fillna(False)
    ]
    best_by_driver = valid_laps.groupby(
        ["session_key", "driver_number"], as_index=False
    )["lap_duration"].min().rename(columns={"lap_duration": "driver_best_lap_duration_s"})
    result = result.merge(best_by_driver, on=["session_key", "driver_number"], how="left")
    result["delta_to_driver_best_lap_s"] = (
        result["lap_duration"] - result["driver_best_lap_duration_s"]
    )

    info = _driver_info(drivers)
    result = result.merge(
        info,
        on=["session_key", "driver_number"],
        how="left",
        suffixes=("", "_driver"),
    )
    return result


def _lap_summary(laps):
    result = laps.copy()
    sector_columns = [
        "duration_sector_1",
        "duration_sector_2",
        "duration_sector_3",
    ]
    available_sectors = [column for column in sector_columns if column in result]
    result["is_complete_lap"] = result["lap_duration"].notna()

    if available_sectors:
        result["is_complete_lap"] &= result[available_sectors].notna().all(axis=1)

    grouped = result.groupby(["session_key", "driver_number"], as_index=False)
    summary = grouped.agg(
        lap_count=("lap_number", "count"),
        complete_lap_count=("is_complete_lap", "sum"),
        pit_out_lap_count=("is_pit_out_lap", "sum"),
    )
    valid = result[result["is_complete_lap"] & ~result["is_pit_out_lap"].fillna(False)]
    summary = summary.merge(
        valid.groupby(["session_key", "driver_number"], as_index=False).agg(
            best_lap_duration_s=("lap_duration", _minimum),
            average_lap_duration_s=("lap_duration", _average),
        ),
        on=["session_key", "driver_number"], how="left",
    )

    for column in available_sectors:
        summary = summary.merge(
            result.groupby(["session_key", "driver_number"], as_index=False).agg(
                **{f"best_{column}_s": (column, _minimum)}
            ),
            on=["session_key", "driver_number"],
            how="left",
        )

    speed_columns = [
        column
        for column in ("i1_speed", "i2_speed", "st_speed")
        if column in result
    ]

    if speed_columns:
        speed_summary = result.groupby(
            ["session_key", "driver_number"],
            as_index=False,
        ).agg(
            **{
                f"max_{column}_kmh": (column, "max")
                for column in speed_columns
            }
        )
        summary = summary.merge(
            speed_summary,
            on=["session_key", "driver_number"],
            how="left",
        )

    return summary


def _telemetry_summary(car_data):
    data = car_data.copy()
    data["drs_active"] = data["drs"].isin(DRS_ACTIVE_VALUES)
    data["brake_pressed"] = data["brake"] > 0

    summary = data.groupby(["session_key", "driver_number"], as_index=False).agg(
        telemetry_sample_count=("date", "count"),
        telemetry_start=("date", "min"),
        telemetry_end=("date", "max"),
        max_speed_kmh=("speed", "max"),
        average_speed_kmh=("speed", "mean"),
        max_rpm=("rpm", "max"),
        average_rpm=("rpm", "mean"),
        average_throttle=("throttle", "mean"),
        brake_pressed_sample_count=("brake_pressed", "sum"),
        drs_active_sample_count=("drs_active", "sum"),
        drs_active_percentage=("drs_active", "mean"),
    )
    summary["drs_active_percentage"] = summary["drs_active_percentage"] * 100
    return summary


def _radio_summary(team_radio):
    if team_radio.empty:
        return pd.DataFrame(
            columns=[
                "session_key",
                "driver_number",
                "radio_message_count",
                "first_radio_at",
                "last_radio_at",
            ]
        )

    return team_radio.groupby(
        ["session_key", "driver_number"],
        as_index=False,
    ).agg(
        radio_message_count=("recording_url", "count"),
        first_radio_at=("date", "min"),
        last_radio_at=("date", "max"),
    )


def _driver_session_performance(
    sessions,
    drivers,
    laps,
    car_data,
    team_radio,
):
    info = _driver_info(drivers)
    result = info.copy()
    result = result.merge(
        _lap_summary(laps),
        on=["session_key", "driver_number"],
        how="left",
    )
    result = result.merge(
        _telemetry_summary(car_data),
        on=["session_key", "driver_number"],
        how="left",
    )
    result = result.merge(
        _radio_summary(team_radio),
        on=["session_key", "driver_number"],
        how="left",
    )

    session_columns = [
        "session_key",
        "meeting_key",
        "session_type",
        "session_name",
        "circuit_short_name",
        "country_name",
        "year",
        "date_start",
        "date_end",
    ]
    available = [column for column in session_columns if column in sessions.columns]
    session_context = sessions[available].drop_duplicates(subset=["session_key"])
    result = result.merge(session_context, on="session_key", how="left")

    count_columns = [
        "lap_count",
        "complete_lap_count",
        "pit_out_lap_count",
        "telemetry_sample_count",
        "brake_pressed_sample_count",
        "drs_active_sample_count",
        "radio_message_count",
    ]
    for column in count_columns:
        if column in result:
            result[column] = result[column].fillna(0).astype("int64")

    return result.sort_values("driver_number").reset_index(drop=True)


def _session_summary(sessions, drivers, laps, car_data, team_radio):
    result = sessions.copy().drop_duplicates(subset=["session_key"])
    result["driver_count"] = drivers["driver_number"].nunique()
    result["lap_record_count"] = len(laps)
    result["car_data_record_count"] = len(car_data)
    result["team_radio_record_count"] = len(team_radio)
    result["telemetry_driver_count"] = car_data["driver_number"].nunique()
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    return result.reset_index(drop=True)


def _drs_state_summary(car_data, drivers):
    result = car_data.groupby(
        ["session_key", "driver_number", "drs"],
        as_index=False,
    ).size()
    result = result.rename(columns={"size": "sample_count"})
    return result.merge(
        _driver_info(drivers),
        on=["session_key", "driver_number"],
        how="left",
    ).sort_values(["driver_number", "drs"])


def _write_manifest(manifest, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )


def build_gold(silver_root, gold_root, session_key=None, logger=None):
    log = logger or get_logger(__name__)
    datasets = {
        endpoint: _read_dataset(
            silver_root,
            endpoint,
            session_key=session_key,
        )
        for endpoint in DATASETS
    }

    if datasets["sessions"].empty:
        raise ValueError("Nenhuma sessão disponível para a camada Gold")

    output_root = Path(gold_root)

    if session_key is not None:
        output_root = output_root / f"session_key={_safe_value(session_key)}"

    output_root.mkdir(parents=True, exist_ok=True)
    outputs = {
        "telemetry_lap_summary": telemetry_by_lap(datasets["car_data"], datasets["laps"]),
        "session_summary": _session_summary(**datasets),
        "driver_session_performance": _driver_session_performance(**datasets),
        "lap_performance": _lap_performance(
            datasets["laps"],
            datasets["drivers"],
        ),
        "telemetry_summary": _telemetry_summary(datasets["car_data"]),
        "radio_summary": _radio_summary(datasets["team_radio"]),
        "drs_state_summary": _drs_state_summary(
            datasets["car_data"],
            datasets["drivers"],
        ),
    }
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_key": None if session_key is None else str(session_key),
        "silver_root": str(silver_root),
        "gold_root": str(output_root),
        "datasets": {},
        "status": "success",
    }

    for name, dataframe in outputs.items():
        path = output_root / f"{name}.parquet"
        dataframe.to_parquet(path, engine="pyarrow", index=False)
        manifest["datasets"][name] = {
            "path": str(path),
            "rows": len(dataframe),
            "columns": list(dataframe.columns),
        }
        log.info("Gold gravada | dataset=%s | rows=%s | path=%s", name, len(dataframe), path)

    manifest_path = output_root / "manifest.json"
    _write_manifest(manifest, manifest_path)
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Construção da camada Gold da OpenF1"
    )
    parser.add_argument("--silver-root", default=None)
    parser.add_argument("--gold-root", default=None)
    parser.add_argument("--session-key", default=None)
    return parser.parse_args(args)


def main(args=None):
    parsed = parse_args(args)
    settings = load_settings()
    configure_logging(log_path=settings.logs_root / "gold.log")
    build_gold(
        silver_root=parsed.silver_root or settings.silver_root,
        gold_root=parsed.gold_root or settings.gold_root,
        session_key=parsed.session_key or settings.session_key,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
