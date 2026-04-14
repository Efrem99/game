"""Low-level startup breadcrumbs that survive logger/graphics init failures."""

import json
from datetime import datetime, timezone
from pathlib import Path


def write_startup_breadcrumb(project_root, stage, context=None):
    root = Path(project_root)
    payload = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "stage": str(stage or "").strip() or "unknown",
        "context": context if isinstance(context, dict) else {},
    }
    path = root / "logs" / "startup_breadcrumbs.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return path
    except Exception:
        return None
