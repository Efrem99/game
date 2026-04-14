"""Compatibility shim for legacy VideoBot imports.

The active VideoBot runtime is fully integrated into ``app.py``
(``XBotApp._video_bot_*`` methods and the ``XBOT_VIDEO_BOT_PLAN`` env path).

This shim stays to avoid hard ImportError in any old tooling that still
references ``from managers.video_bot import VideoBotManager``.

TODO(cleanup): Verify no active code imports VideoBotManager, then delete
this file entirely. Tracked in docs/TODO.md §10 (video_bot_plan / old video-bot).
"""


class VideoBotManager:
    """No-op placeholder for legacy integrations. Do not use in new code."""

    def __init__(self, app=None):
        self.app = app

    def update(self, dt):
        _ = dt
        return None
