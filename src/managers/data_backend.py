import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import msgpack

from utils.logger import logger


DEFAULT_BACKEND_CONFIG = {
    "backend": "sqlite_msgpack",
    "sqlite_path": "cache/data_store.sqlite3",
    "auto_build": True,
}


def _clean_rel_token(path_like):
    token = str(path_like or "").replace("\\", "/").strip().lstrip("./")
    return token


def _json_read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        logger.error(f"[DataBackend] Не удалось прочитать JSON {path}: {exc}")
        return {}


def _json_write(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )


def _entry_key(rel_token, payload):
    if isinstance(payload, dict):
        item_id = payload.get("id")
        if isinstance(item_id, str) and item_id.strip():
            return item_id.strip()
    return Path(str(rel_token or "")).stem


def _coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    token = str(value or "").strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def load_backend_config(data_dir):
    data_root = Path(data_dir)
    cfg_path = data_root / "data_backend.json"
    cfg = dict(DEFAULT_BACKEND_CONFIG)
    if cfg_path.exists():
        payload = _json_read(cfg_path)
        if isinstance(payload, dict):
            cfg.update({k: v for k, v in payload.items() if v is not None})

    env_backend = str(os.environ.get("XBOT_DATA_BACKEND", "") or "").strip()
    if env_backend:
        cfg["backend"] = env_backend
    env_db = str(os.environ.get("XBOT_DATA_BACKEND_DB", "") or "").strip()
    if env_db:
        cfg["sqlite_path"] = env_db
    env_auto = str(os.environ.get("XBOT_DATA_BACKEND_AUTO_BUILD", "") or "").strip()
    if env_auto:
        cfg["auto_build"] = _coerce_bool(env_auto, default=cfg.get("auto_build", True))
    return cfg


class JsonDataBackend:
    name = "json"

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)

    def describe(self):
        return {"backend": self.name, "data_dir": str(self.data_dir)}

    def load_file(self, rel_path):
        return _json_read(self.data_dir / _clean_rel_token(rel_path))

    def load_recursive(self, rel_dir):
        out = {}
        root = self.data_dir / _clean_rel_token(rel_dir)
        if not root.exists():
            return out
        for json_file in root.rglob("*.json"):
            payload = _json_read(json_file)
            key = _entry_key(json_file.relative_to(self.data_dir).as_posix(), payload)
            out[key] = payload
        return out

    def save_file(self, rel_path, payload):
        _json_write(self.data_dir / _clean_rel_token(rel_path), payload)


class SQLiteMsgpackDataBackend:
    name = "sqlite_msgpack"

    def __init__(self, data_dir, db_path, auto_build=True):
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path)
        self.auto_build = bool(auto_build)
        self._ready = False

    def describe(self):
        return {
            "backend": self.name,
            "data_dir": str(self.data_dir),
            "sqlite_path": str(self.db_path),
            "auto_build": bool(self.auto_build),
        }

    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @contextmanager
    def _managed_connection(self):
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self, conn):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                path TEXT PRIMARY KEY,
                payload BLOB NOT NULL,
                source_mtime REAL NOT NULL,
                source_size INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.commit()

    def ensure_ready(self):
        if self._ready:
            return
        with self._managed_connection() as conn:
            self._init_schema(conn)
            if self.auto_build:
                self.sync_from_json(conn)
        self._ready = True

    def sync_from_json(self, conn=None):
        own_conn = conn is None
        if own_conn:
            conn = self._connect()
            self._init_schema(conn)
        try:
            disk_tokens = set()
            for json_file in self.data_dir.rglob("*.json"):
                rel_token = json_file.relative_to(self.data_dir).as_posix()
                disk_tokens.add(rel_token)
                stat = json_file.stat()
                row = conn.execute(
                    "SELECT source_mtime, source_size FROM entries WHERE path = ?",
                    (rel_token,),
                ).fetchone()
                if row and float(row[0]) == float(stat.st_mtime) and int(row[1]) == int(stat.st_size):
                    continue
                payload = _json_read(json_file)
                packed = msgpack.packb(payload, use_bin_type=True)
                conn.execute(
                    """
                    INSERT INTO entries(path, payload, source_mtime, source_size)
                    VALUES(?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        payload = excluded.payload,
                        source_mtime = excluded.source_mtime,
                        source_size = excluded.source_size
                    """,
                    (rel_token, sqlite3.Binary(packed), float(stat.st_mtime), int(stat.st_size)),
                )

            db_tokens = {
                str(row[0])
                for row in conn.execute("SELECT path FROM entries").fetchall()
            }
            stale_tokens = db_tokens - disk_tokens
            if stale_tokens:
                conn.executemany("DELETE FROM entries WHERE path = ?", [(token,) for token in sorted(stale_tokens)])

            conn.execute(
                """
                INSERT INTO metadata(key, value) VALUES('last_sync_mode', 'json_scan')
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """
            )
            conn.commit()
        finally:
            if own_conn:
                conn.close()

    def _decode_row(self, row):
        if not row:
            return {}
        try:
            return msgpack.unpackb(row[0], raw=False)
        except Exception as exc:
            logger.error(f"[DataBackend] Не удалось распаковать msgpack из {self.db_path}: {exc}")
            return {}

    def load_file(self, rel_path):
        self.ensure_ready()
        token = _clean_rel_token(rel_path)
        with self._managed_connection() as conn:
            row = conn.execute("SELECT payload FROM entries WHERE path = ?", (token,)).fetchone()
        return self._decode_row(row)

    def load_recursive(self, rel_dir):
        self.ensure_ready()
        prefix = _clean_rel_token(rel_dir).rstrip("/")
        prefix_like = f"{prefix}/%"
        out = {}
        with self._managed_connection() as conn:
            rows = conn.execute(
                "SELECT path, payload FROM entries WHERE path LIKE ? ORDER BY path ASC",
                (prefix_like,),
            ).fetchall()
        for rel_token, packed in rows:
            payload = self._decode_row((packed,))
            key = _entry_key(rel_token, payload)
            out[key] = payload
        return out

    def save_file(self, rel_path, payload):
        self.ensure_ready()
        token = _clean_rel_token(rel_path)
        src_path = self.data_dir / token
        _json_write(src_path, payload)
        stat = src_path.stat()
        packed = msgpack.packb(payload, use_bin_type=True)
        with self._managed_connection() as conn:
            conn.execute(
                """
                INSERT INTO entries(path, payload, source_mtime, source_size)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    payload = excluded.payload,
                    source_mtime = excluded.source_mtime,
                    source_size = excluded.source_size
                """,
                (token, sqlite3.Binary(packed), float(stat.st_mtime), int(stat.st_size)),
            )
            conn.commit()


def create_data_backend(data_dir, backend_config=None):
    data_root = Path(data_dir)
    cfg = load_backend_config(data_root)
    if isinstance(backend_config, dict):
        cfg.update({k: v for k, v in backend_config.items() if v is not None})

    backend_name = str(cfg.get("backend", "json") or "json").strip().lower()
    if backend_name in {"sqlite_msgpack", "sqlite+msgpack", "sqlite-msgpack"}:
        db_path = Path(str(cfg.get("sqlite_path", DEFAULT_BACKEND_CONFIG["sqlite_path"]) or DEFAULT_BACKEND_CONFIG["sqlite_path"]))
        if not db_path.is_absolute():
            db_path = data_root.parent / db_path
        return SQLiteMsgpackDataBackend(
            data_root,
            db_path=db_path,
            auto_build=_coerce_bool(cfg.get("auto_build", True), default=True),
        )
    return JsonDataBackend(data_root)
