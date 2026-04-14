import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.data_backend import SQLiteMsgpackDataBackend, load_backend_config


def main():
    data_dir = Path("data")
    cfg = load_backend_config(data_dir)
    backend_name = str(cfg.get("backend", "json") or "json").strip().lower()
    if backend_name not in {"sqlite_msgpack", "sqlite+msgpack", "sqlite-msgpack"}:
        raise SystemExit(f"Data backend config is '{backend_name}', not sqlite_msgpack.")

    db_path = Path(str(cfg.get("sqlite_path", "cache/data_store.sqlite3") or "cache/data_store.sqlite3"))
    if not db_path.is_absolute():
        db_path = data_dir.parent / db_path

    backend = SQLiteMsgpackDataBackend(
        data_dir=data_dir,
        db_path=db_path,
        auto_build=True,
    )
    backend.ensure_ready()
    print(f"Data backend ready: {db_path}")


if __name__ == "__main__":
    main()
