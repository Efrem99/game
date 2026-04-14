import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRAPHICS_SETTINGS_PATH = ROOT / "data" / "graphics_settings.json"


def _load_graphics_settings():
    return json.loads(GRAPHICS_SETTINGS_PATH.read_text(encoding="utf-8-sig"))


def test_default_quality_is_not_low():
    payload = _load_graphics_settings()
    quality = str(payload.get("quality", "") or "").strip().lower()
    assert quality in {"medium", "high", "ultra"}


def test_bloom_intensity_stays_in_readable_range():
    payload = _load_graphics_settings()
    post = payload.get("post_processing", {}) if isinstance(payload, dict) else {}
    bloom = post.get("bloom", {}) if isinstance(post, dict) else {}
    intensity = float(bloom.get("intensity", 0.0) or 0.0)
    assert 0.0 <= intensity <= 0.55


def test_exposure_default_targets_daylight_balance():
    payload = _load_graphics_settings()
    pbr = payload.get("pbr", {}) if isinstance(payload, dict) else {}
    exposure = float(pbr.get("exposure", 1.0) or 1.0)
    assert 1.0 <= exposure <= 1.35
