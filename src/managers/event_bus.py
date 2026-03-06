"""Lightweight in-process event bus for decoupled manager orchestration."""

from collections import deque

from utils.logger import logger


class EventBus:
    def __init__(self):
        self._subs = {}
        self._queue = deque()
        self._next_token = 1

    def subscribe(self, event_name, handler, priority=0, once=False):
        token = int(self._next_token)
        self._next_token += 1

        event = str(event_name or "").strip()
        if not event:
            return None
        row = {
            "token": token,
            "handler": handler,
            "priority": int(priority or 0),
            "once": bool(once),
        }
        rows = self._subs.setdefault(event, [])
        rows.append(row)
        rows.sort(key=lambda item: (-int(item["priority"]), int(item["token"])))
        return token

    def unsubscribe(self, token):
        try:
            wanted = int(token)
        except Exception:
            return False
        removed = False
        for event, rows in list(self._subs.items()):
            kept = [row for row in rows if int(row.get("token", -1)) != wanted]
            if len(kept) != len(rows):
                removed = True
                if kept:
                    self._subs[event] = kept
                else:
                    self._subs.pop(event, None)
        return removed

    def emit(self, event_name, payload=None, immediate=False):
        event = str(event_name or "").strip()
        if not event:
            return 0
        if immediate:
            return self._dispatch(event, payload or {})
        self._queue.append((event, payload or {}))
        return 0

    def flush(self, max_events=32):
        budget = max(1, int(max_events or 1))
        total = 0
        while self._queue and total < budget:
            event, payload = self._queue.popleft()
            total += self._dispatch(event, payload)
        return total

    def _dispatch(self, event, payload):
        rows = []
        rows.extend(self._subs.get(event, []))
        rows.extend(self._subs.get("*", []))
        fired = 0
        to_remove = []
        for row in list(rows):
            handler = row.get("handler")
            if not callable(handler):
                continue
            try:
                handler(event, payload)
                fired += 1
            except Exception as exc:
                logger.debug(f"[EventBus] handler failed for '{event}': {exc}")
            if bool(row.get("once", False)):
                to_remove.append(int(row.get("token", -1)))
        for token in to_remove:
            self.unsubscribe(token)
        return fired
