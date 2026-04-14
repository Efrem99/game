import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import msgpack

from utils.logger import logger
from utils.runtime_paths import project_root


DEFAULT_SAVE_BACKEND_CONFIG = {
    "backend": "sqlite_msgpack",
    "sqlite_path": "save_store.sqlite3",
    "auto_build": True,
    "mirror_json": True,
}

_SAVE_SLOT_SUFFIXES = {".json", ".sav", ".save"}


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


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        logger.warning(f"[SaveBackend] Не удалось прочитать JSON-сейв {path}: {exc}")
        return None


def _write_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _payload_saved_at(payload):
    if not isinstance(payload, dict):
        return datetime.now(timezone.utc).timestamp()
    meta = payload.get("meta", {})
    if not isinstance(meta, dict):
        return datetime.now(timezone.utc).timestamp()
    raw = meta.get("saved_at_utc")
    if isinstance(raw, str) and raw.strip():
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except Exception:
            pass
    return datetime.now(timezone.utc).timestamp()


def load_save_backend_config():
    cfg = dict(DEFAULT_SAVE_BACKEND_CONFIG)
    cfg_path = project_root() / "data" / "save_backend.json"
    if cfg_path.exists():
        payload = _read_json(cfg_path)
        if isinstance(payload, dict):
            cfg.update({k: v for k, v in payload.items() if v is not None})

    env_backend = str(os.environ.get("XBOT_SAVE_BACKEND", "") or "").strip()
    if env_backend:
        cfg["backend"] = env_backend
    env_db = str(os.environ.get("XBOT_SAVE_BACKEND_DB", "") or "").strip()
    if env_db:
        cfg["sqlite_path"] = env_db
    env_auto = str(os.environ.get("XBOT_SAVE_BACKEND_AUTO_BUILD", "") or "").strip()
    if env_auto:
        cfg["auto_build"] = _coerce_bool(env_auto, default=cfg.get("auto_build", True))
    env_mirror = str(os.environ.get("XBOT_SAVE_BACKEND_MIRROR_JSON", "") or "").strip()
    if env_mirror:
        cfg["mirror_json"] = _coerce_bool(env_mirror, default=cfg.get("mirror_json", True))
    return cfg


class JsonSaveBackend:
    name = "json"

    def __init__(self, save_dir):
        self.save_dir = Path(save_dir)

    def describe(self):
        return {"backend": self.name, "save_dir": str(self.save_dir)}

    def path_exists(self, path):
        return Path(path).exists()

    def read_path(self, path):
        return _read_json(path)

    def write_path(self, path, payload):
        _write_json(path, payload)

    def latest_path(self, paths):
        candidates = [Path(path) for path in paths if Path(path).exists()]
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]


class SQLiteMsgpackSaveBackend:
    name = "sqlite_msgpack"

    def __init__(self, save_dir, db_path, auto_build=True, mirror_json=True):
        self.save_dir = Path(save_dir)
        self.db_path = Path(db_path)
        self.auto_build = bool(auto_build)
        self.mirror_json = bool(mirror_json)
        self._ready = False

    def describe(self):
        return {
            "backend": self.name,
            "save_dir": str(self.save_dir),
            "sqlite_path": str(self.db_path),
            "auto_build": bool(self.auto_build),
            "mirror_json": bool(self.mirror_json),
        }

    def _key_for_path(self, path):
        target = Path(path)
        if target.suffix.lower() in _SAVE_SLOT_SUFFIXES:
            stem = target.stem.strip().lower()
            if stem in {"autosave", "latest"} or stem.startswith("slot"):
                return stem
        return target.name.strip().lower()

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
            CREATE TABLE IF NOT EXISTS saves (
                slot_key TEXT PRIMARY KEY,
                payload BLOB NOT NULL,
                saved_at REAL NOT NULL,
                source_mtime REAL NOT NULL,
                source_size INTEGER NOT NULL
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
            disk_keys = set()
            for json_path in sorted(self.save_dir.glob("*.json")):
                key = self._key_for_path(json_path)
                disk_keys.add(key)
                payload = _read_json(json_path)
                if not isinstance(payload, dict):
                    continue
                stat = json_path.stat()
                row = conn.execute(
                    "SELECT source_mtime, source_size FROM saves WHERE slot_key = ?",
                    (key,),
                ).fetchone()
                if row and float(row[0]) == float(stat.st_mtime) and int(row[1]) == int(stat.st_size):
                    continue
                packed = msgpack.packb(payload, use_bin_type=True)
                conn.execute(
                    """
                    INSERT INTO saves(slot_key, payload, saved_at, source_mtime, source_size)
                    VALUES(?, ?, ?, ?, ?)
                    ON CONFLICT(slot_key) DO UPDATE SET
                        payload = excluded.payload,
                        saved_at = excluded.saved_at,
                        source_mtime = excluded.source_mtime,
                        source_size = excluded.source_size
                    """,
                    (
                        key,
                        sqlite3.Binary(packed),
                        float(_payload_saved_at(payload)),
                        float(stat.st_mtime),
                        int(stat.st_size),
                    ),
                )
            conn.commit()
        finally:
            if own_conn:
                conn.close()

    def _decode_row(self, row):
        if not row:
            return None
        try:
            return msgpack.unpackb(row[0], raw=False)
        except Exception as exc:
            logger.warning(f"[SaveBackend] Не удалось распаковать msgpack-сейв из {self.db_path}: {exc}")
            return None

    def path_exists(self, path):
        self.ensure_ready()
        key = self._key_for_path(path)
        with self._managed_connection() as conn:
            row = conn.execute("SELECT 1 FROM saves WHERE slot_key = ? LIMIT 1", (key,)).fetchone()
        return bool(row) or Path(path).exists()

    def read_path(self, path):
        self.ensure_ready()
        key = self._key_for_path(path)
        with self._managed_connection() as conn:
            row = conn.execute("SELECT payload FROM saves WHERE slot_key = ?", (key,)).fetchone()
        payload = self._decode_row(row)
        if isinstance(payload, dict):
            return payload
        disk_payload = _read_json(path)
        if isinstance(disk_payload, dict):
            self.write_path(path, disk_payload)
        return disk_payload

    def write_path(self, path, payload):
        self.ensure_ready()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if self.mirror_json:
            _write_json(target, payload)
            stat = target.stat()
            source_mtime = float(stat.st_mtime)
            source_size = int(stat.st_size)
        else:
            source_mtime = float(datetime.now(timezone.utc).timestamp())
            source_size = len(msgpack.packb(payload, use_bin_type=True))
        packed = msgpack.packb(payload, use_bin_type=True)
        key = self._key_for_path(target)
        with self._managed_connection() as conn:
            conn.execute(
                """
                INSERT INTO saves(slot_key, payload, saved_at, source_mtime, source_size)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(slot_key) DO UPDATE SET
                    payload = excluded.payload,
                    saved_at = excluded.saved_at,
                    source_mtime = excluded.source_mtime,
                    source_size = excluded.source_size
                """,
                (
                    key,
                    sqlite3.Binary(packed),
                    float(_payload_saved_at(payload)),
                    source_mtime,
                    source_size,
                ),
            )
            conn.commit()

    def latest_path(self, paths):
        self.ensure_ready()
        candidates = [(self._key_for_path(path), Path(path)) for path in paths]
        with self._managed_connection() as conn:
            rows = conn.execute("SELECT slot_key, saved_at FROM saves").fetchall()
        saved_map = {str(row[0]): float(row[1]) for row in rows}
        ranked = [(saved_map.get(key, float("-inf")), path) for key, path in candidates if key in saved_map or path.exists()]
        if not ranked:
            return None
        ranked.sort(key=lambda row: row[0], reverse=True)
        return ranked[0][1]


def create_save_backend(save_dir, backend_config=None):
    save_root = Path(save_dir)
    cfg = load_save_backend_config()
    if isinstance(backend_config, dict):
        cfg.update({k: v for k, v in backend_config.items() if v is not None})
    backend_name = str(cfg.get("backend", "json") or "json").strip().lower()
    if backend_name in {"sqlite_msgpack", "sqlite+msgpack", "sqlite-msgpack"}:
        db_path = Path(str(cfg.get("sqlite_path", DEFAULT_SAVE_BACKEND_CONFIG["sqlite_path"]) or DEFAULT_SAVE_BACKEND_CONFIG["sqlite_path"]))
        if not db_path.is_absolute():
            db_path = save_root / db_path
        return SQLiteMsgpackSaveBackend(
            save_dir=save_root,
            db_path=db_path,
            auto_build=_coerce_bool(cfg.get("auto_build", True), default=True),
            mirror_json=_coerce_bool(cfg.get("mirror_json", True), default=True),
        )
    return JsonSaveBackend(save_root)
