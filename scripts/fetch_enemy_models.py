#!/usr/bin/env python3
"""Fetch enemy GLB models from configured Meshy pages."""

from __future__ import annotations

import argparse
import re
import urllib.request
from pathlib import Path


TARGETS = {
    "golem_boss": {
        "page": "https://www.meshy.ai/3d-models/Stylized-animated-golem-humanoid-but-bulky-built-from-stacked-stone-plates-with-glowing-cracks-of-molten-orange-light-between-segments-Runic-carvings-etched-deeply-into-the-torso-and-arms-faintly-illuminated-Jagged-rocky-shoulders-and-oversized-fists-movement-implied-by-floating-stone-fragments-orbiting-the-core-Surfaces-are-rough-weathered-stone-with-glowing-ember-veins-giving-a-livingmagical-construct-feel-Slightly-exaggerated-proportions-for-a-heroic-stylized-look-v2-01983a38-f414-768c-b20d-c44eb94bacf4",
        "out": "assets/models/enemies/golem_boss.glb",
    },
    "fire_elemental": {
        "page": "https://www.meshy.ai/3d-models/fire-elemental-creature-made-of-fire-with-a-monster-face-v2-01954f3b-69c1-73f8-a0cd-952c3fcc2e81",
        "out": "assets/models/enemies/fire_elemental.glb",
    },
    "shadow_stalker": {
        "page": "https://www.meshy.ai/3d-models/Shadow-Creature-v2-019465e6-b853-714d-8925-b92d2bbd0ba0",
        "out": "assets/models/enemies/shadow_stalker.glb",
    },
    "goblin_raider": {
        "page": "https://www.meshy.ai/3d-models/Goblin-v2-0193f14b-a3e3-7ac8-a642-20bcd4aed441",
        "out": "assets/models/enemies/goblin_raider.glb",
    },
}


MODEL_URL_RE = re.compile(r"https://assets\.meshy\.ai/[^\"'\s<]+/output/model\.glb[^\"'\s<]*")


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _extract_model_url(page_html: str) -> str:
    match = MODEL_URL_RE.search(page_html or "")
    if not match:
        return ""
    token = match.group(0)
    token = token.replace("\\u0026", "&").replace("\\", "")
    return token


def _download_file(url: str, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    out_path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="", help="Comma-separated keys")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    wanted = set()
    if args.only.strip():
        wanted = {item.strip() for item in args.only.split(",") if item.strip()}

    for key, payload in TARGETS.items():
        if wanted and key not in wanted:
            continue
        page = payload["page"]
        out = Path(payload["out"])
        print(f"[fetch] {key} page={page}")
        html = _fetch_text(page)
        model_url = _extract_model_url(html)
        if not model_url:
            print(f"[miss] {key}: model URL not found")
            continue
        print(f"[url] {key}: {model_url}")
        if args.dry_run:
            continue
        _download_file(model_url, out)
        print(f"[ok] {key}: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
