from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
from pathlib import Path
import time
import uuid


def audited(function):
    @wraps(function)
    def execute(settings, *args, **kwargs):
        identifier = uuid.uuid4().hex
        start = time.monotonic()
        record = {
            "execution_id": identifier,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "session_key": str(kwargs.get("session_key") or settings.session_key),
            "status": "running",
        }
        root = settings.logs_root / "executions"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{identifier}.json"

        def save():
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)

        save()
        try:
            result = function(settings, *args, **kwargs)
            record["status"] = result["transformation"]["status"]
            record["pipeline_manifest"] = result["pipeline_manifest"]
            record["outputs"] = {}
            for name, dataset in result["gold"]["datasets"].items():
                source = Path(dataset["path"])
                digest = hashlib.sha256()
                with source.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                record["outputs"][name] = {
                    "rows": dataset["rows"], "bytes": source.stat().st_size,
                    "sha256": digest.hexdigest(),
                }
            result["execution_id"] = identifier
            return result
        except Exception as error:
            record["status"] = "failed"
            record["error_type"] = type(error).__name__
            raise
        finally:
            record["duration_seconds"] = round(time.monotonic() - start, 3)
            record["completed_at"] = datetime.now(timezone.utc).isoformat()
            save()
    return execute
