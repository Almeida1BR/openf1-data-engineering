import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

import pandas as pd

from sqlalchemy import create_engine, inspect, text

from config.settings import load_settings
from src.loading.loader import load_gold


def main():
    settings = load_settings()
    root = settings.gold_root / f"session_key={settings.session_key}"
    manifest = json.loads((root / "manifest.json").read_text())
    for _ in range(2):
        load_gold(root, settings.postgres_url)
    engine = create_engine(settings.postgres_url)
    with engine.connect() as connection:
        original_name = connection.execute(text(
            "SELECT full_name FROM analytics.driver_session_performance "
            "WHERE session_key=:session ORDER BY driver_number LIMIT 1"
        ), {"session": int(settings.session_key)}).scalar_one()
    with TemporaryDirectory(prefix="openf1-rollback-") as temporary:
        target = Path(temporary)
        for source in root.glob("*.parquet"):
            shutil.copy2(source, target / source.name)
        shutil.copy2(root / "manifest.json", target / "manifest.json")
        drivers_path = target / "driver_session_performance.parquet"
        drivers = pd.read_parquet(drivers_path)
        drivers["full_name"] = "Teste transacional temporário"
        drivers.to_parquet(drivers_path, index=False)
        telemetry_path = target / "telemetry_summary.parquet"
        telemetry = pd.read_parquet(telemetry_path)
        pd.concat([telemetry, telemetry.iloc[:1]]).to_parquet(telemetry_path, index=False)
        try:
            load_gold(target, settings.postgres_url)
        except Exception:
            pass
        else:
            raise AssertionError("Chave duplicada deveria interromper a carga")
    with engine.connect() as connection:
        after_name = connection.execute(text(
            "SELECT full_name FROM analytics.driver_session_performance "
            "WHERE session_key=:session ORDER BY driver_number LIMIT 1"
        ), {"session": int(settings.session_key)}).scalar_one()
        assert after_name == original_name
    print("Rollback confirmado: alteração anterior à falha não persistiu")
    with engine.connect() as connection:
        for name, dataset in manifest["datasets"].items():
            count = connection.execute(
                text(f'SELECT count(*) FROM analytics."{name}" WHERE session_key=:session'),
                {"session": int(settings.session_key)},
            ).scalar_one()
            assert count == dataset["rows"], (name, count, dataset["rows"])
            assert inspect(connection).get_pk_constraint(name, schema="analytics")["constrained_columns"]
            print(f"{name}: {count} linhas, chave primária preservada")
        assert connection.execute(text(
            "SELECT jsonb_typeof(segments_sector_1) FROM analytics.lap_performance "
            "WHERE segments_sector_1 IS NOT NULL LIMIT 1"
        )).scalar_one() == "array"
        for query in sorted((Path(__file__).resolve().parents[1] / "sql/queries").glob("*.sql")):
            rows = connection.execute(text(query.read_text())).fetchall()
            assert rows, query.name
            print(f"{query.name}: {len(rows)} resultados")
    engine.dispose()


if __name__ == "__main__":
    main()
