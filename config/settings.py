from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve_path(value, project_root):
    path = Path(value)

    if path.is_absolute():
        return path

    return project_root / path


def _read_int(name, default):
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    return int(value)


def _read_float(name, default):
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    return float(value)


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_root: Path
    bronze_root: Path
    silver_root: Path
    gold_root: Path
    logs_root: Path
    base_url: str
    session_key: str
    request_timeout: float
    max_retries: int
    min_request_interval: float
    postgres_url: str | None

    @classmethod
    def from_env(cls, env_file=None):
        project_root = PROJECT_ROOT
        dotenv_path = env_file or project_root / ".env"
        load_dotenv(dotenv_path=dotenv_path, override=False)

        data_root = _resolve_path(
            os.getenv("OPENF1_DATA_ROOT", "data"),
            project_root,
        )

        base_url = (
            os.getenv("OPENF1_BASE_URL")
            or os.getenv("API_OPENF1")
            or "https://api.openf1.org/v1"
        ).rstrip("/")

        postgres_url = os.getenv("POSTGRES_URL")

        if postgres_url is not None and not postgres_url.strip():
            postgres_url = None

        return cls(
            project_root=project_root,
            data_root=data_root,
            bronze_root=data_root / "bronze",
            silver_root=data_root / "silver",
            gold_root=data_root / "gold",
            logs_root=project_root / "logs",
            base_url=base_url,
            session_key=os.getenv("OPENF1_SESSION_KEY", "9158"),
            request_timeout=_read_float("OPENF1_REQUEST_TIMEOUT", 30.0),
            max_retries=_read_int("OPENF1_MAX_RETRIES", 3),
            min_request_interval=_read_float(
                "OPENF1_MIN_REQUEST_INTERVAL",
                2.1,
            ),
            postgres_url=postgres_url,
        )


def load_settings(env_file=None):
    return Settings.from_env(env_file=env_file)
