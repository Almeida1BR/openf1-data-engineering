from config.settings import Settings
from src.ingestion.ingestion_openf1 import OpenF1Ingestion


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_json(self, endpoint, params):
        self.calls.append((endpoint, params))

        if endpoint == "sessions":
            return [
                {
                    "session_key": 9158,
                    "session_name": "Practice 1",
                }
            ]

        if endpoint == "drivers":
            return [
                {
                    "session_key": 9158,
                    "driver_number": 1,
                    "full_name": "Max VERSTAPPEN",
                    "last_name": "Verstappen",
                },
                {
                    "session_key": 9158,
                    "driver_number": 4,
                    "full_name": "Lando NORRIS",
                    "last_name": "Norris",
                },
            ]

        if endpoint == "laps":
            return [
                {
                    "session_key": 9158,
                    "driver_number": 1,
                    "lap_number": 1,
                }
            ]

        if endpoint == "team_radio":
            return []

        if endpoint == "car_data":
            return [
                {
                    "session_key": params["session_key"],
                    "driver_number": params["driver_number"],
                    "date": "2023-09-15T09:30:00+00:00",
                }
            ]

        raise AssertionError(endpoint)


def build_settings(tmp_path):
    data_root = tmp_path / "data"
    return Settings(
        project_root=tmp_path,
        data_root=data_root,
        bronze_root=data_root / "bronze",
        silver_root=data_root / "silver",
        gold_root=data_root / "gold",
        logs_root=tmp_path / "logs",
        base_url="https://api.openf1.org/v1",
        session_key="9158",
        request_timeout=1.0,
        max_retries=0,
        min_request_interval=0.0,
        postgres_url=None,
    )


def test_ingestion_creates_session_run_with_per_driver_telemetry(tmp_path):
    client = FakeClient()
    ingestion = OpenF1Ingestion(
        settings=build_settings(tmp_path),
        client=client,
    )

    run_path, manifest = ingestion.run()

    assert manifest["status"] == "success"
    assert manifest["session_key"] == "9158"
    assert manifest["records"]["drivers"] == 2
    assert manifest["records"]["car_data"]["drivers"] == 2
    assert (run_path / "manifest.json").exists()
    assert (run_path / "sessions" / "sessions.json").exists()
    assert (run_path / "drivers" / "drivers.json").exists()
    assert (run_path / "laps" / "laps.json").exists()
    assert (run_path / "team_radio" / "team_radio.json").exists()
    assert (run_path / "car_data" / "driver_number=1" / "data.json").exists()
    assert (run_path / "car_data" / "driver_number=4" / "data.json").exists()
    assert [call[0] for call in client.calls].count("car_data") == 2


def test_ingestion_rejects_telemetry_from_another_driver(tmp_path):
    client = FakeClient()
    original_get_json = client.get_json

    def get_wrong_driver(endpoint, params):
        payload = original_get_json(endpoint, params)

        if endpoint == "car_data":
            payload[0]["driver_number"] = 99

        return payload

    client.get_json = get_wrong_driver
    ingestion = OpenF1Ingestion(settings=build_settings(tmp_path), client=client)

    try:
        ingestion.run(endpoints=("drivers", "car_data"))
    except ValueError as error:
        assert "retornou pilotos" in str(error)
    else:
        raise AssertionError("A ingestão deveria rejeitar o piloto incorreto")
