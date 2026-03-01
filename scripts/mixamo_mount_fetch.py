#!/usr/bin/env python3
"""
Fetch mount/riding animations from Mixamo API and wire them into the runtime manifest.

Usage:
  python scripts/mixamo_mount_fetch.py --dry-run
  python scripts/mixamo_mount_fetch.py --token-env MIXAMO_ACCESS_TOKEN
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

DEFAULT_CHARACTER_ID = "ef7eb018-7cf3-4ae1-99ac-bab1c2c5d419"  # Mixamo XBot

# Query order matters: first successful query wins.
TARGET_QUERIES: Dict[str, List[str]] = {
    "mounting_horse": [
        "mount horse",
        "getting on horse",
        "climb up",
    ],
    "mounted_idle_horse": [
        "sitting idle",
        "seated idle",
        "horse idle",
    ],
    "mounted_move_horse": [
        "run forward",
        "running",
        "medium run",
    ],
    "dismounting_horse": [
        "dismount horse",
        "getting off horse",
        "jump down",
    ],
    "mounting_carriage": [
        "climb up",
        "sit down",
        "mount vehicle",
    ],
    "mounted_idle_carriage": [
        "sitting idle",
        "sit idle",
        "seated idle",
    ],
    "mounted_move_carriage": [
        "sitting idle",
        "sitting",
        "bumpy ride",
        "ride",
    ],
    "dismounting_carriage": [
        "stand up",
        "get up",
        "jump down",
    ],
    "mounting_boat": [
        "climb up",
        "step up",
        "enter",
    ],
    "mounted_idle_boat": [
        "sitting idle",
        "row idle",
        "seated idle",
    ],
    "mounted_move_boat": [
        "paddle",
        "paddling",
        "rowing",
        "row boat",
    ],
    "dismounting_boat": [
        "stand up",
        "step down",
        "jump down",
    ],
}

# Pinned product ids keep selection deterministic and avoid noisy search results.
TARGET_PRODUCT_IDS: Dict[str, str] = {
    "mounting_horse": "c9c83859-b96c-11e4-a802-0aaa78deedf9",       # Climbing
    "mounted_idle_horse": "c9ccab1b-b96c-11e4-a802-0aaa78deedf9",    # Sitting Idle
    "mounted_move_horse": "c9ccfb22-b96c-11e4-a802-0aaa78deedf9",    # Run Forward
    "dismounting_horse": "c9cea6ae-b96c-11e4-a802-0aaa78deedf9",     # Jump Down
    "mounting_carriage": "c9c83859-b96c-11e4-a802-0aaa78deedf9",     # Climbing
    "mounted_idle_carriage": "c9ccab1b-b96c-11e4-a802-0aaa78deedf9", # Sitting Idle
    "mounted_move_carriage": "c9c699a5-b96c-11e4-a802-0aaa78deedf9", # Sitting
    "dismounting_carriage": "c9c6d314-b96c-11e4-a802-0aaa78deedf9",  # Stand Up
    "mounting_boat": "c9c83859-b96c-11e4-a802-0aaa78deedf9",         # Climbing
    "mounted_idle_boat": "c9ccab1b-b96c-11e4-a802-0aaa78deedf9",     # Sitting Idle
    "mounted_move_boat": "c9cc1658-b96c-11e4-a802-0aaa78deedf9",     # Paddling
    "dismounting_boat": "c9c6d314-b96c-11e4-a802-0aaa78deedf9",      # Stand Up
}

DEFAULT_LOOPS: Dict[str, bool] = {
    "mounting_horse": False,
    "mounted_idle_horse": True,
    "mounted_move_horse": True,
    "dismounting_horse": False,
    "mounting_carriage": False,
    "mounted_idle_carriage": True,
    "mounted_move_carriage": True,
    "dismounting_carriage": False,
    "mounting_boat": False,
    "mounted_idle_boat": True,
    "mounted_move_boat": True,
    "dismounting_boat": False,
}


class MixamoClient:
    BASE = "https://www.mixamo.com/api/v1"

    def __init__(self, token: str, timeout_sec: float = 45.0, max_retries: int = 5):
        self.token = token.strip()
        self.timeout_sec = max(5.0, float(timeout_sec))
        self.max_retries = max(0, int(max_retries))
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "x-api-key": "mixamo2",
            "x-app-id": "cc6a7eb7-e39f-4f98-a90a-09b92940fdd9",
        }

    def _request_json(self, method: str, url: str, payload: Optional[dict] = None):
        data = None
        headers = dict(self._headers)
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url=url, data=data, headers=headers, method=method)

        attempt = 0
        while True:
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    raw = resp.read()
                    if not raw:
                        return {}
                    return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                retryable = exc.code in {429, 500, 502, 503, 504}
                if retryable and attempt < self.max_retries:
                    retry_after = 0.0
                    try:
                        value = exc.headers.get("Retry-After")
                        retry_after = float(value) if value is not None else 0.0
                    except Exception:
                        retry_after = 0.0
                    backoff = (2.0 ** attempt) * 0.8
                    sleep_sec = max(retry_after, min(12.0, backoff))
                    time.sleep(max(0.2, sleep_sec))
                    attempt += 1
                    continue
                raise

    def search_products(self, query: str, page: int = 1, limit: int = 96) -> List[dict]:
        params = urllib.parse.urlencode(
            {
                "limit": str(limit),
                "page": str(page),
                "order": "",
                "type": "Motion,MotionPack",
                "query": query,
            }
        )
        url = f"{self.BASE}/products?{params}"
        payload = self._request_json("GET", url)
        results = payload.get("results", []) if isinstance(payload, dict) else []
        return [item for item in results if isinstance(item, dict)]

    def product_details(self, product_id: str, character_id: str) -> Optional[dict]:
        params = urllib.parse.urlencode({"similar": "0", "character_id": character_id})
        url = f"{self.BASE}/products/{product_id}?{params}"
        payload = self._request_json("GET", url)
        return payload if isinstance(payload, dict) else None

    def request_export(
        self,
        character_id: str,
        product_name: str,
        product_type: str,
        gms_hash: dict,
    ) -> Optional[dict]:
        url = f"{self.BASE}/animations/export"
        prepared_hash = _prepare_gms_hash(gms_hash)
        if not isinstance(prepared_hash, dict):
            return None
        body = {
            "character_id": character_id,
            "gms_hash": [prepared_hash],
            "product_name": str(product_name or "").strip() or "MixamoClip",
            "type": str(product_type or "").strip() or "Motion",
            "preferences": {
                "format": "fbx7_2019",
                "skin": False,
                "fps": "24",
                "reducekf": "0",
            },
        }
        payload = self._request_json("POST", url, body)
        if not isinstance(payload, dict):
            return None
        job_ref = (
            str(payload.get("job_id") or payload.get("job_uuid") or payload.get("id") or "").strip()
        )
        download_url = _extract_download_url(payload.get("job_result")) or _extract_download_url(payload)
        if not job_ref and not download_url:
            return None
        return {"job_ref": job_ref, "download_url": download_url}

    def wait_export_url(
        self,
        character_id: str,
        job_ref: str,
        max_wait_sec: float = 120.0,
        poll_sec: float = 1.5,
    ) -> Optional[str]:
        poll = max(0.3, float(poll_sec))
        deadline = time.time() + max(2.0, float(max_wait_sec))

        while time.time() < deadline:
            params = urllib.parse.urlencode({"job_id": job_ref})
            url = f"{self.BASE}/characters/{character_id}/monitor?{params}"
            payload = self._request_json("GET", url)
            result = _extract_job_payload(payload, job_ref=job_ref)
            if not result:
                time.sleep(poll)
                continue
            status = str(result.get("status", "")).strip().lower()
            if status in {"completed", "success", "done"}:
                download_url = _extract_download_url(result.get("job_result")) or _extract_download_url(result)
                if download_url:
                    return download_url
                return None
            if status in {"error", "failed"}:
                return None
            time.sleep(poll)
        return None

    def download_file(self, url: str, out_path: Path):
        data = None
        try:
            req = urllib.request.Request(url=url, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = resp.read()
        except Exception:
            # Some hosts still require auth headers; try once with API headers.
            req = urllib.request.Request(url=url, headers=self._headers, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = resp.read()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data or b"")


def _extract_job_payload(payload, job_ref: str) -> Optional[dict]:
    if isinstance(payload, dict):
        if (
            str(payload.get("job_id", "")).strip() == job_ref
            or str(payload.get("job_uuid", "")).strip() == job_ref
        ):
            return payload
        jobs = payload.get("jobs")
        if isinstance(jobs, list):
            for item in jobs:
                if not isinstance(item, dict):
                    continue
                if (
                    str(item.get("job_id", "")).strip() == job_ref
                    or str(item.get("job_uuid", "")).strip() == job_ref
                ):
                    return item
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            if (
                str(item.get("job_id", "")).strip() == job_ref
                or str(item.get("job_uuid", "")).strip() == job_ref
            ):
                return item
    return None


def _extract_download_url(value) -> Optional[str]:
    if isinstance(value, str):
        token = value.strip()
        if token.startswith("http://") or token.startswith("https://"):
            return token
        return None
    if isinstance(value, dict):
        for key in ("url", "download_url", "result", "job_result"):
            nested = value.get(key)
            found = _extract_download_url(nested)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _extract_download_url(item)
            if found:
                return found
    return None


def _prepare_gms_hash(gms_hash: dict) -> Optional[dict]:
    if not isinstance(gms_hash, dict):
        return None
    prepared = json.loads(json.dumps(gms_hash))

    params = prepared.get("params")
    if isinstance(params, list):
        values = []
        for item in params:
            value = item
            if isinstance(item, (list, tuple)) and item:
                value = item[-1]
            try:
                values.append(str(int(float(value))))
            except Exception:
                continue
        prepared["params"] = ",".join(values)
    elif not isinstance(params, str):
        prepared["params"] = ""

    trim = prepared.get("trim")
    if isinstance(trim, (list, tuple)) and len(trim) >= 2:
        try:
            prepared["trim"] = [int(float(trim[0])), int(float(trim[1]))]
        except Exception:
            prepared["trim"] = [0, 100]
    else:
        prepared["trim"] = [0, 100]

    if "overdrive" not in prepared:
        prepared["overdrive"] = 0

    return prepared


def _pick_best_product(results: Iterable[dict], query: str) -> Optional[dict]:
    query_norm = query.strip().lower()

    def score(item: dict) -> Tuple[int, int]:
        name = str(item.get("name", "")).strip().lower()
        typ = str(item.get("type", "")).strip().lower()
        score_primary = 0
        if typ == "motion":
            score_primary += 5
        if typ == "motionpack":
            score_primary -= 8
        if "pack" in name:
            score_primary -= 6
        if "," not in name:
            score_primary += 3
        if query_norm in name:
            score_primary += 6
        if any(tok in name for tok in query_norm.split() if tok):
            score_primary += 2
        score_secondary = -len(name)
        return score_primary, score_secondary

    items = [it for it in results if isinstance(it, dict)]
    if not items:
        return None
    motion_items = [it for it in items if str(it.get("type", "")).strip().lower() == "motion"]
    if motion_items:
        items = motion_items
    items.sort(key=score, reverse=True)
    return items[0]


def _detect_extension(download_url: str) -> str:
    path = urllib.parse.urlparse(download_url).path
    suffix = Path(path).suffix.lower().strip()
    if suffix in {".fbx", ".zip", ".glb", ".gltf", ".bam"}:
        return suffix
    return ".fbx"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _save_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def _ensure_manifest_entry(manifest_sources: List[dict], key: str, loop: bool) -> dict:
    for entry in manifest_sources:
        if isinstance(entry, dict) and str(entry.get("key", "")).strip().lower() == key:
            return entry
    entry = {"key": key, "path": "", "loop": bool(loop)}
    manifest_sources.append(entry)
    return entry


def _resolve_targets(only: str) -> List[str]:
    keys = list(TARGET_QUERIES.keys())
    if not only:
        return keys
    requested = [part.strip().lower() for part in only.split(",") if part.strip()]
    return [k for k in keys if k in requested]


def fetch_targets(
    client: MixamoClient,
    character_id: str,
    targets: List[str],
    out_dir: Path,
    dry_run: bool,
    max_wait_sec: float,
    poll_sec: float,
    request_delay_sec: float = 1.2,
):
    fetched: Dict[str, str] = {}
    failed: Dict[str, str] = {}

    for idx, key in enumerate(targets):
        if idx > 0 and request_delay_sec > 0:
            time.sleep(float(request_delay_sec))
        queries = TARGET_QUERIES.get(key, [])
        print(f"[mixamo] target: {key}")
        selected_product = None
        selected_query = ""

        pinned_id = str(TARGET_PRODUCT_IDS.get(key, "")).strip()
        if pinned_id:
            selected_product = {"id": pinned_id, "name": "Pinned product"}
            selected_query = "pinned_id"
        else:
            for query in queries:
                try:
                    results = client.search_products(query)
                except Exception as exc:
                    print(f"  - search '{query}' failed: {exc}")
                    continue
                selected_product = _pick_best_product(results, query)
                if selected_product:
                    selected_query = query
                    break
                print(f"  - no results for '{query}'")

        if not selected_product:
            failed[key] = "no_product"
            continue

        product_id = str(selected_product.get("id", "")).strip()
        product_name = str(selected_product.get("name", "")).strip()
        if not product_id:
            failed[key] = "missing_product_id"
            continue

        print(f"  - selected: {product_name} ({product_id}) via '{selected_query}'")
        if dry_run:
            fetched[key] = ""
            continue

        details = None
        try:
            details = client.product_details(product_id, character_id)
        except Exception as exc:
            details = None
            print(f"  - details for selected product failed: {exc}")

        export_name = str((details or {}).get("name", "")).strip() or product_name
        export_type = str((details or {}).get("type", "")).strip() or "Motion"
        gms_hash = (details or {}).get("details", {}).get("gms_hash")
        if not isinstance(gms_hash, dict):
            # Pinned ID can be unavailable for account/character; fallback to search.
            fallback_product = None
            fallback_query = ""
            for query in queries:
                try:
                    results = client.search_products(query)
                except Exception as exc:
                    print(f"  - fallback search '{query}' failed: {exc}")
                    continue
                fallback_product = _pick_best_product(results, query)
                if fallback_product:
                    fallback_query = query
                    break

            if not fallback_product:
                failed[key] = "no_fallback_product"
                continue

            product_id = str(fallback_product.get("id", "")).strip()
            product_name = str(fallback_product.get("name", "")).strip()
            if not product_id:
                failed[key] = "missing_fallback_product_id"
                continue

            print(f"  - fallback selected: {product_name} ({product_id}) via '{fallback_query}'")
            try:
                details = client.product_details(product_id, character_id)
            except Exception as exc:
                failed[key] = f"fallback_details_failed:{exc}"
                continue

            export_name = str((details or {}).get("name", "")).strip() or product_name
            export_type = str((details or {}).get("type", "")).strip() or "Motion"
            gms_hash = (details or {}).get("details", {}).get("gms_hash")
            if not isinstance(gms_hash, dict):
                failed[key] = "missing_gms_hash"
                continue

        try:
            export_ticket = client.request_export(
                character_id=character_id,
                product_name=export_name,
                product_type=export_type,
                gms_hash=gms_hash,
            )
        except Exception as exc:
            failed[key] = f"export_failed:{exc}"
            continue
        if not isinstance(export_ticket, dict):
            failed[key] = "missing_export_ticket"
            continue

        download_url = str(export_ticket.get("download_url") or "").strip()
        job_ref = str(export_ticket.get("job_ref") or "").strip()
        if not download_url:
            if not job_ref:
                failed[key] = "missing_job_ref"
                continue
            try:
                download_url = client.wait_export_url(
                    character_id,
                    job_ref,
                    max_wait_sec=max_wait_sec,
                    poll_sec=poll_sec,
                ) or ""
            except Exception as exc:
                failed[key] = f"monitor_failed:{exc}"
                continue
            if not download_url:
                failed[key] = "export_timeout_or_failed"
                continue

        ext = _detect_extension(download_url)
        out_path = out_dir / f"{key}{ext}"
        try:
            client.download_file(download_url, out_path)
        except Exception as exc:
            failed[key] = f"download_failed:{exc}"
            continue

        rel = out_path.as_posix()
        fetched[key] = rel
        print(f"  - saved: {rel}")

    return fetched, failed


def patch_manifest(manifest_path: Path, updates: Dict[str, str], dry_run: bool):
    payload = _load_json(manifest_path)
    manifest = payload.get("manifest", {}) if isinstance(payload, dict) else {}
    if not isinstance(manifest, dict):
        raise ValueError("manifest section is missing or invalid in player_animations.json")
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise ValueError("manifest.sources is missing or invalid in player_animations.json")

    changed = 0
    for key, rel_path in updates.items():
        if not rel_path:
            continue
        entry = _ensure_manifest_entry(sources, key=key, loop=DEFAULT_LOOPS.get(key, False))
        old = str(entry.get("path", "")).strip().replace("\\", "/")
        new = rel_path.replace("\\", "/")
        if old != new:
            entry["path"] = new
            changed += 1

    if not dry_run and changed > 0:
        _save_json(manifest_path, payload)

    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download mount/riding animations from Mixamo.")
    parser.add_argument(
        "--token",
        default="",
        help="Mixamo bearer token. If omitted, --token-env is used.",
    )
    parser.add_argument(
        "--token-env",
        default="MIXAMO_ACCESS_TOKEN",
        help="Environment variable name for Mixamo bearer token.",
    )
    parser.add_argument(
        "--character-id",
        default=os.environ.get("MIXAMO_CHARACTER_ID", DEFAULT_CHARACTER_ID),
        help="Mixamo character id (defaults to XBot).",
    )
    parser.add_argument(
        "--manifest",
        default="data/actors/player_animations.json",
        help="Path to player animation manifest.",
    )
    parser.add_argument(
        "--out-dir",
        default="assets/anims",
        help="Output folder for downloaded clips.",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated subset of keys to fetch (e.g. mounting_horse,mounted_move_horse).",
    )
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=45.0,
        help="HTTP timeout for Mixamo requests.",
    )
    parser.add_argument(
        "--max-wait-sec",
        type=float,
        default=120.0,
        help="Maximum export wait time per clip.",
    )
    parser.add_argument(
        "--poll-sec",
        type=float,
        default=1.5,
        help="Polling interval for export monitor endpoint.",
    )
    parser.add_argument(
        "--request-delay-sec",
        type=float,
        default=1.2,
        help="Delay between target exports to reduce rate limiting.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Retry count for retryable HTTP statuses (429/5xx).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only resolve candidates, do not download or patch files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = str(args.token or "").strip()
    if not token:
        token = str(os.environ.get(str(args.token_env), "")).strip()
    if not token:
        print(
            f"[mixamo] token is missing. Set --token or environment variable {args.token_env}.",
            file=sys.stderr,
        )
        return 2

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"[mixamo] manifest not found: {manifest_path.as_posix()}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    targets = _resolve_targets(args.only)
    if not targets:
        print("[mixamo] no valid targets selected", file=sys.stderr)
        return 2

    client = MixamoClient(
        token=token,
        timeout_sec=args.timeout_sec,
        max_retries=args.max_retries,
    )

    print(f"[mixamo] character_id={args.character_id}")
    print(f"[mixamo] targets={len(targets)} dry_run={bool(args.dry_run)}")
    fetched, failed = fetch_targets(
        client=client,
        character_id=str(args.character_id).strip(),
        targets=targets,
        out_dir=out_dir,
        dry_run=bool(args.dry_run),
        max_wait_sec=float(args.max_wait_sec),
        poll_sec=float(args.poll_sec),
        request_delay_sec=float(args.request_delay_sec),
    )

    changed = 0
    if not args.dry_run:
        changed = patch_manifest(manifest_path, fetched, dry_run=False)

    print("")
    print("[mixamo] summary")
    print(f"  resolved: {len(fetched)}")
    if not args.dry_run:
        print(f"  manifest updates: {changed}")
    print(f"  failed: {len(failed)}")
    for key, reason in failed.items():
        print(f"    - {key}: {reason}")

    # Return non-zero only if nothing resolved.
    return 0 if fetched else 1


if __name__ == "__main__":
    raise SystemExit(main())
