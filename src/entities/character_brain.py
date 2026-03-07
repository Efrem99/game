"""CharacterBrain: context FSM + utility decisions + rule filtering + motion planning.

This module intentionally keeps large modes in FSM and delegates local action choice
to utility evaluators. It is designed to be extended without exploding transition count.
"""

import math
from typing import Dict, Tuple


_CONTEXTS = {
    "normal",
    "combat",
    "parkour",
    "airborne",
    "flight",
    "interaction",
    "injured",
    "stealth",
    "panic",
    "cinematic",
}


class CharacterBrain:
    def __init__(self, app, player):
        self.app = app
        self.player = player
        self.context_state = "normal"
        self.mental_state = "calm"

        self.mental = {
            "fear": 0.12,
            "confidence": 0.78,
            "perception_noise": 0.05,
            "risk_tolerance": 0.46,
            "reaction_speed": 1.0,
        }
        self.fatigue = 0.0
        self.injuries: Dict[str, Dict] = {}
        self.surface_memory: Dict[Tuple[int, int], Dict] = {}
        self.last_plan: Dict = {}

        self._cfg = self._load_config()
        defaults = self._cfg.get("mental_defaults", {}) if isinstance(self._cfg, dict) else {}
        if isinstance(defaults, dict):
            self.mental["fear"] = max(0.0, min(1.0, self._coerce_float(defaults.get("fear", self.mental["fear"]), self.mental["fear"])))
            self.mental["confidence"] = max(0.0, min(1.0, self._coerce_float(defaults.get("confidence", self.mental["confidence"]), self.mental["confidence"])))
            self.mental["perception_noise"] = max(0.0, min(1.0, self._coerce_float(defaults.get("perception_noise", self.mental["perception_noise"]), self.mental["perception_noise"])))
            self.mental["risk_tolerance"] = max(0.05, min(1.0, self._coerce_float(defaults.get("risk_tolerance", self.mental["risk_tolerance"]), self.mental["risk_tolerance"])))
            self.mental["reaction_speed"] = max(0.5, min(1.5, self._coerce_float(defaults.get("reaction_speed", self.mental["reaction_speed"]), self.mental["reaction_speed"])))
        self._regional_bias = self._cfg.get("regional_bias", {}) if isinstance(self._cfg, dict) else {}
        self._surface_risk = {
            "rock": 0.35,
            "sand": 0.24,
            "mud": 0.48,
            "debris": 0.56,
            "wood": 0.30,
            "ice": 0.72,
            "unknown": 0.62,
        }
        cfg_surface = self._cfg.get("surface_risk", {}) if isinstance(self._cfg, dict) else {}
        if isinstance(cfg_surface, dict):
            for key, value in cfg_surface.items():
                token = str(key or "").strip().lower()
                if not token:
                    continue
                self._surface_risk[token] = max(0.0, min(1.0, self._coerce_float(value, self._surface_risk.get(token, 0.5))))

    def _load_config(self):
        dm = getattr(self.app, "data_mgr", None)
        getter = getattr(dm, "get_character_logic_config", None)
        if callable(getter):
            try:
                payload = getter()
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass
        return {}

    def _coerce_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    def _cell_key(self, x, y):
        return int(round(float(x) / 6.0)), int(round(float(y) / 6.0))

    def register_injury(self, body_part, damage_type, severity=1.0):
        token = str(body_part or "").strip().lower()
        if not token:
            return
        self.injuries[token] = {
            "damage_type": str(damage_type or "bruise").strip().lower(),
            "severity": max(0.0, min(2.0, self._coerce_float(severity, 1.0))),
        }

    def clear_injury(self, body_part):
        token = str(body_part or "").strip().lower()
        self.injuries.pop(token, None)

    def _injury_modifiers(self):
        speed_penalty = 0.0
        balance_penalty = 0.0
        jump_penalty = 0.0
        reaction_penalty = 0.0
        pain = 0.0

        for key, row in self.injuries.items():
            if not isinstance(row, dict):
                continue
            sev = max(0.0, min(2.0, self._coerce_float(row.get("severity", 0.0), 0.0)))
            pain += sev * 0.12
            if any(tag in key for tag in ("thigh", "shin", "foot", "leg")):
                speed_penalty += sev * 0.16
                balance_penalty += sev * 0.22
                jump_penalty += sev * 0.26
            elif any(tag in key for tag in ("arm", "hand", "forearm")):
                reaction_penalty += sev * 0.10
            elif any(tag in key for tag in ("head", "neck")):
                reaction_penalty += sev * 0.20
                balance_penalty += sev * 0.12
            elif any(tag in key for tag in ("torso", "chest", "abdomen", "back")):
                speed_penalty += sev * 0.08
                reaction_penalty += sev * 0.06

        return {
            "speed_modifier": max(0.55, 1.0 - speed_penalty),
            "balance_modifier": max(0.35, 1.0 - balance_penalty),
            "jump_modifier": max(0.35, 1.0 - jump_penalty),
            "reaction_modifier": max(0.50, 1.0 - reaction_penalty),
            "pain_level": max(0.0, min(1.0, pain)),
        }

    def _location_fear_bias(self, location_name=""):
        world = getattr(self.app, "world", None)
        token = str(location_name or getattr(world, "active_location", "") or "").strip().lower()
        if not token:
            return 0.0, 0.0
        if isinstance(self._regional_bias, dict):
            for region_key, row in self._regional_bias.items():
                needle = str(region_key or "").strip().lower()
                if not needle or needle not in token or not isinstance(row, dict):
                    continue
                fear_add = max(0.0, min(1.0, self._coerce_float(row.get("fear_add", 0.0), 0.0)))
                conf_sub = max(0.0, min(1.0, self._coerce_float(row.get("confidence_sub", 0.0), 0.0)))
                return fear_add, conf_sub
        if ("krym" in token) or ("krimor" in token):
            return 0.24, 0.12
        return 0.0, 0.0

    def _surface_sample(self, x, y):
        world = getattr(self.app, "world", None)
        if not world:
            return "unknown", 0.6

        slope = 0.0
        if hasattr(world, "_th"):
            try:
                h = float(world._th(x, y))
                hx = float(world._th(x + 0.8, y))
                hy = float(world._th(x, y + 0.8))
                slope = min(1.0, math.sqrt(((hx - h) ** 2) + ((hy - h) ** 2)) / 0.75)
            except Exception:
                slope = 0.0

        if y <= -56.0:
            return "sand", min(1.0, 0.45 + (slope * 0.4))

        if hasattr(world, "_distance_to_river"):
            try:
                river_d = float(world._distance_to_river(x, y))
                if river_d <= 4.0:
                    return "mud", min(1.0, 0.52 + (slope * 0.35))
                if river_d <= 8.0:
                    return "sand", min(1.0, 0.38 + (slope * 0.3))
            except Exception:
                pass

        # Port/town wood estimate from coastal district.
        if -78.0 <= y <= -48.0 and -2.0 <= x <= 36.0:
            return "wood", min(1.0, 0.30 + (slope * 0.4))

        if slope >= 0.52:
            return "rock", min(1.0, 0.48 + (slope * 0.5))
        if slope >= 0.30:
            return "debris", min(1.0, 0.58 + (slope * 0.35))
        if slope >= 0.16:
            return "mud", min(1.0, 0.42 + (slope * 0.3))
        return "rock", min(1.0, 0.26 + (slope * 0.25))

    def _observe_surface(self, x, y, surface_hint=""):
        hint = str(surface_hint or "").strip().lower()
        if hint and hint in self._surface_risk:
            surface = hint
            risk = self._surface_risk.get(surface, self._surface_risk["unknown"])
        else:
            surface, risk = self._surface_sample(x, y)
        key = self._cell_key(x, y)
        row = self.surface_memory.get(key)
        if not isinstance(row, dict):
            row = {"surface": surface, "confidence": 0.18, "visits": 0}
        if row.get("surface") != surface:
            row["surface"] = surface
            row["confidence"] = min(0.42, self._coerce_float(row.get("confidence", 0.0), 0.0) * 0.5)
        row["visits"] = int(row.get("visits", 0) or 0) + 1
        # Sensor-tagged surfaces can be trusted more than procedural fallback samples.
        confidence_step = 0.12 if hint and hint in self._surface_risk else 0.09
        row["confidence"] = min(0.98, self._coerce_float(row.get("confidence", 0.0), 0.0) + confidence_step)
        self.surface_memory[key] = row
        return surface, max(0.0, min(1.0, risk)), float(row["confidence"])

    def _context_from_sensors(self, sensors):
        state_mgr = getattr(self.app, "state_mgr", None)
        game_state = str(getattr(getattr(state_mgr, "current_state", None), "name", "") or "").strip().lower()
        if game_state in {"dialog", "paused", "loading", "main_menu"}:
            return "cinematic"

        if bool(sensors.get("is_flying", False)):
            return "flight"
        if not bool(sensors.get("on_ground", True)):
            return "airborne"
        if bool(sensors.get("combat", False)):
            return "combat"
        if bool(sensors.get("parkour", False)):
            return "parkour"
        if bool(sensors.get("is_crouched", False)) or bool(sensors.get("stealth_context", False)):
            return "stealth"

        hp_ratio = self._coerce_float(sensors.get("hp_ratio", 1.0), 1.0)
        if hp_ratio <= 0.34:
            return "injured"
        if self.mental.get("fear", 0.0) >= 0.78:
            return "panic"
        return "normal"

    def _update_mental(self, context, surface_confidence, injury_mod, location_name=""):
        fear_bias, confidence_bias = self._location_fear_bias(location_name)
        fear = self.mental["fear"]
        confidence = self.mental["confidence"]

        fear = max(0.0, min(1.0, fear + (fear_bias * 0.03)))
        confidence = max(0.0, min(1.0, confidence - (confidence_bias * 0.03)))

        unknown_penalty = (1.0 - max(0.0, min(1.0, surface_confidence))) * 0.03
        fear = min(1.0, fear + unknown_penalty)
        confidence = max(0.0, confidence - (unknown_penalty * 0.9))

        pain = float(injury_mod.get("pain_level", 0.0))
        fear = min(1.0, fear + (pain * 0.08))
        confidence = max(0.0, confidence - (pain * 0.07))

        if context == "combat":
            confidence = min(1.0, confidence + 0.01)
        elif context == "stealth":
            fear = min(1.0, fear + 0.004)
            confidence = min(1.0, confidence + 0.004)
        if context == "panic":
            fear = min(1.0, fear + 0.02)

        risk_tol = max(0.05, min(1.0, 0.52 + ((confidence - fear) * 0.7)))
        reaction = max(0.55, min(1.25, float(injury_mod.get("reaction_modifier", 1.0)) * (1.0 - fear * 0.2 + confidence * 0.12)))

        self.mental["fear"] = fear
        self.mental["confidence"] = confidence
        self.mental["risk_tolerance"] = risk_tol
        self.mental["reaction_speed"] = reaction
        self.mental["perception_noise"] = max(0.0, min(1.0, 0.05 + fear * 0.24 + (1.0 - surface_confidence) * 0.16))

        if fear >= 0.80:
            self.mental_state = "panicked"
        elif fear >= 0.62:
            self.mental_state = "afraid"
        elif context == "combat":
            self.mental_state = "focused"
        elif confidence >= 0.72:
            self.mental_state = "determined"
        elif fear >= 0.38:
            self.mental_state = "tense"
        else:
            self.mental_state = "calm"

    def _select_turn(self, speed_norm, turn_norm, surface_risk, injury_mod):
        fear = self.mental.get("fear", 0.0)
        confidence = self.mental.get("confidence", 0.5)
        risk_tol = self.mental.get("risk_tolerance", 0.4)
        leg_penalty = max(0.0, 1.0 - float(injury_mod.get("jump_modifier", 1.0)))

        scores = {
            "arc_turn": (1.0 - turn_norm) * 0.78 + speed_norm * 0.32 - surface_risk * 0.36,
            "step_turn": 0.42 + turn_norm * 0.56 + fear * 0.20 - speed_norm * 0.14,
            "pivot_turn": turn_norm * 0.76 + speed_norm * 0.22 - surface_risk * 0.42 - fear * 0.10,
            "reverse_step": turn_norm * 0.90 + fear * 0.28 + (1.0 - confidence) * 0.20 + (1.0 - risk_tol) * 0.26,
            "hop_turn": speed_norm * 0.62 + confidence * 0.42 + risk_tol * 0.28 - surface_risk * 0.62 - fear * 0.42,
            "slide_turn": speed_norm * 0.54 + turn_norm * 0.32 - surface_risk * 0.52 - fear * 0.25,
        }

        # Rule filter: disallow risky airborne hop-turn when leg injuries or high fear are present.
        if leg_penalty >= 0.34 or fear >= 0.72:
            scores["hop_turn"] -= 1.0
        if surface_risk >= 0.62:
            scores["slide_turn"] -= 0.55
        if turn_norm <= 0.22:
            scores["reverse_step"] -= 0.40
            scores["pivot_turn"] -= 0.20

        choice = max(scores.items(), key=lambda pair: pair[1])[0]
        return choice, scores

    def _select_landing(self, impact_norm, surface_risk, injury_mod):
        fear = self.mental.get("fear", 0.0)
        confidence = self.mental.get("confidence", 0.5)
        balance_mod = float(injury_mod.get("balance_modifier", 1.0))

        scores = {
            "soft_land": (1.0 - impact_norm) * 0.88 + confidence * 0.22 - surface_risk * 0.16,
            "roll_land": impact_norm * 0.74 + confidence * 0.24 - surface_risk * 0.25,
            "stumble_land": impact_norm * 0.56 + fear * 0.32 + (1.0 - balance_mod) * 0.28,
            "collapse": impact_norm * 0.86 + (1.0 - balance_mod) * 0.50 + surface_risk * 0.30 + fear * 0.22,
        }
        scores["hard_land"] = impact_norm * 0.62 + surface_risk * 0.18 + fear * 0.10

        if impact_norm <= 0.28:
            scores["collapse"] -= 1.0
            scores["hard_land"] -= 0.55
        if balance_mod <= 0.62:
            scores["roll_land"] -= 0.35

        choice = max(scores.items(), key=lambda pair: pair[1])[0]
        return choice, scores

    def _select_balance_recovery(self, instability, surface_risk, injury_mod):
        fear = self.mental.get("fear", 0.0)
        balance_mod = float(injury_mod.get("balance_modifier", 1.0))

        scores = {
            "micro_balance": (1.0 - instability) * 0.88 + balance_mod * 0.24,
            "recovery_step": instability * 0.64 + (1.0 - balance_mod) * 0.20,
            "stumble": instability * 0.72 + surface_risk * 0.20 + fear * 0.18,
            "near_fall": instability * 0.86 + surface_risk * 0.30 + (1.0 - balance_mod) * 0.36,
            "fall": instability * 0.94 + surface_risk * 0.34 + (1.0 - balance_mod) * 0.44 + fear * 0.18,
        }

        if instability <= 0.18:
            scores["near_fall"] -= 0.80
            scores["fall"] -= 1.10
        if instability <= 0.30:
            scores["stumble"] -= 0.28

        choice = max(scores.items(), key=lambda pair: pair[1])[0]
        return choice, scores

    def evaluate(self, input_intent, sensors):
        if not isinstance(input_intent, dict):
            input_intent = {}
        if not isinstance(sensors, dict):
            sensors = {}

        x = self._coerce_float(sensors.get("x", 0.0), 0.0)
        y = self._coerce_float(sensors.get("y", 0.0), 0.0)
        speed = max(0.0, self._coerce_float(sensors.get("speed", 0.0), 0.0))
        turn_angle = abs(self._coerce_float(input_intent.get("turn_angle_deg", 0.0), 0.0))
        vertical_speed = abs(self._coerce_float(sensors.get("vertical_speed", 0.0), 0.0))
        fatigue = max(0.0, min(1.0, self._coerce_float(sensors.get("fatigue", self.fatigue), self.fatigue)))
        self.fatigue = fatigue

        injury_mod = self._injury_modifiers()
        surface_hint = str(sensors.get("surface_tag", sensors.get("surface", "")) or "").strip().lower()
        location_name = str(sensors.get("location_name", "") or "").strip()
        surface, sampled_risk, confidence = self._observe_surface(x, y, surface_hint=surface_hint)
        base_risk = self._surface_risk.get(surface, self._surface_risk["unknown"])
        surface_risk = max(sampled_risk, base_risk)
        surface_risk = max(0.0, min(1.0, surface_risk + ((1.0 - confidence) * 0.25)))

        self.context_state = self._context_from_sensors(sensors)
        if self.context_state not in _CONTEXTS:
            self.context_state = "normal"
        self._update_mental(self.context_state, confidence, injury_mod, location_name=location_name)

        speed_norm = max(0.0, min(1.0, speed / 10.5))
        turn_norm = max(0.0, min(1.0, turn_angle / 180.0))
        impact_norm = max(0.0, min(1.0, vertical_speed / 16.0))
        instability = max(0.0, min(1.0, (speed_norm * 0.4) + (surface_risk * 0.34) + ((1.0 - injury_mod["balance_modifier"]) * 0.42) + (fatigue * 0.28)))

        turn_choice, turn_scores = self._select_turn(speed_norm, turn_norm, surface_risk, injury_mod)
        landing_choice, landing_scores = self._select_landing(impact_norm, surface_risk, injury_mod)
        balance_choice, balance_scores = self._select_balance_recovery(instability, surface_risk, injury_mod)

        cautious_mult = 1.0 - (surface_risk * 0.20) - ((1.0 - confidence) * 0.16) - ((1.0 - self.mental["risk_tolerance"]) * 0.10)
        if self.context_state == "stealth":
            cautious_mult *= 0.74
        gait_speed_mult = max(0.58, min(1.08, cautious_mult * injury_mod["speed_modifier"]))

        plan = {
            "context_state": self.context_state,
            "mental_state": self.mental_state,
            "mental": dict(self.mental),
            "injury": dict(injury_mod),
            "environment": {
                "surface": surface,
                "surface_risk": surface_risk,
                "surface_confidence": confidence,
            },
            "utility": {
                "turn_choice": turn_choice,
                "turn_scores": turn_scores,
                "landing_choice": landing_choice,
                "landing_scores": landing_scores,
                "balance_choice": balance_choice,
                "balance_scores": balance_scores,
            },
            "motion_plan": {
                "turn_type": turn_choice,
                "landing_prep": landing_choice,
                "balance_correction": balance_choice,
                "gait_speed_mult": gait_speed_mult,
                "jump_modifier": injury_mod["jump_modifier"],
                "reaction_modifier": injury_mod["reaction_modifier"],
            },
        }
        self.last_plan = plan
        return plan

    def get_last_plan(self):
        return dict(self.last_plan) if isinstance(self.last_plan, dict) else {}
