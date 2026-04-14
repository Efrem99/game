import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "actors" / "player_animations.json"


def _load_payload():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))


def _manifest_sources_map(payload):
    rows = payload.get("manifest", {}).get("sources", [])
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or row.get("state") or row.get("id") or "").strip().lower()
        path = str(row.get("path") or row.get("file") or row.get("src") or "").strip().replace("\\", "/")
        if key and path:
            out[key] = path
    return out


def test_casting_prefers_fast_cast_clip():
    payload = _load_payload()
    casting = payload.get("player", {}).get("casting", [])
    if isinstance(casting, str):
        casting = [casting]
    assert isinstance(casting, list)
    assert casting and str(casting[0]).strip().lower() == "cast_fast"


def test_bow_aim_and_shoot_sources_are_mixamo_player_clips():
    payload = _load_payload()
    sources = _manifest_sources_map(payload)
    for key in ("bow_aim", "bow_shoot", "cast_fast"):
        clip = sources.get(key, "")
        assert clip.startswith("assets/anims/mixamo/player/")
