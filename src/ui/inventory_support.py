"""Pure helpers shared by inventory UI and its tests."""


def _weapon_style_from_token(token):
    value = str(token or "").strip().lower()
    if not value:
        return "blade"
    if any(mark in value for mark in ("bow", "longbow", "shortbow")):
        return "bow"
    if any(mark in value for mark in ("staff", "wand", "orb", "focus", "tome")):
        return "magic"
    return "blade"


def _armor_style_from_token(token):
    value = str(token or "").strip().lower()
    if not value:
        return "medium"
    if any(mark in value for mark in ("royal", "plate", "heavy")):
        return "heavy"
    if any(mark in value for mark in ("leather", "light", "scout", "hunter")):
        return "light"
    return "medium"


def _offhand_style_from_token(token):
    value = str(token or "").strip().lower()
    if not value:
        return "ward"
    if "tower" in value:
        return "tower"
    if any(mark in value for mark in ("buckler", "round")):
        return "buckler"
    return "ward"


def _trinket_style_from_token(token):
    value = str(token or "").strip().lower()
    if not value:
        return "charm"
    if any(mark in value for mark in ("orb", "crystal", "focus")):
        return "orb"
    if any(mark in value for mark in ("seal", "relic", "sigil")):
        return "relic"
    return "charm"


def derive_inventory_character_visual_profile(equipped):
    payload = equipped if isinstance(equipped, dict) else {}
    chest = str(payload.get("chest", "") or "").strip().lower()
    offhand = str(payload.get("offhand", "") or "").strip().lower()
    trinket = str(payload.get("trinket", "") or "").strip().lower()
    weapon_main = str(payload.get("weapon_main", "") or "").strip().lower()

    armor_score = 0.16
    if chest:
        armor_score += 0.30
    if "chain" in chest:
        armor_score += 0.08
    if "royal" in chest:
        armor_score += 0.14
    if offhand:
        armor_score += 0.10
    armor_score = max(0.12, min(0.86, armor_score))

    trim_boost = 0.14
    if "royal" in chest:
        trim_boost += 0.18
    if offhand:
        trim_boost += 0.08
    if trinket:
        trim_boost += 0.06
    trim_boost = max(0.10, min(0.40, trim_boost))

    trim_alpha = max(0.52, min(0.98, 0.56 + trim_boost))
    royal_bonus = 0.10 if "royal" in chest else 0.0
    chain_bonus = 0.06 if "chain" in chest else 0.0
    trinket_bonus = 0.05 if trinket else 0.0
    shield_bonus = 0.05 if offhand else 0.0

    armor_tint = (
        max(0.22, min(0.95, 0.42 + (armor_score * 0.40) + royal_bonus)),
        max(0.20, min(0.92, 0.38 + (armor_score * 0.36) + chain_bonus + (royal_bonus * 0.60))),
        max(0.18, min(0.88, 0.34 + (armor_score * 0.30) + trinket_bonus + (royal_bonus * 0.35))),
        1.0,
    )
    armor_gloss = max(0.02, min(0.86, 0.05 + (armor_score * 0.64) + trinket_bonus + shield_bonus))

    if weapon_main:
        weapon_badge_color = (0.84, 0.62, 0.30, 1.0)
        if "bow" in weapon_main:
            weapon_badge_color = (0.58, 0.78, 0.44, 1.0)
        elif "staff" in weapon_main:
            weapon_badge_color = (0.52, 0.66, 0.90, 1.0)
        elif "sword" in weapon_main:
            weapon_badge_color = (0.88, 0.68, 0.36, 1.0)
    else:
        weapon_badge_color = (0.26, 0.27, 0.30, 0.90)

    if offhand:
        shield_badge_color = (0.76, 0.68, 0.54, 1.0)
        if "training" in offhand:
            shield_badge_color = (0.62, 0.76, 0.50, 1.0)
        elif "tower" in offhand:
            shield_badge_color = (0.72, 0.64, 0.84, 1.0)
    else:
        shield_badge_color = (0.25, 0.24, 0.28, 0.90)

    return {
        "weapon_token": weapon_main,
        "offhand_token": offhand,
        "chest_token": chest,
        "trinket_token": trinket,
        "weapon_style": _weapon_style_from_token(weapon_main),
        "armor_style": _armor_style_from_token(chest),
        "offhand_style": _offhand_style_from_token(offhand),
        "trinket_style": _trinket_style_from_token(trinket),
        "shield_visible": bool(offhand),
        "weapon_visible": bool(weapon_main),
        "trinket_visible": bool(trinket),
        "trim_alpha": float(trim_alpha),
        "armor_tint": tuple(float(v) for v in armor_tint),
        "armor_gloss": float(armor_gloss),
        "armor_score": float(armor_score),
        "weapon_badge_color": tuple(float(v) for v in weapon_badge_color),
        "shield_badge_color": tuple(float(v) for v in shield_badge_color),
    }


def build_skill_tree_layout(rows):
    entries = list(rows or [])
    branch_order = []
    grouped = {}
    for idx, raw in enumerate(entries):
        if not isinstance(raw, dict):
            continue
        branch = str(raw.get("branch_name", "") or "Skills").strip() or "Skills"
        if branch not in grouped:
            grouped[branch] = []
            branch_order.append(branch)
        row = dict(raw)
        row["_order"] = idx
        grouped[branch].append(row)

    branches = []
    for branch_name in branch_order:
        branch_rows = grouped.get(branch_name, [])
        by_id = {}
        for row in branch_rows:
            token = str(row.get("id", "") or "").strip().lower()
            if not token:
                continue
            row["id"] = token
            reqs = row.get("requires", [])
            if not isinstance(reqs, list):
                reqs = []
            row["requires"] = [str(req or "").strip().lower() for req in reqs if str(req or "").strip()]
            by_id[token] = row

        level_cache = {}
        visiting = set()

        def _level_for(node_id):
            token = str(node_id or "").strip().lower()
            if token in level_cache:
                return level_cache[token]
            if token in visiting:
                return 0
            visiting.add(token)
            node = by_id.get(token, {})
            parents = [req for req in node.get("requires", []) if req in by_id]
            if not parents:
                level = 0
            else:
                level = max(_level_for(req) + 1 for req in parents)
            visiting.discard(token)
            level_cache[token] = level
            return level

        nodes = []
        sorted_rows = sorted(
            by_id.values(),
            key=lambda row: (_level_for(row.get("id")), int(row.get("_order", 0)), str(row.get("name", ""))),
        )
        for lane, row in enumerate(sorted_rows):
            node = dict(row)
            node["level"] = _level_for(row.get("id"))
            node["lane"] = lane
            nodes.append(node)

        edges = []
        for node in nodes:
            child_id = str(node.get("id", "") or "")
            for req in node.get("requires", []):
                if req in by_id:
                    edges.append((req, child_id))

        branches.append(
            {
                "branch_name": branch_name,
                "nodes": nodes,
                "edges": edges,
                "max_level": max((int(node.get("level", 0)) for node in nodes), default=0),
                "max_lane": max((int(node.get("lane", 0)) for node in nodes), default=0),
            }
        )

    return {"branches": branches}
