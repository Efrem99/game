"""Dirty-state helpers for the embedded studio shell."""

from __future__ import annotations


def normalize_source_text(raw_text: str | None) -> str:
    return str(raw_text or "").replace("\r\n", "\n")


def is_source_dirty(*, persisted_text: str | None, buffer_text: str | None, editable: bool) -> bool:
    if not editable:
        return False
    return normalize_source_text(buffer_text) != normalize_source_text(persisted_text)


def decorate_preview_title(title: str | None, *, dirty: bool) -> str:
    base = str(title or "").strip() or "Selection"
    return f"{base} *" if dirty else base


def compose_preview_status(status: str | None, *, dirty: bool) -> str:
    base = str(status or "").strip()
    if not dirty:
        return base
    if not base:
        return "Unsaved changes in the shared source buffer."
    if "save to persist" in base.lower() or "unsaved" in base.lower():
        return base
    return f"{base} Unsaved changes pending."
