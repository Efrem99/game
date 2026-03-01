import math
import os

from direct.gui.DirectGui import DirectFrame, OnscreenImage, OnscreenText
from panda3d.core import CardMaker, TextNode, TransparencyAttrib

from ui.design_system import THEME, body_font, title_font, place_ui_on_top


class HUDOverlay:
    def __init__(self, app):
        self.app = app
        self._logo_spin = 0.0
        self._autosave_on = False
        self._skill_labels = []
        self._active_skill_idx = 0
        self._ultimate_skill_idx = 0
        self._skill_wheel_visible = False
        self._skill_hover_idx = None
        self._skill_preview_idx = None
        self._skill_icon_cache = {}
        wheel_key = (
            self.app.data_mgr.get_binding("skill_wheel")
            or self.app.data_mgr.get_binding("attack_thrust")
            or "tab"
        )
        self._skill_wheel_hint_key = str(wheel_key).upper()
        self._xp = 0
        self._gold = 0
        self._checkpoint_pulse = 0.0
        self._xp_label_text = self.app.data_mgr.t("stats.xp", "XP")
        self._gold_label_text = self.app.data_mgr.t("stats.gold", "Gold")

        self.root = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-2, 2, -1, 1),
            parent=self.app.aspect2d,
        )
        place_ui_on_top(self.root, 80)

        self._create_vignette()
        self._create_bars()
        self._create_combo()
        self._create_checkpoint_tracker()
        self._create_damage_feed()
        self._create_profile_block()
        self._create_mount_hint()
        self._create_skill_wheel()
        self._create_autosave_badge()
        self._refresh_profile_text()

        self.root.hide()

    def _create_vignette(self):
        alpha = 0.20
        self.vig_top = DirectFrame(
            frameColor=(0, 0, 0, alpha),
            frameSize=(-2, 2, 0.76, 1.0),
            parent=self.root,
        )
        self.vig_bottom = DirectFrame(
            frameColor=(0, 0, 0, alpha),
            frameSize=(-2, 2, -1.0, -0.78),
            parent=self.root,
        )
        self.vig_left = DirectFrame(
            frameColor=(0, 0, 0, alpha * 0.85),
            frameSize=(-2, -1.55, -1.0, 1.0),
            parent=self.root,
        )
        self.vig_right = DirectFrame(
            frameColor=(0, 0, 0, alpha * 0.85),
            frameSize=(1.55, 2, -1.0, 1.0),
            parent=self.root,
        )
        for node in (self.vig_top, self.vig_bottom, self.vig_left, self.vig_right):
            place_ui_on_top(node, 80)

    def _create_bar(self, y, color):
        bg = DirectFrame(
            frameColor=(0.08, 0.08, 0.10, 0.88),
            frameSize=(0.0, 0.34, -0.013, 0.013),
            pos=(-1.32, 0, y),
            parent=self.root,
        )
        fill = DirectFrame(
            frameColor=color,
            frameSize=(0.0, 0.34, -0.011, 0.011),
            pos=(-1.32, 0, y),
            parent=self.root,
        )
        place_ui_on_top(bg, 82)
        place_ui_on_top(fill, 83)
        return bg, fill

    def _create_bars(self):
        b_font = body_font(self.app)
        self.hp_bg, self.hp_fill = self._create_bar(-0.84, (0.84, 0.20, 0.20, 0.95))
        self.sp_bg, self.sp_fill = self._create_bar(-0.89, (0.22, 0.76, 0.26, 0.95))
        self.mp_bg, self.mp_fill = self._create_bar(-0.94, (0.22, 0.42, 0.84, 0.95))

        self.hp_label = OnscreenText(
            text=self.app.data_mgr.t("stats.health", "Health"),
            pos=(-1.36, -0.83),
            scale=0.033,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ALeft,
            parent=self.root,
            mayChange=True,
            font=b_font,
        )
        self.sp_label = OnscreenText(
            text=self.app.data_mgr.t("stats.stamina", "Stamina"),
            pos=(-1.36, -0.88),
            scale=0.033,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ALeft,
            parent=self.root,
            mayChange=True,
            font=b_font,
        )
        self.mp_label = OnscreenText(
            text=self.app.data_mgr.t("stats.mana", "Mana"),
            pos=(-1.36, -0.93),
            scale=0.033,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ALeft,
            parent=self.root,
            mayChange=True,
            font=b_font,
        )
        for node in (self.hp_label, self.sp_label, self.mp_label):
            place_ui_on_top(node, 84)

    def _create_combo(self):
        self.combo_text = OnscreenText(
            text="",
            pos=(0, 0.84),
            scale=0.08,
            fg=THEME["gold_primary"],
            shadow=(0, 0, 0, 0.85),
            align=TextNode.ACenter,
            parent=self.root,
            mayChange=True,
            font=title_font(self.app),
        )
        place_ui_on_top(self.combo_text, 84)

        self.quest_header = OnscreenText(
            text=self.app.data_mgr.t("hud.active_quests", "ACTIVE QUESTS"),
            pos=(1.18, 0.72),
            scale=0.034,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.8),
            align=TextNode.ARight,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.quest_header, 84)

        self.quest_text = OnscreenText(
            text="",
            pos=(1.18, 0.64),
            scale=0.028,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ARight,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.quest_text, 84)

    def _create_checkpoint_tracker(self):
        self.checkpoint_text = OnscreenText(
            text="",
            pos=(1.18, 0.47),
            scale=0.028,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.82),
            align=TextNode.ARight,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.checkpoint_text, 84)

        self.checkpoint_hint_text = OnscreenText(
            text="",
            pos=(1.18, 0.42),
            scale=0.023,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.78),
            align=TextNode.ARight,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.checkpoint_hint_text, 84)

        self._checkpoint_marker_root = self.app.render.attachNewNode("hud_checkpoint_marker")
        cm = CardMaker("hud_checkpoint_marker_card")
        cm.setFrame(-0.38, 0.38, -0.10, 0.10)
        marker = self._checkpoint_marker_root.attachNewNode(cm.generate())
        marker.setBillboardPointEye()
        marker.setTransparency(TransparencyAttrib.MAlpha)
        marker.setLightOff(1)
        marker.setColorScale(1.0, 0.86, 0.24, 0.85)
        flare_path = "assets/textures/flare.png"
        if os.path.exists(flare_path):
            try:
                tex = self.app.loader.loadTexture(flare_path)
                if tex:
                    marker.setTexture(tex, 1)
            except Exception:
                pass
        self._checkpoint_marker = marker
        self._checkpoint_marker_root.hide()

    def _create_damage_feed(self):
        self.damage_text = OnscreenText(
            text="",
            pos=(0, 0.72),
            scale=0.05,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.85),
            align=TextNode.ACenter,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.damage_text, 84)

    def _damage_color(self, damage_type):
        t = str(damage_type or "").lower()
        if t == "fire":
            return (0.95, 0.46, 0.20, 1.0)
        if t == "lightning":
            return (0.75, 0.90, 1.00, 1.0)
        if t == "ice":
            return (0.55, 0.80, 1.00, 1.0)
        if t == "arcane":
            return (0.80, 0.55, 1.00, 1.0)
        if t == "holy":
            return (0.95, 0.90, 0.60, 1.0)
        if t == "physical":
            return (0.95, 0.82, 0.68, 1.0)
        return THEME["text_main"]

    def _create_profile_block(self):
        b_font = body_font(self.app)
        self.xp_text = OnscreenText(
            text="",
            pos=(-1.36, 0.90),
            scale=0.034,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ALeft,
            parent=self.root,
            mayChange=True,
            font=b_font,
        )
        self.gold_text = OnscreenText(
            text="",
            pos=(-1.36, 0.84),
            scale=0.034,
            fg=THEME["gold_primary"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ALeft,
            parent=self.root,
            mayChange=True,
            font=b_font,
        )
        place_ui_on_top(self.xp_text, 84)
        place_ui_on_top(self.gold_text, 84)

    def _create_mount_hint(self):
        self.mount_hint_text = OnscreenText(
            text="",
            pos=(0.0, -0.72),
            scale=0.038,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.82),
            align=TextNode.ACenter,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.mount_hint_text, 84)

    def _create_skill_wheel(self):
        self.skill_slots = []
        self.skill_slot_meta = []
        center_x = 0.0
        center_y = -0.18
        radius_x = 0.34
        radius_y = 0.22
        max_slots = 7

        self.skill_wheel_backdrop = DirectFrame(
            frameColor=(0.03, 0.03, 0.04, 0.68),
            frameSize=(-0.47, 0.47, -0.34, 0.34),
            pos=(center_x, 0, center_y),
            parent=self.root,
        )
        self.skill_wheel_center_ring = DirectFrame(
            frameColor=(0.12, 0.12, 0.14, 0.80),
            frameSize=(-0.12, 0.12, -0.12, 0.12),
            pos=(center_x, 0, center_y),
            parent=self.root,
        )
        place_ui_on_top(self.skill_wheel_backdrop, 84)
        place_ui_on_top(self.skill_wheel_center_ring, 85)

        flare_path = "assets/textures/flare.png"
        has_flare = os.path.exists(flare_path)
        icon_placeholder = "assets/textures/kw_logo.png"
        if not os.path.exists(icon_placeholder):
            icon_placeholder = flare_path if has_flare else ""

        for idx in range(max_slots):
            angle = math.radians(90.0 - (idx * (360.0 / max_slots)))
            sx = center_x + (math.cos(angle) * radius_x)
            sy = center_y + (math.sin(angle) * radius_y)

            ring = DirectFrame(
                frameColor=(0.10, 0.10, 0.12, 0.90),
                frameSize=(-0.095, 0.095, -0.095, 0.095),
                pos=(sx, 0, sy),
                parent=self.root,
            )
            plate = DirectFrame(
                frameColor=(0.08, 0.08, 0.10, 0.92),
                frameSize=(-0.076, 0.076, -0.076, 0.076),
                pos=(sx, 0, sy),
                parent=self.root,
            )
            glow = DirectFrame(
                frameColor=(1.0, 1.0, 1.0, 0.0),
                frameSize=(-0.105, 0.105, -0.105, 0.105),
                pos=(sx, 0, sy),
                parent=self.root,
            )
            icon_glow = None
            if has_flare:
                icon_glow = OnscreenImage(
                    image=flare_path,
                    pos=(sx, 0, sy + 0.004),
                    scale=0.056,
                    parent=self.root,
                )
                icon_glow.setTransparency(TransparencyAttrib.MAlpha)

            icon_image = OnscreenImage(
                image=icon_placeholder if icon_placeholder else flare_path,
                pos=(sx, 0, sy + 0.004),
                scale=0.045,
                parent=self.root,
            )
            icon_image.setTransparency(TransparencyAttrib.MAlpha)
            icon_text = OnscreenText(
                text="",
                pos=(sx, sy - 0.004),
                scale=0.044,
                fg=THEME["text_main"],
                shadow=(0, 0, 0, 0.86),
                align=TextNode.ACenter,
                parent=self.root,
                mayChange=True,
                font=title_font(self.app),
            )
            label = OnscreenText(
                text="",
                pos=(sx, sy - 0.076),
                scale=0.022,
                fg=THEME["text_muted"],
                shadow=(0, 0, 0, 0.75),
                align=TextNode.ACenter,
                parent=self.root,
                mayChange=True,
                font=body_font(self.app),
            )
            place_ui_on_top(ring, 86)
            place_ui_on_top(plate, 87)
            place_ui_on_top(glow, 88)
            if icon_glow:
                place_ui_on_top(icon_glow, 88)
            place_ui_on_top(icon_image, 89)
            place_ui_on_top(icon_text, 90)
            place_ui_on_top(label, 89)
            self.skill_slots.append(
                {
                    "ring": ring,
                    "plate": plate,
                    "glow": glow,
                    "flare": icon_glow,
                    "icon_image": icon_image,
                    "icon_text": icon_text,
                    "icon_path": None,
                    "label": label,
                }
            )
            self.skill_slot_meta.append({"x": sx, "y": sy, "r": 0.115})

        self.skill_center_text = OnscreenText(
            text="",
            pos=(center_x, center_y + 0.004),
            scale=0.040,
            fg=THEME["gold_primary"],
            shadow=(0, 0, 0, 0.82),
            align=TextNode.ACenter,
            parent=self.root,
            mayChange=True,
            font=title_font(self.app),
        )
        place_ui_on_top(self.skill_center_text, 90)

        self.skill_controls_text = OnscreenText(
            text="",
            pos=(center_x, center_y - 0.28),
            scale=0.027,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.72),
            align=TextNode.ACenter,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.skill_controls_text, 90)

    def set_skill_wheel_visible(self, visible, hovered_idx=None, preview_idx=None, hint_key=None):
        self._skill_wheel_visible = bool(visible)
        if isinstance(hovered_idx, int) and hovered_idx >= 0:
            self._skill_hover_idx = int(hovered_idx)
        else:
            self._skill_hover_idx = None
        if isinstance(preview_idx, int) and preview_idx >= 0:
            self._skill_preview_idx = int(preview_idx)
        else:
            self._skill_preview_idx = None
        if isinstance(hint_key, str) and hint_key.strip():
            self._skill_wheel_hint_key = hint_key.strip().upper()

    def _skill_style_for_spell(self, label):
        token = str(label or "").strip().lower()
        if "fire" in token or "meteor" in token:
            return "F", (0.95, 0.45, 0.20, 1.0)
        if "light" in token or "storm" in token:
            return "L", (0.72, 0.90, 1.00, 1.0)
        if "ice" in token or "frost" in token:
            return "I", (0.56, 0.82, 1.00, 1.0)
        if "heal" in token or "ward" in token or "holy" in token:
            return "H", (0.94, 0.92, 0.64, 1.0)
        if "arcane" in token or "nova" in token or "force" in token or "phase" in token:
            return "A", (0.84, 0.62, 1.00, 1.0)
        return "*", (0.80, 0.76, 0.66, 1.0)

    def _resolve_spell_icon_path(self, label):
        token = str(label or "").strip().lower()
        if not token:
            return None
        if token in self._skill_icon_cache:
            return self._skill_icon_cache[token]

        compact = "".join(ch for ch in token if ch.isalnum())
        underscored = "".join(ch if ch.isalnum() else "_" for ch in token).strip("_")
        candidates = [token, underscored, compact]

        if "fire" in compact:
            candidates += ["fireball", "fire"]
        if "light" in compact or "storm" in compact or "bolt" in compact:
            candidates += ["lightning", "lightningbolt"]
        if "ice" in compact or "frost" in compact:
            candidates += ["ice", "iceshards"]
        if "meteor" in compact:
            candidates += ["meteor"]
        if "ward" in compact or "heal" in compact or "holy" in compact:
            candidates += ["ward", "healing", "healingaura", "holy"]
        if "nova" in compact or "force" in compact or "arcane" in compact:
            candidates += ["nova", "arcane", "forcewave"]
        if "phase" in compact:
            candidates += ["phase"]

        tried = set()
        for key in candidates:
            norm = str(key).strip().lower()
            if not norm or norm in tried:
                continue
            tried.add(norm)
            path = f"assets/textures/skills/{norm}.png"
            if os.path.exists(path):
                self._skill_icon_cache[token] = path
                return path

        default_path = "assets/textures/skills/default.png"
        resolved = default_path if os.path.exists(default_path) else None
        self._skill_icon_cache[token] = resolved
        return resolved

    def pick_skill_slot(self, mouse_x, mouse_y):
        if not self._skill_wheel_visible or not self.skill_slot_meta:
            return None
        x = float(mouse_x) * float(self.app.getAspectRatio())
        y = float(mouse_y)
        best_idx = None
        best_dist = 999.0
        for idx, meta in enumerate(self.skill_slot_meta):
            dx = x - meta["x"]
            dy = y - meta["y"]
            dist = math.sqrt((dx * dx) + (dy * dy))
            if dist <= meta["r"] and dist < best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx

    def set_skill_wheel(self, spell_labels, active_idx=0, ultimate_idx=0):
        labels = list(spell_labels or [])
        self._skill_labels = labels
        self._active_skill_idx = int(active_idx or 0)
        self._ultimate_skill_idx = int(ultimate_idx or 0)

        max_slots = len(self.skill_slots)
        if max_slots <= 0:
            return

        if labels:
            self._active_skill_idx = max(0, min(self._active_skill_idx, len(labels) - 1))
            self._ultimate_skill_idx = max(0, min(self._ultimate_skill_idx, len(labels) - 1))
        else:
            self._active_skill_idx = 0
            self._ultimate_skill_idx = 0
            self._skill_preview_idx = None
            self._skill_hover_idx = None

        display_active_idx = self._active_skill_idx
        if (
            self._skill_wheel_visible
            and isinstance(self._skill_preview_idx, int)
            and 0 <= self._skill_preview_idx < len(labels)
        ):
            display_active_idx = int(self._skill_preview_idx)

        if not self._skill_wheel_visible:
            self.skill_wheel_backdrop.hide()
            self.skill_wheel_center_ring.hide()
            self.skill_center_text.hide()
            self.skill_controls_text.hide()
            for slot in self.skill_slots:
                slot["ring"].hide()
                slot["plate"].hide()
                slot["glow"].hide()
                if slot["flare"]:
                    slot["flare"].hide()
                slot["icon_image"].hide()
                slot["icon_text"].hide()
                slot["label"].hide()
            return

        self.skill_wheel_backdrop.show()
        self.skill_wheel_center_ring.show()
        self.skill_center_text.show()
        self.skill_controls_text.show()

        for idx, slot in enumerate(self.skill_slots):
            ring = slot["ring"]
            plate = slot["plate"]
            glow = slot["glow"]
            flare = slot["flare"]
            icon_image = slot["icon_image"]
            icon_text = slot["icon_text"]
            label = slot["label"]

            if idx >= len(labels):
                ring.hide()
                plate.hide()
                glow.hide()
                if flare:
                    flare.hide()
                icon_image.hide()
                icon_text.hide()
                label.hide()
                label.setText("")
                continue

            ring.show()
            plate.show()
            glow.show()
            icon_image.show()
            label.show()
            if flare:
                flare.show()

            raw = str(labels[idx])
            icon_char, tint = self._skill_style_for_spell(raw)
            icon_path = self._resolve_spell_icon_path(raw)
            last_icon_path = slot.get("icon_path")
            if icon_path:
                if icon_path != last_icon_path:
                    try:
                        icon_image.setImage(icon_path)
                        slot["icon_path"] = icon_path
                    except Exception:
                        slot["icon_path"] = None
                        icon_path = None
            if not icon_path:
                slot["icon_path"] = None
                icon_image.hide()
                icon_text.show()
                icon_text.setText(icon_char)
            else:
                icon_image.show()
                icon_text.hide()
            friendly = raw.replace("_", " ").strip()
            if len(friendly) > 16:
                friendly = f"{friendly[:15]}."
            label.setText(friendly.title() if friendly else "Unknown")

            is_hover = idx == self._skill_hover_idx
            is_active = idx == display_active_idx
            is_ult = idx == self._ultimate_skill_idx

            ring_color = (0.10, 0.10, 0.12, 0.92)
            plate_color = (tint[0] * 0.20, tint[1] * 0.20, tint[2] * 0.20, 0.92)
            glow_color = (tint[0], tint[1], tint[2], 0.0)
            icon_fg = (tint[0], tint[1], tint[2], 1.0)
            icon_img_scale = (1.0, 1.0, 1.0, 0.92)
            label_fg = THEME["text_muted"]

            if is_active and is_ult:
                ring_color = (0.72, 0.32, 0.18, 0.96)
                plate_color = (0.50, 0.25, 0.16, 0.95)
                glow_color = (1.0, 0.62, 0.28, 0.38)
                icon_fg = THEME["text_main"]
                icon_img_scale = (1.0, 0.95, 0.80, 1.0)
                label_fg = THEME["text_main"]
            elif is_hover:
                ring_color = (0.86, 0.72, 0.28, 0.98)
                plate_color = (0.42, 0.34, 0.14, 0.94)
                glow_color = (1.0, 0.86, 0.34, 0.55)
                icon_fg = THEME["text_main"]
                icon_img_scale = (1.08, 1.04, 0.86, 1.0)
                label_fg = THEME["gold_soft"]
            elif is_active:
                ring_color = (0.18, 0.42, 0.72, 0.96)
                plate_color = (0.12, 0.23, 0.36, 0.95)
                glow_color = (0.34, 0.64, 1.0, 0.30)
                icon_fg = THEME["text_main"]
                icon_img_scale = (0.90, 0.98, 1.08, 0.98)
                label_fg = THEME["text_main"]
            elif is_ult:
                ring_color = (0.56, 0.20, 0.18, 0.95)
                plate_color = (0.32, 0.14, 0.12, 0.95)
                glow_color = (0.96, 0.36, 0.26, 0.26)
                icon_img_scale = (1.06, 0.92, 0.84, 0.96)
                label_fg = THEME["gold_soft"]

            ring["frameColor"] = ring_color
            plate["frameColor"] = plate_color
            glow["frameColor"] = glow_color
            icon_text.setFg(icon_fg)
            icon_image.setColorScale(*icon_img_scale)
            label.setFg(label_fg)
            if flare:
                flare.setColorScale(tint[0], tint[1], tint[2], 0.42 if is_hover else 0.25)

        if labels:
            focus_idx = display_active_idx
            if (
                isinstance(self._skill_hover_idx, int)
                and 0 <= self._skill_hover_idx < len(labels)
            ):
                focus_idx = int(self._skill_hover_idx)

            focus_name = str(labels[focus_idx]).replace("_", " ").title()
            tags = []
            if focus_idx == display_active_idx:
                tags.append("Selected")
            if focus_idx == self._ultimate_skill_idx:
                tags.append("Ultimate")
            if self._skill_hover_idx is not None:
                tags.append(f"Release {self._skill_wheel_hint_key} to equip")
            postfix = f" | {' - '.join(tags)}" if tags else ""
            self.skill_center_text.setText(f"{focus_name}{postfix}")
        else:
            self.skill_center_text.setText("No learned skills")

        self.skill_controls_text.setText(
            f"Hold {self._skill_wheel_hint_key}: Skill Wheel  |  LMB: Cast  |  F: Ultimate"
        )

    def _create_autosave_badge(self):
        logo_path = "assets/textures/kw_logo.png"
        self.autosave_logo = None
        if os.path.exists(logo_path):
            self.autosave_logo = OnscreenImage(
                image=logo_path,
                pos=(1.18, 0, 0.88),
                scale=0.06,
                parent=self.root,
            )
            self.autosave_logo.setTransparency(TransparencyAttrib.MAlpha)
            self.autosave_logo.hide()
            place_ui_on_top(self.autosave_logo, 84)

        self.autosave_text = OnscreenText(
            text="",
            pos=(1.02, 0.86),
            scale=0.03,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.8),
            align=TextNode.ARight,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.autosave_text, 84)

    def show(self):
        self.root.show()

    def hide(self):
        self.root.hide()
        self._checkpoint_marker_root.hide()

    def refresh_locale(self):
        self.hp_label.setText(self.app.data_mgr.t("stats.health", "Health"))
        self.sp_label.setText(self.app.data_mgr.t("stats.stamina", "Stamina"))
        self.mp_label.setText(self.app.data_mgr.t("stats.mana", "Mana"))
        self.quest_header.setText(self.app.data_mgr.t("hud.active_quests", "ACTIVE QUESTS"))
        self._xp_label_text = self.app.data_mgr.t("stats.xp", "XP")
        self._gold_label_text = self.app.data_mgr.t("stats.gold", "Gold")
        self._refresh_profile_text()
        if self._autosave_on:
            self.autosave_text.setText(self.app.data_mgr.t("ui.autosaving", "Autosaving..."))

    def set_autosave(self, active):
        self._autosave_on = bool(active)
        if self.autosave_logo:
            if self._autosave_on:
                self.autosave_logo.show()
            else:
                self.autosave_logo.hide()
        self.autosave_text.setText(
            self.app.data_mgr.t("ui.autosaving", "Autosaving...") if self._autosave_on else ""
        )

    def _set_fill(self, fill, pct):
        width = 0.34 * max(0.0, min(1.0, pct))
        fill["frameSize"] = (0.0, width, -0.011, 0.011)

    def _refresh_profile_text(self):
        self.xp_text.setText(f"{self._xp_label_text}: {self._xp}")
        self.gold_text.setText(f"{self._gold_label_text}: {self._gold}")

    def _format_dist(self, value):
        if value is None:
            return "--"
        try:
            meters = max(0.0, float(value))
        except Exception:
            return "--"
        if meters >= 1000.0:
            return f"{meters / 1000.0:.1f} km"
        return f"{int(round(meters))} m"

    def _update_checkpoint_tracker(self, dt, quest_data):
        tracked = None
        if isinstance(quest_data, list):
            for item in quest_data:
                if not isinstance(item, dict):
                    continue
                target = item.get("target")
                if isinstance(target, (list, tuple)) and len(target) >= 3:
                    tracked = item
                    break

        if not tracked:
            self.checkpoint_text.setText("")
            self.checkpoint_hint_text.setText("")
            self._checkpoint_marker_root.hide()
            return

        objective = str(tracked.get("objective", "") or "Objective").strip()
        status = str(tracked.get("status", "Reach") or "Reach").strip()
        if status.lower() == "reach":
            status = self.app.data_mgr.t("hud.reach", "Reach")
        elif status.lower() == "interact":
            status = self.app.data_mgr.t("hud.interact", "Interact")
        dist_txt = self._format_dist(tracked.get("distance"))
        cp_title = self.app.data_mgr.t("hud.checkpoint", "Checkpoint")
        self.checkpoint_text.setText(f"{cp_title}: {dist_txt}")
        self.checkpoint_hint_text.setText(f"{status}: {objective}")

        target = tracked.get("target")
        if not (isinstance(target, (list, tuple)) and len(target) >= 3):
            self._checkpoint_marker_root.hide()
            return

        try:
            tx = float(target[0])
            ty = float(target[1])
            tz = float(target[2])
        except Exception:
            self._checkpoint_marker_root.hide()
            return

        self._checkpoint_pulse += max(0.0, float(dt)) * 5.0
        pulse = 1.0 + (0.12 * math.sin(self._checkpoint_pulse))
        self._checkpoint_marker_root.show()
        self._checkpoint_marker_root.setPos(tx, ty, tz + 2.2 + (0.12 * pulse))
        self._checkpoint_marker_root.setScale(0.95 * pulse)

    def update(
        self,
        dt,
        char_state,
        quest_data=None,
        profile=None,
        mount_hint=None,
        combat_event=None,
        spell_labels=None,
        active_skill_idx=0,
        ultimate_skill_idx=0,
    ):
        if not isinstance(profile, dict):
            profile = getattr(self.app, "profile", {})
        if isinstance(profile, dict):
            try:
                xp = int(profile.get("xp", 0) or 0)
            except Exception:
                xp = 0
            try:
                gold = int(profile.get("gold", 0) or 0)
            except Exception:
                gold = 0
            if xp != self._xp or gold != self._gold:
                self._xp = xp
                self._gold = gold
                self._refresh_profile_text()

        self.set_skill_wheel(spell_labels or [], active_skill_idx, ultimate_skill_idx)

        if not char_state:
            if self._autosave_on and self.autosave_logo:
                self._logo_spin = (self._logo_spin + dt * 100.0) % 360.0
                self.autosave_logo.setR(self._logo_spin)
            self.damage_text.setText("")
            self.checkpoint_text.setText("")
            self.checkpoint_hint_text.setText("")
            self._checkpoint_marker_root.hide()
            return
        self._set_fill(self.hp_fill, char_state.health / max(1.0, char_state.maxHealth))
        self._set_fill(self.sp_fill, char_state.stamina / max(1.0, char_state.maxStamina))
        self._set_fill(self.mp_fill, char_state.mana / max(1.0, char_state.maxMana))

        combo_count = int(getattr(char_state, "comboCount", 0))
        if combo_count > 1:
            label = self.app.data_mgr.t("ui.combo", "COMBO")
            self.combo_text.setText(f"{label} x{combo_count}")
        else:
            self.combo_text.setText("")

        if quest_data:
            lines = []
            for idx, entry in enumerate(quest_data[:3]):
                if not isinstance(entry, dict):
                    continue
                title = str(entry.get("title", "")).strip()
                objective = str(entry.get("objective", "")).strip()
                status = str(entry.get("status", "")).strip() or "Objective"
                dist_txt = self._format_dist(entry.get("distance"))
                if title and objective:
                    prefix = "●" if idx == 0 else "•"
                    lines.append(f"{prefix} {title}")
                    lines.append(f"  {status}: {objective} ({dist_txt})")
                elif title:
                    lines.append(title)
            self.quest_text.setText("\n".join(lines))
        else:
            self.quest_text.setText("")
        self._update_checkpoint_tracker(dt, quest_data or [])

        if isinstance(mount_hint, str):
            self.mount_hint_text.setText(mount_hint)
        else:
            self.mount_hint_text.setText("")

        if isinstance(combat_event, dict):
            amount = int(combat_event.get("amount", 0) or 0)
            dmg_type = str(combat_event.get("type", "physical") or "physical")
            label = str(combat_event.get("label", "") or "").strip()
            prefix = label if label else dmg_type.upper()
            self.damage_text.setText(f"{prefix}: {amount}")
            self.damage_text["fg"] = self._damage_color(dmg_type)
        else:
            self.damage_text.setText("")

        if self._autosave_on and self.autosave_logo:
            self._logo_spin = (self._logo_spin + dt * 100.0) % 360.0
            self.autosave_logo.setR(self._logo_spin)
