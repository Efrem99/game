"""Thin runtime data-access seam over data backend and legacy JSON files."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from utils.logger import logger


def _clone_default(default, fallback):
    if default is None:
        return copy.deepcopy(fallback)
    return copy.deepcopy(default)


def _data_manager(app):
    return getattr(app, "data_mgr", None) or getattr(app, "data_manager", None)


def _data_root(app):
    mgr = _data_manager(app)
    if mgr is not None:
        data_dir = getattr(mgr, "data_dir", None)
        if data_dir:
            return Path(data_dir)
    project_root = Path(str(getattr(app, "project_root", ".") or "."))
    return project_root / "data"


def _backend(app):
    mgr = _data_manager(app)
    return getattr(mgr, "backend", None) if mgr is not None else None


def _normalize_rel_token(path_like):
    token = str(path_like or "").replace("\\", "/").strip()
    if not token:
        return ""
    if token.lower().startswith("data/"):
        token = token[5:]
    while token.startswith("./"):
        token = token[2:]
    return token.lstrip("/")


def _read_json_path(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        logger.warning(f"[DataAccess] Не удалось прочитать JSON {path}: {exc}")
        return None


def _candidate_path(app, candidate):
    raw = Path(str(candidate or "").strip())
    if raw.is_absolute():
        return raw
    token = _normalize_rel_token(candidate)
    if not token:
        return None
    return _data_root(app) / token


def load_data_file(app, rel_path, default=None):
    token = _normalize_rel_token(rel_path)
    if not token:
        return _clone_default(default, {})
    backend = _backend(app)
    source_path = _data_root(app) / token
    if backend is not None and hasattr(backend, "load_file"):
        try:
            payload = backend.load_file(token)
            if source_path.exists() or payload not in ({}, [], None):
                if isinstance(payload, (dict, list)):
                    return payload
        except Exception as exc:
            logger.warning(f"[DataAccess] Backend load_file failed for {token}: {exc}")
    if source_path.exists():
        payload = _read_json_path(source_path)
        if isinstance(payload, (dict, list)):
            return payload
    return _clone_default(default, {})


def load_data_recursive(app, rel_dir, default=None):
    token = _normalize_rel_token(rel_dir).rstrip("/")
    if not token:
        return _clone_default(default, {})
    backend = _backend(app)
    source_dir = _data_root(app) / token
    if backend is not None and hasattr(backend, "load_recursive"):
        try:
            payload = backend.load_recursive(token)
            if source_dir.exists() or payload not in ({}, None):
                if isinstance(payload, dict):
                    return payload
        except Exception as exc:
            logger.warning(f"[DataAccess] Backend load_recursive failed for {token}: {exc}")
    if source_dir.exists():
        out = {}
        for json_file in sorted(source_dir.rglob("*.json")):
            payload = _read_json_path(json_file)
            if isinstance(payload, dict):
                out[json_file.stem] = payload
        return out
    return _clone_default(default, {})


def load_data_file_candidates(app, candidates, default=None):
    for candidate in list(candidates or []):
        path = _candidate_path(app, candidate)
        token = _normalize_rel_token(candidate)
        if not token:
            continue
        backend = _backend(app)
        if backend is not None and hasattr(backend, "load_file"):
            try:
                payload = backend.load_file(token)
                if (path is not None and path.exists()) or payload not in ({}, [], None):
                    if isinstance(payload, (dict, list)):
                        return payload
            except Exception as exc:
                logger.warning(f"[DataAccess] Backend candidate load failed for {token}: {exc}")
        if path is not None and path.exists():
            payload = _read_json_path(path)
            if isinstance(payload, (dict, list)):
                return payload
    return _clone_default(default, {})
