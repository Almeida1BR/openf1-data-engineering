from datetime import datetime, timezone

import pandas as pd


COMMON_COLUMNS = {
    "meeting_key",
    "session_key",
}


ENDPOINT_SCHEMAS = {
    "sessions": {
        "required": {
            "session_key",
            "session_type",
            "session_name",
            "date_start",
            "date_end",
            "meeting_key",
            "circuit_key",
            "circuit_short_name",
            "country_key",
            "country_code",
            "country_name",
            "location",
            "gmt_offset",
            "year",
            "is_cancelled",
        },
        "optional": set(),
    },
    "drivers": {
        "required": {
            "meeting_key",
            "session_key",
            "driver_number",
            "full_name",
            "name_acronym",
            "team_name",
            "last_name",
        },
        "optional": {
            "broadcast_name",
            "team_colour",
            "first_name",
            "headshot_url",
            "country_code",
        },
    },
    "laps": {
        "required": {
            "meeting_key",
            "session_key",
            "driver_number",
            "lap_number",
            "date_start",
            "lap_duration",
            "is_pit_out_lap",
        },
        "optional": {
            "duration_sector_1",
            "duration_sector_2",
            "duration_sector_3",
            "i1_speed",
            "i2_speed",
            "segments_sector_1",
            "segments_sector_2",
            "segments_sector_3",
            "st_speed",
        },
    },
    "team_radio": {
        "required": {
            "meeting_key",
            "session_key",
            "driver_number",
            "recording_url",
        },
        "optional": {
            "date",
        },
    },
    "car_data": {
        "required": {
            "date",
            "meeting_key",
            "session_key",
            "driver_number",
            "speed",
            "n_gear",
            "drs",
            "throttle",
            "brake",
            "rpm",
        },
        "optional": set(),
    },
}


NATURAL_KEYS = {
    "sessions": ["session_key"],
    "drivers": ["session_key", "driver_number"],
    "laps": ["session_key", "driver_number", "lap_number"],
    "team_radio": ["session_key", "driver_number", "recording_url"],
    "car_data": ["session_key", "driver_number", "date"],
}


class DataQualityError(ValueError):
    pass


def _integer(value):
    return int(value)


def _datetime_now():
    return datetime.now(timezone.utc).isoformat()


def _add_error(report, message):
    report["errors"].append(message)


def _add_warning(report, message):
    report["warnings"].append(message)


def _validate_required_columns(df, endpoint, report):
    schema = ENDPOINT_SCHEMAS[endpoint]
    missing = sorted(schema["required"] - set(df.columns))
    unexpected = sorted(
        set(df.columns)
        - schema["required"]
        - schema["optional"]
        - {"source_file", "source_path", "ingestion_run_id"}
    )
    report["missing_columns"] = missing
    report["unexpected_columns"] = unexpected

    if missing:
        _add_error(report, f"Colunas obrigatórias ausentes: {missing}")

    if unexpected:
        _add_warning(report, f"Colunas não documentadas encontradas: {unexpected}")


def _validate_null_keys(df, endpoint, report):
    keys = NATURAL_KEYS[endpoint]
    report["natural_key"] = keys

    available = [column for column in keys if column in df.columns]

    if len(available) != len(keys):
        report["duplicate_key_rows"] = 0
        return

    null_rows = int(df[available].isna().any(axis=1).sum())
    report["null_key_rows"] = null_rows

    if null_rows:
        _add_error(
            report,
            f"Linhas com chave nula para {keys}: {null_rows}",
        )

    duplicate_rows = int(df.duplicated(available, keep=False).sum())
    report["duplicate_key_rows"] = duplicate_rows

    if duplicate_rows:
        _add_error(
            report,
            f"Linhas duplicadas pela chave {keys}: {duplicate_rows}",
        )


def _validate_session_scope(df, session_key, report):
    if session_key is None or session_key == "latest" or "session_key" not in df:
        return

    expected = str(session_key)
    values = df["session_key"].dropna().astype(str)
    mismatch_rows = int((values != expected).sum())
    report["session_key"] = expected
    report["session_key_mismatch_rows"] = mismatch_rows

    if mismatch_rows:
        _add_error(
            report,
            f"Linhas fora da sessão {expected}: {mismatch_rows}",
        )


def _validate_domain(df, endpoint, report):
    if endpoint == "sessions" and {"date_start", "date_end"}.issubset(df.columns):
        invalid_dates = int((df["date_end"] < df["date_start"]).fillna(False).sum())

        if invalid_dates:
            _add_error(
                report,
                f"Sessões com date_end anterior a date_start: {invalid_dates}",
            )

    if endpoint == "car_data":
        if "speed" in df:
            invalid_speed = int((df["speed"] < 0).fillna(False).sum())

            if invalid_speed:
                _add_error(report, f"Velocidades negativas: {invalid_speed}")

        if "rpm" in df:
            invalid_rpm = int((df["rpm"] < 0).fillna(False).sum())

            if invalid_rpm:
                _add_error(report, f"RPM negativo: {invalid_rpm}")

        if "n_gear" in df:
            invalid_gear = int((~df["n_gear"].isin(range(0, 9))).fillna(False).sum())

            if invalid_gear:
                _add_error(report, f"Marchas fora de 0 a 8: {invalid_gear}")

        if "throttle" in df:
            above_percentage = int((df["throttle"] > 100).fillna(False).sum())

            if above_percentage:
                _add_warning(
                    report,
                    f"Acelerador acima de 100 observado: {above_percentage}; "
                    "preservado conforme a origem",
                )

        if "brake" in df:
            unknown_brake = int((~df["brake"].isin({0, 100, 104})).fillna(False).sum())

            if unknown_brake:
                _add_warning(
                    report,
                    f"Códigos de freio fora do conjunto documentado: {unknown_brake}",
                )

    if endpoint == "laps" and "lap_number" in df:
        invalid_laps = int((df["lap_number"] <= 0).fillna(False).sum())

        if invalid_laps:
            _add_error(report, f"Números de volta inválidos: {invalid_laps}")

    for column in ("lap_duration", "duration_sector_1", "duration_sector_2", "duration_sector_3"):
        if column in df:
            invalid_duration = int((df[column] <= 0).fillna(False).sum())

            if invalid_duration:
                _add_warning(
                    report,
                    f"Durações não positivas em {column}: {invalid_duration}",
                )


def validate_dataframe(df, endpoint, session_key=None):
    if endpoint not in ENDPOINT_SCHEMAS:
        raise ValueError(f"Endpoint sem schema: {endpoint}")

    report = {
        "generated_at": _datetime_now(),
        "endpoint": endpoint,
        "rows": _integer(len(df)),
        "columns": [str(column) for column in df.columns],
        "missing_columns": [],
        "unexpected_columns": [],
        "natural_key": [],
        "null_key_rows": 0,
        "duplicate_key_rows": 0,
        "session_key": None if session_key is None else str(session_key),
        "session_key_mismatch_rows": 0,
        "null_counts": {
            str(column): _integer(value)
            for column, value in df.isna().sum().items()
            if value
        },
        "errors": [],
        "warnings": [],
    }

    _validate_required_columns(df, endpoint, report)
    _validate_null_keys(df, endpoint, report)
    _validate_session_scope(df, session_key, report)
    _validate_domain(df, endpoint, report)

    if report["errors"]:
        report["status"] = "failed"
    elif report["warnings"]:
        report["status"] = "warning"
    else:
        report["status"] = "success"

    return report


def assert_quality(report):
    if report["status"] == "failed":
        raise DataQualityError(
            f"Qualidade reprovada para {report['endpoint']}: "
            f"{'; '.join(report['errors'])}"
        )

    return report
