import json
import argparse
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import re
import uuid

from config.settings import load_settings
from src.ingestion.openf1_client import OpenF1Client
from src.utils.logger import configure_logging, get_logger


ENDPOINTS = (
    "sessions",
    "drivers",
    "laps",
    "team_radio",
    "car_data",
)


def _records(payload, endpoint):
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = [payload]
    else:
        raise ValueError(
            f"Resposta inválida para {endpoint}: "
            f"tipo {type(payload).__name__}"
        )

    if not all(isinstance(record, dict) for record in records):
        raise ValueError(f"Resposta inválida para {endpoint}: registro não é objeto")

    return records


def _safe_value(value):
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", str(value)).strip("_")


def _write_json(file_path, payload):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = file_path.with_name(
        f".{file_path.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
        temporary_path.replace(file_path)
    finally:
        temporary_path.unlink(missing_ok=True)


class OpenF1Ingestion:
    def __init__(self, settings, client=None, logger=None, output_root=None):
        self.settings = settings
        self.client = client or OpenF1Client(
            base_url=settings.base_url,
            timeout=settings.request_timeout,
            max_retries=settings.max_retries,
            min_request_interval=settings.min_request_interval,
        )
        self.logger = logger or get_logger(__name__)
        self.output_root = Path(output_root or settings.bronze_root)

    def _session_params(self):
        return {"session_key": self.settings.session_key}

    def _validate_session(self, records, endpoint):
        expected = str(self.settings.session_key)
        if any(record.get("session_key") is None for record in records):
            raise ValueError(f"Endpoint {endpoint} retornou chave de sessão nula")

        if expected == "latest":
            return

        observed = {
            str(record["session_key"])
            for record in records
            if record.get("session_key") is not None
        }

        if observed and observed != {expected}:
            raise ValueError(
                f"Endpoint {endpoint} retornou sessões inesperadas: "
                f"{sorted(observed)}; esperado {expected}"
            )

    def _run_path(self):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{timestamp}_{uuid.uuid4().hex[:8]}"
        return run_id, self.output_root / f"run_id={run_id}"

    def _write_endpoint(self, run_path, endpoint, records):
        file_path = run_path / endpoint / f"{endpoint}.json"
        _write_json(file_path, records)
        return len(records)

    def run(self, endpoints=None):
        requested = tuple(endpoints or ENDPOINTS)
        unknown = sorted(set(requested) - set(ENDPOINTS))

        if unknown:
            raise ValueError(f"Endpoints desconhecidos: {unknown}")

        run_id, run_path = self._run_path()
        started_at = datetime.now(timezone.utc).isoformat()
        manifest = {
            "run_id": run_id,
            "started_at": started_at,
            "session_key": self.settings.session_key,
            "base_url": self.settings.base_url,
            "endpoints": list(requested),
            "records": {},
            "status": "running",
        }
        _write_json(run_path / "manifest.json", manifest)

        try:
            drivers = None

            if "sessions" in requested:
                records = _records(
                    self.client.get_json("sessions", self._session_params()),
                    "sessions",
                )
                self._validate_session(records, "sessions")
                manifest["records"]["sessions"] = self._write_endpoint(
                    run_path,
                    "sessions",
                    records,
                )

            if "drivers" in requested or "car_data" in requested:
                drivers = _records(
                    self.client.get_json("drivers", self._session_params()),
                    "drivers",
                )
                self._validate_session(drivers, "drivers")

                if "drivers" in requested:
                    manifest["records"]["drivers"] = self._write_endpoint(
                        run_path,
                        "drivers",
                        drivers,
                    )

            for endpoint in ("laps", "team_radio"):
                if endpoint not in requested:
                    continue

                records = _records(
                    self.client.get_json(endpoint, self._session_params()),
                    endpoint,
                )
                self._validate_session(records, endpoint)
                manifest["records"][endpoint] = self._write_endpoint(
                    run_path,
                    endpoint,
                    records,
                )

            if "car_data" in requested:
                if drivers is None:
                    raise ValueError("Drivers são necessários para car_data")

                driver_numbers = sorted(
                    {
                        int(driver["driver_number"])
                        for driver in drivers
                        if driver.get("driver_number") is not None
                    }
                )
                telemetry_counts = {}

                for driver_number in driver_numbers:
                    records = _records(
                        self.client.get_json(
                            "car_data",
                            {
                                "session_key": self.settings.session_key,
                                "driver_number": driver_number,
                            },
                        ),
                        "car_data",
                    )
                    self._validate_session(records, "car_data")

                    observed_drivers = {
                        int(record["driver_number"])
                        for record in records
                        if record.get("driver_number") is not None
                    }
                    if any(record.get("driver_number") is None for record in records):
                        raise ValueError("Telemetria retornou chave de piloto nula")

                    if observed_drivers and observed_drivers != {driver_number}:
                        raise ValueError(
                            f"Telemetria do piloto {driver_number} "
                            f"retornou pilotos {sorted(observed_drivers)}"
                        )

                    driver_path = (
                        run_path
                        / "car_data"
                        / f"driver_number={_safe_value(driver_number)}"
                        / "data.json"
                    )
                    _write_json(driver_path, records)
                    telemetry_counts[str(driver_number)] = len(records)

                manifest["records"]["car_data"] = {
                    "drivers": len(telemetry_counts),
                    "total": sum(telemetry_counts.values()),
                    "by_driver": telemetry_counts,
                }

            manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
            manifest["status"] = "success"
            _write_json(run_path / "manifest.json", manifest)
            self.logger.info(
                "Ingestão concluída | run_id=%s | session_key=%s | path=%s",
                run_id,
                self.settings.session_key,
                run_path,
            )
            return run_path, manifest
        except Exception as error:
            manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
            manifest["status"] = "failed"
            manifest["error"] = str(error)
            _write_json(run_path / "manifest.json", manifest)
            self.logger.exception(
                "Ingestão falhou | run_id=%s | session_key=%s",
                run_id,
                self.settings.session_key,
            )
            raise


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Ingestão dos dados OpenF1 para a camada Bronze"
    )
    parser.add_argument(
        "--session-key",
        default=None,
        help="Identificador da sessão; o padrão é OPENF1_SESSION_KEY",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Diretório de saída da Bronze",
    )
    parser.add_argument(
        "--endpoints",
        nargs="+",
        choices=ENDPOINTS,
        default=ENDPOINTS,
        help="Endpoints que serão ingeridos",
    )
    return parser.parse_args(args)


def main(args=None):
    parsed = parse_args(args)
    settings = load_settings()

    if parsed.session_key is not None:
        settings = replace(settings, session_key=str(parsed.session_key))

    log_path = settings.logs_root / "ingestion.log"
    configure_logging(log_path=log_path)
    ingestion = OpenF1Ingestion(
        settings=settings,
        output_root=parsed.output_root,
    )
    ingestion.run(endpoints=parsed.endpoints)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
