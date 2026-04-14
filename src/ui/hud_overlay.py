import math
import os

from direct.gui.DirectGui import DirectFrame, OnscreenImage, OnscreenText
from panda3d.core import (
    CardMaker,
    LineSegs,
    NodePath,
    PNMImage,
    Point3,
    TextNode,
    Texture,
    TransparencyAttrib,
    Vec4,
)

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
        wheel_key = self.app.data_mgr.get_binding("skill_wheel") or "tab"
        self._skill_wheel_hint_key = str(wheel_key).upper()
        lock_key = self.app.data_mgr.get_binding("target_lock") or "t"
        self._target_lock_hint_key = str(lock_key).upper()
        interact_key = self.app.data_mgr.get_binding("interact") or "f"
        self._interact_hint_key = str(interact_key).upper()
        self._attack_hint_key = "LMB"
        self._cast_hint_key = "wheel slot"
        self._refresh_control_hint_tokens()
        self._xp = 0
        self._gold = 0
        self._checkpoint_pulse = 0.0
        self._breadcrumb_pulse = 0.0
        self._breadcrumb_nodes = []
        self._breadcrumb_max = 16
        self._minimap_range = 120.0
        self._xp_label_text = self.app.data_mgr.t("stats.xp", "XP")
        self._gold_label_text = self.app.data_mgr.t("stats.gold", "Gold")
        self._npc_scene_debug_entries = []
        npc_cfg = {}
        dm = getattr(self.app, "data_mgr", None)
        if dm and isinstance(getattr(dm, "sound_config", None), dict):
            npc_cfg = dm.sound_config.get("npc_activity", {}) if isinstance(dm.sound_config.get("npc_activity"), dict) else {}
        self._npc_scene_debug_enabled = bool(npc_cfg.get("debug_overlay", True))
        try:
            self._npc_scene_debug_max = max(1, int(npc_cfg.get("debug_lines", 5) or 5))
        except Exception:
            self._npc_scene_debug_max = 5
        self._npc_scene_debug_ttl = 9.0
        self._bar_values = {
            "hp": 1.0,
            "stamina": 1.0,
            "mana": 1.0,
        }
        self._bar_seeded = False
        self._reticle_pulse = 0.0
        self._hp_ring_segments = []
        self._stamina_ring_segments = []
        self._mana_ring_segments = []
        self._ring_style = {
            "hp": {
                "active": (0.92, 0.30, 0.30, 0.96),
                "inactive": (0.20, 0.08, 0.08, 0.36),
            },
            "stamina": {
                "active": (0.36, 0.86, 0.40, 0.95),
                "inactive": (0.08, 0.20, 0.09, 0.34),
            },
            "mana": {
                "active": (0.38, 0.58, 0.98, 0.96),
                "inactive": (0.08, 0.13, 0.24, 0.34),
            },
        }

        self.root = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-2, 2, -1, 1),
            parent=self.app.aspect2d,
        )
        place_ui_on_top(self.root, 80)

        self._create_vignette()
        self._create_screen_postfx()
        self._create_bars()
        self._create_combo()
        self._create_checkpoint_tracker()
        self._create_minimap()
        self._create_damage_feed()
        self._create_profile_block()
        self._create_targeting_reticle()
        self._create_boss_health_bar()
        self._create_tutorial_hint()
        self._create_mount_hint()
        self._create_stealth_hint()
        self._create_skill_wheel()
        self._create_autosave_badge()
        self._create_npc_scene_debug()
        self._create_video_bot_debug()
        self._create_respawn_notification()
        self._refresh_profile_text()

        # Weather & Extra FX
        self._flash_color = [1.0, 1.0, 1.0, 0.0]
        self._cursed_blend = 0.0
        self._cursed_color = [0.8, 0.1, 0.0, 0.0] # Reddish but dark
        self._flash_timer = 0.0
        self._flash_total = 0.1


        self.root.hide()

    def _create_vignette(self):
        # Keep vignette subtle; strong edges looked like a giant UI rectangle in gameplay.
        alpha = 0.055
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
            frameColor=(0, 0, 0, alpha * 0.55),
            frameSize=(-2, -1.55, -1.0, 1.0),
            parent=self.root,
        )
        self.vig_right = DirectFrame(
            frameColor=(0, 0, 0, alpha * 0.55),
            frameSize=(1.55, 2, -1.0, 1.0),
            parent=self.root,
        )
        for node in (self.vig_top, self.vig_bottom, self.vig_left, self.vig_right):
            place_ui_on_top(node, 80)

    def _create_screen_postfx(self):
        self.postfx_pulse = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-2, 2, -1, 1),
            parent=self.root,
        )
        self.postfx_flash = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-2, 2, -1, 1),
            parent=self.root,
        )
        place_ui_on_top(self.postfx_pulse, 81)
        place_ui_on_top(self.postfx_flash, 82)

    def _resolve_screen_postfx_layers(
        self,
        *,
        boost=0.0,
        fear=0.0,
        damage=0.0,
        combat_heat=0.0,
        damage_type="",
        damage_intensity=0.0,
    ):
        b = max(0.0, min(1.0, float(boost or 0.0)))
        fear = max(0.0, min(1.0, float(fear or 0.0)))
        damage = max(0.0, min(1.0, float(damage or 0.0)))
        heat = max(0.0, min(1.0, float(combat_heat or 0.0)))
        dint = max(0.0, min(1.0, float(damage_intensity or 0.0)))
        dcol = self._damage_color(damage_type)

        flash_alpha = min(0.44, 0.015 + (0.26 * dint) + (0.08 * damage) + (0.04 * heat))
        flash_mix = 0.22 + (0.56 * max(dint, damage * 0.7))
        flash = (
            min(1.0, (dcol[0] * flash_mix) + (0.06 * heat) + self._flash_color[0] * self._flash_color[3]),
            min(1.0, (dcol[1] * flash_mix * 0.92) + (0.02 * fear) + self._flash_color[1] * self._flash_color[3]),
            min(1.0, (dcol[2] * flash_mix * 0.84) + (0.04 * fear) + self._flash_color[2] * self._flash_color[3]),
            max(flash_alpha, self._flash_color[3]),
        )

        pulse_alpha = min(0.38, 0.01 + (0.12 * heat) + (0.05 * b) + (0.035 * fear) + (0.18 * self._cursed_blend))
        pulse = (
            min(1.0, 0.10 + (0.36 * heat) + (0.05 * damage) + (self._cursed_color[0] * self._cursed_blend)),
            min(1.0, 0.05 + (0.18 * heat) + (0.05 * fear) + (self._cursed_color[1] * self._cursed_blend)),
            min(1.0, 0.06 + (0.10 * fear) + (0.02 * damage) + (self._cursed_color[2] * self._cursed_blend)),
            pulse_alpha,
        )
        return {"flash": flash, "pulse": pulse}

    def _apply_screen_postfx(
        self,
        *,
        boost=0.0,
        fear=0.0,
        damage=0.0,
        combat_heat=0.0,
        damage_type="",
        damage_intensity=0.0,
    ):
        layers = self._resolve_screen_postfx_layers(
            boost=boost,
            fear=fear,
            damage=damage,
            combat_heat=combat_heat,
            damage_type=damage_type,
            damage_intensity=damage_intensity,
        )
        self.postfx_flash["frameColor"] = layers["flash"]
        self.postfx_pulse["frameColor"] = layers["pulse"]

    def _apply_context_vignette(self, boost=0.0, fear=0.0, damage=0.0, damage_type="", damage_intensity=0.0):
        b = max(0.0, min(1.0, float(boost or 0.0)))
        fear = max(0.0, min(1.0, float(fear or 0.0)))
        damage = max(0.0, min(1.0, float(damage or 0.0)))
        dtype = str(damage_type or "").strip().lower()
        dint = max(0.0, min(1.0, float(damage_intensity or 0.0)))
        top_alpha = 0.055 + (0.10 * b) + (0.05 * damage)
        side_alpha = 0.03 + (0.06 * b) + (0.03 * fear)
        if dint > 0.0:
            top_alpha += 0.16 * dint
            side_alpha += 0.10 * dint
        damage_tint = 0.18 * damage
        fear_tint = 0.10 * fear

        if dint > 0.01:
            dcol = self._damage_color(dtype)
            tint = min(0.44, (0.12 + (0.30 * dint)))
            ch_r = min(1.0, (dcol[0] * tint) + (damage_tint * 0.35))
            ch_g = min(1.0, dcol[1] * tint * 0.74)
            ch_b = min(1.0, (dcol[2] * tint * 0.62) + fear_tint)
        else:
            ch_r = damage_tint
            ch_g = 0.0
            ch_b = fear_tint

        # Apply cursed blend to vignette colors
        ch_r = min(1.0, ch_r + (self._cursed_color[0] * self._cursed_blend))
        ch_g = min(1.0, ch_g + (self._cursed_color[1] * self._cursed_blend))
        ch_b = min(1.0, ch_b + (self._cursed_color[2] * self._cursed_blend))
        top_alpha = min(0.90, top_alpha + (0.15 * self._cursed_blend))
        side_alpha = min(0.82, side_alpha + (0.10 * self._cursed_blend))

        self.vig_top["frameColor"] = (ch_r, ch_g, ch_b, top_alpha)
        self.vig_bottom["frameColor"] = (ch_r, ch_g, ch_b, top_alpha)
        self.vig_left["frameColor"] = (ch_r, ch_g, ch_b, side_alpha)
        self.vig_right["frameColor"] = (ch_r, ch_g, ch_b, side_alpha)

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
        self.hp_value = OnscreenText(
            text="",
            pos=(-0.95, -0.83),
            scale=0.027,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.72),
            align=TextNode.ARight,
            parent=self.root,
            mayChange=True,
            font=b_font,
        )
        self.sp_value = OnscreenText(
            text="",
            pos=(-0.95, -0.88),
            scale=0.027,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.72),
            align=TextNode.ARight,
            parent=self.root,
            mayChange=True,
            font=b_font,
        )
        self.mp_value = OnscreenText(
            text="",
            pos=(-0.95, -0.93),
            scale=0.027,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.72),
            align=TextNode.ARight,
            parent=self.root,
            mayChange=True,
            font=b_font,
        )
        for node in (
            self.hp_label,
            self.sp_label,
            self.mp_label,
            self.hp_value,
            self.sp_value,
            self.mp_value,
        ):
            place_ui_on_top(node, 84)

        # Legacy linear bars are kept for compatibility, but hidden in current radial HUD layout.
        for node in (self.hp_bg, self.sp_bg, self.mp_bg, self.hp_fill, self.sp_fill, self.mp_fill):
            node.hide()
        for node in (self.hp_label, self.sp_label, self.mp_label):
            node.hide()

        self.hp_value.setPos(-1.18, -0.72)
        self.sp_value.setPos(-1.32, -0.87)
        self.mp_value.setPos(-1.04, -0.87)
        self.hp_value.setFg((0.95, 0.82, 0.82, 0.95))
        self.sp_value.setFg((0.82, 0.95, 0.84, 0.95))
        self.mp_value.setFg((0.82, 0.88, 0.98, 0.95))
        self._create_vitals_orb()

    def _build_circle_texture(
        self,
        tex_name,
        *,
        size=128,
        inner=0.0,
        outer=1.0,
        rgb=(1.0, 1.0, 1.0),
        alpha=1.0,
        feather=0.02,
    ):
        img = PNMImage(size, size, 4)
        cx = (size - 1) * 0.5
        cy = (size - 1) * 0.5
        inv = 1.0 / max(1.0, float(cx))
        inner = max(0.0, min(1.0, float(inner)))
        outer = max(inner, min(1.0, float(outer)))
        feather = max(0.0001, float(feather))
        r0 = max(0.0, outer - feather)
        r1 = min(1.0, outer + feather)
        i0 = max(0.0, inner - feather)
        i1 = min(1.0, inner + feather)

        for py in range(size):
            for px in range(size):
                dx = (float(px) - cx) * inv
                dy = (float(py) - cy) * inv
                dist = math.sqrt((dx * dx) + (dy * dy))
                if dist < inner or dist > outer:
                    a = 0.0
                else:
                    a = float(alpha)
                    if dist > r0:
                        edge = max(0.0, min(1.0, (r1 - dist) / max(1e-6, (r1 - r0))))
                        a *= edge
                    if dist < i1:
                        edge = max(0.0, min(1.0, (dist - i0) / max(1e-6, (i1 - i0))))
                        a *= edge
                img.setXelA(px, py, float(rgb[0]), float(rgb[1]), float(rgb[2]), a)

        tex = Texture(tex_name)
        tex.load(img)
        tex.setMinfilter(Texture.FTLinearMipmapLinear)
        tex.setMagfilter(Texture.FTLinear)
        return tex

    def _create_ring_segments(self, parent, radius, thickness, *, segments=56, color=(1.0, 1.0, 1.0, 1.0)):
        out = []
        seg_count = max(12, int(segments))
        arc_step = (math.pi * 2.0) / float(seg_count)
        seg_len = max(0.003, ((2.0 * math.pi * float(radius)) / float(seg_count)) * 0.88)
        for idx in range(seg_count):
            angle = (math.pi * 0.5) - (float(idx) * arc_step)
            x = math.cos(angle) * float(radius)
            z = math.sin(angle) * float(radius)
            seg = DirectFrame(
                frameColor=color,
                frameSize=(-seg_len * 0.5, seg_len * 0.5, -thickness * 0.5, thickness * 0.5),
                pos=(x, 0, z),
                parent=parent,
            )
            seg.setR((-math.degrees(angle)) + 90.0)
            place_ui_on_top(seg, 84)
            out.append(seg)
        return out

    def _set_ring_fill(self, segments, pct, active_color, inactive_color):
        if not segments:
            return
        pct = max(0.0, min(1.0, float(pct or 0.0)))
        total = len(segments)
        exact = pct * float(total)
        full = int(math.floor(exact))
        partial = exact - float(full)
        for idx, node in enumerate(segments):
            if idx < full:
                node["frameColor"] = active_color
            elif idx == full and partial > 0.0 and full < total:
                node["frameColor"] = (
                    inactive_color[0] + ((active_color[0] - inactive_color[0]) * partial),
                    inactive_color[1] + ((active_color[1] - inactive_color[1]) * partial),
                    inactive_color[2] + ((active_color[2] - inactive_color[2]) * partial),
                    inactive_color[3] + ((active_color[3] - inactive_color[3]) * partial),
                )
            else:
                node["frameColor"] = inactive_color

    def _create_vitals_orb(self):
        self.vitals_root = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-0.24, 0.24, -0.24, 0.24),
            pos=(-1.18, 0, -0.86),
            parent=self.root,
        )
        place_ui_on_top(self.vitals_root, 84)

        avatar_ring_tex = self._build_circle_texture(
            "hud_avatar_ring",
            size=128,
            inner=0.82,
            outer=1.0,
            rgb=(0.90, 0.78, 0.42),
            alpha=0.95,
            feather=0.04,
        )
        avatar_disc_tex = self._build_circle_texture(
            "hud_avatar_disc",
            size=128,
            inner=0.0,
            outer=1.0,
            rgb=(0.09, 0.09, 0.12),
            alpha=0.90,
            feather=0.02,
        )
        avatar_core_tex = self._build_circle_texture(
            "hud_avatar_core",
            size=128,
            inner=0.0,
            outer=1.0,
            rgb=(0.20, 0.18, 0.15),
            alpha=0.65,
            feather=0.05,
        )
        self.avatar_disc = OnscreenImage(image=avatar_disc_tex, pos=(0, 0, 0), scale=0.084, parent=self.vitals_root)
        self.avatar_core = OnscreenImage(image=avatar_core_tex, pos=(0, 0, 0), scale=0.074, parent=self.vitals_root)
        self.avatar_ring = OnscreenImage(image=avatar_ring_tex, pos=(0, 0, 0), scale=0.090, parent=self.vitals_root)
        self.avatar_monogram = OnscreenText(
            text="SW",
            pos=(0.0, -0.018),
            scale=0.045,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.78),
            align=TextNode.ACenter,
            parent=self.vitals_root,
            mayChange=False,
            font=title_font(self.app),
        )
        for node in (self.avatar_disc, self.avatar_core, self.avatar_ring, self.avatar_monogram):
            place_ui_on_top(node, 85)

        self._hp_ring_segments = self._create_ring_segments(
            self.vitals_root,
            radius=0.126,
            thickness=0.010,
            segments=58,
            color=self._ring_style["hp"]["inactive"],
        )
        self._stamina_ring_segments = self._create_ring_segments(
            self.vitals_root,
            radius=0.109,
            thickness=0.009,
            segments=54,
            color=self._ring_style["stamina"]["inactive"],
        )
        self._mana_ring_segments = self._create_ring_segments(
            self.vitals_root,
            radius=0.092,
            thickness=0.008,
            segments=50,
            color=self._ring_style["mana"]["inactive"],
        )

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
        self.combo_text.hide()
        self._combo_banner_t = 0.0

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

        self._breadcrumb_root = self.app.render.attachNewNode("hud_breadcrumbs")
        step_card = CardMaker("hud_breadcrumb_step")
        step_card.setFrame(-0.10, 0.10, -0.03, 0.03)
        for idx in range(self._breadcrumb_max):
            node = self._breadcrumb_root.attachNewNode(step_card.generate())
            node.setBillboardPointEye()
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setLightOff(1)
            alpha = max(0.18, 0.72 - (idx * 0.03))
            node.setColorScale(1.0, 0.78, 0.24, alpha)
            node.hide()
            self._breadcrumb_nodes.append(node)
        self._breadcrumb_root.hide()

    def _create_minimap(self):
        self.minimap_frame = DirectFrame(
            frameColor=(0.03, 0.03, 0.04, 0.72),
            frameSize=(-0.195, 0.195, -0.195, 0.195),
            pos=(1.16, 0, -0.62),
            parent=self.root,
        )
        place_ui_on_top(self.minimap_frame, 84)

        self.minimap_border = DirectFrame(
            frameColor=(0.72, 0.62, 0.32, 0.66),
            frameSize=(-0.172, 0.172, -0.172, 0.172),
            parent=self.minimap_frame,
        )
        self.minimap_inner = DirectFrame(
            frameColor=(0.10, 0.11, 0.13, 0.78),
            frameSize=(-0.166, 0.166, -0.166, 0.166),
            parent=self.minimap_frame,
        )
        self.minimap_grid_h = DirectFrame(
            frameColor=(0.58, 0.56, 0.52, 0.20),
            frameSize=(-0.154, 0.154, -0.001, 0.001),
            parent=self.minimap_frame,
        )
        self.minimap_grid_v = DirectFrame(
            frameColor=(0.58, 0.56, 0.52, 0.20),
            frameSize=(-0.001, 0.001, -0.154, 0.154),
            parent=self.minimap_frame,
        )
        self.minimap_player = DirectFrame(
            frameColor=(0.34, 0.76, 0.95, 0.98),
            frameSize=(-0.010, 0.010, -0.010, 0.010),
            parent=self.minimap_frame,
        )
        self.minimap_pin = DirectFrame(
            frameColor=(0.95, 0.78, 0.28, 0.96),
            frameSize=(-0.012, 0.012, -0.012, 0.012),
            parent=self.minimap_frame,
        )
        self.minimap_pin.hide()
        place_ui_on_top(self.minimap_border, 84)
        place_ui_on_top(self.minimap_inner, 85)
        place_ui_on_top(self.minimap_grid_h, 86)
        place_ui_on_top(self.minimap_grid_v, 86)
        place_ui_on_top(self.minimap_player, 87)
        place_ui_on_top(self.minimap_pin, 88)

        self.minimap_title = OnscreenText(
            text=self.app.data_mgr.t("hud.minimap", "MINIMAP"),
            pos=(1.16, -0.82),
            scale=0.021,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ACenter,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        self.minimap_hint = OnscreenText(
            text="",
            pos=(1.16, -0.86),
            scale=0.020,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.82),
            align=TextNode.ACenter,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.minimap_title, 84)
        place_ui_on_top(self.minimap_hint, 84)

    def _coerce_vec3(self, value):
        if value is None:
            return None
        try:
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                vx, vy, vz = float(value[0]), float(value[1]), float(value[2])
            else:
                vx, vy, vz = float(value.x), float(value.y), float(value.z)
            if not all(math.isfinite(v) for v in (vx, vy, vz)):
                return None
            return (vx, vy, vz)
        except Exception:
            return None

    def _get_player_world_pos(self, char_state=None):
        if char_state and hasattr(char_state, "position"):
            pos = self._coerce_vec3(char_state.position)
            if pos:
                return pos
        player = getattr(self.app, "player", None)
        actor = getattr(player, "actor", None) if player else None
        if actor:
            try:
                return self._coerce_vec3(actor.getPos(self.app.render))
            except Exception:
                return self._coerce_vec3(actor.getPos())
        return None

    def _hide_breadcrumbs(self):
        if hasattr(self, "_breadcrumb_root"):
            self._breadcrumb_root.hide()
        for node in self._breadcrumb_nodes:
            node.hide()

    def _update_breadcrumbs(self, dt, player_pos, target):
        if not player_pos or not target:
            self._hide_breadcrumbs()
            return

        px, py, pz = player_pos
        tx, ty, tz = target
        dx = tx - px
        dy = ty - py
        dz = tz - pz
        dist = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
        if not math.isfinite(dist) or dist < 3.0:
            self._hide_breadcrumbs()
            return

        step = 6.0
        count = int(dist / step)
        count = max(1, min(count, len(self._breadcrumb_nodes)))
        self._breadcrumb_pulse += max(0.0, float(dt)) * 4.0
        self._breadcrumb_root.show()

        for idx, node in enumerate(self._breadcrumb_nodes):
            if idx >= count:
                node.hide()
                continue
            t = float(idx + 1) / float(count + 1)
            if not math.isfinite(t):
                node.hide()
                continue
            wobble = 0.08 * math.sin(self._breadcrumb_pulse + (idx * 0.6))
            node.show()
            node.setPos(px + (dx * t), py + (dy * t), pz + (dz * t) + 0.25 + wobble)
            node.setScale(0.65 + (0.35 * t))

    def _update_minimap(self, quest_data, player_pos):
        tracked = None
        if isinstance(quest_data, list):
            for item in quest_data:
                if not isinstance(item, dict):
                    continue
                target = self._coerce_vec3(item.get("target"))
                if target:
                    tracked = item
                    break

        if not player_pos:
            self.minimap_pin.hide()
            self.minimap_hint.setText(self.app.data_mgr.t("hud.no_target", "No target"))
            return

        if not tracked:
            self.minimap_pin.hide()
            self.minimap_hint.setText(self.app.data_mgr.t("hud.no_target", "No target"))
            return

        target = self._coerce_vec3(tracked.get("target"))
        if not target:
            self.minimap_pin.hide()
            self.minimap_hint.setText(self.app.data_mgr.t("hud.no_target", "No target"))
            return

        px, py, _ = player_pos
        tx, ty, _ = target
        dx = tx - px
        dy = ty - py
        map_range = max(1.0, float(self._minimap_range))
        nx = max(-1.0, min(1.0, dx / map_range))
        ny = max(-1.0, min(1.0, dy / map_range))
        self.minimap_pin.show()
        self.minimap_pin.setPos(nx * 0.145, 0, ny * 0.145)

        status = str(tracked.get("status", "")).strip() or "Reach"
        if status.lower() == "reach":
            status = self.app.data_mgr.t("hud.reach", "Reach")
        elif status.lower() == "interact":
            status = self.app.data_mgr.t("hud.interact", "Interact")
        dist_txt = self._format_dist(tracked.get("distance"))
        self.minimap_hint.setText(f"{status}: {dist_txt}")

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
    def push_damage_event(self, amount, damage_type):
        """Called when player takes damage. Triggers visual effects but no floating numbers."""
        pass

    def notify_respawn(self, duration=4.0):
        self._respawn_active = True
        self._respawn_timer = float(duration)
        if hasattr(self, "respawn_root"):
            self.respawn_root.show()

    def _create_respawn_notification(self):
        self._respawn_active = False
        self._respawn_timer = 0.0
        self.respawn_root = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-2, 2, -1, 1),
            parent=self.root,
        )
        self.respawn_bg = DirectFrame(
            frameColor=(0.05, 0.01, 0.01, 0.0),
            frameSize=(-2, 2, -1, 1),
            parent=self.respawn_root,
        )
        self.respawn_title = OnscreenText(
            text=self.app.data_mgr.t("hud.fainted", "YOU HAVE FAINTED"),
            pos=(0.0, 0.12),
            scale=0.10,
            fg=(0.92, 0.24, 0.24, 0.0),
            shadow=(0, 0, 0, 0.0),
            align=TextNode.ACenter,
            parent=self.respawn_root,
            mayChange=True,
            font=title_font(self.app),
        )
        self.respawn_hint = OnscreenText(
            text=self.app.data_mgr.t("hud.respawn_tip", "Respawn available soon..."),
            pos=(0.0, -0.05),
            scale=0.035,
            fg=(0.85, 0.85, 0.88, 0.0),
            shadow=(0, 0, 0, 0.0),
            align=TextNode.ACenter,
            parent=self.respawn_root,
            mayChange=True,
            font=body_font(self.app),
        )
        self.respawn_timer_text = OnscreenText(
            text="",
            pos=(0.0, -0.15),
            scale=0.05,
            fg=(0.95, 0.90, 0.60, 0.0),
            shadow=(0, 0, 0, 0.0),
            align=TextNode.ACenter,
            parent=self.respawn_root,
            mayChange=True,
            font=title_font(self.app),
        )
        for node in (self.respawn_bg, self.respawn_title, self.respawn_hint, self.respawn_timer_text):
            place_ui_on_top(node, 95)
        self.respawn_root.hide()


    def _damage_color(self, damage_type):
        t = str(damage_type or "").lower()
        if t == "fire":
            return (0.95, 0.46, 0.20, 1.0)
        if t == "lightning":
            return (0.75, 0.90, 1.00, 1.0)
        if t == "ice":
            return (0.55, 0.80, 1.00, 1.0)
        if t == "poison":
            return (0.52, 0.88, 0.34, 1.0)
        if t == "arcane":
            return (0.80, 0.55, 1.00, 1.0)
        if t == "holy":
            return (0.95, 0.90, 0.60, 1.0)
        if t in {"bleed", "slash"}:
            return (0.92, 0.24, 0.24, 1.0)
        if t in {"crush", "impact"}:
            return (0.96, 0.72, 0.56, 1.0)
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
        self.location_text = OnscreenText(
            text="",
            pos=(-1.36, 0.78),
            scale=0.032,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ALeft,
            parent=self.root,
            mayChange=True,
            font=b_font,
        )
        place_ui_on_top(self.xp_text, 84)
        place_ui_on_top(self.gold_text, 84)
        place_ui_on_top(self.location_text, 84)

    def _create_targeting_reticle(self):
        self.reticle_root = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-0.06, 0.06, -0.06, 0.06),
            pos=(0.0, 0.0, 0.0),
            parent=self.root,
        )
        self.reticle_line_top = DirectFrame(
            frameColor=(0.88, 0.86, 0.80, 0.34),
            frameSize=(-0.0016, 0.0016, 0.010, 0.026),
            parent=self.reticle_root,
        )
        self.reticle_line_bottom = DirectFrame(
            frameColor=(0.88, 0.86, 0.80, 0.34),
            frameSize=(-0.0016, 0.0016, -0.026, -0.010),
            parent=self.reticle_root,
        )
        self.reticle_line_left = DirectFrame(
            frameColor=(0.88, 0.86, 0.80, 0.34),
            frameSize=(-0.026, -0.010, -0.0016, 0.0016),
            parent=self.reticle_root,
        )
        self.reticle_line_right = DirectFrame(
            frameColor=(0.88, 0.86, 0.80, 0.34),
            frameSize=(0.010, 0.026, -0.0016, 0.0016),
            parent=self.reticle_root,
        )
        self.reticle_dot = DirectFrame(
            frameColor=(0.90, 0.88, 0.82, 0.45),
            frameSize=(-0.0018, 0.0018, -0.0018, 0.0018),
            parent=self.reticle_root,
        )
        self.target_label = OnscreenText(
            text="",
            pos=(0.0, 0.08),
            scale=0.028,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.82),
            align=TextNode.ACenter,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        self.target_hint = OnscreenText(
            text="",
            pos=(0.0, 0.045),
            scale=0.021,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ACenter,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        for node in (
            self.reticle_root,
            self.reticle_line_top,
            self.reticle_line_bottom,
            self.reticle_line_left,
            self.reticle_line_right,
            self.reticle_dot,
            self.target_label,
            self.target_hint,
        ):
            place_ui_on_top(node, 86)

    def _create_boss_health_bar(self):
        self.boss_hp_root = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-0.50, 0.50, -0.08, 0.08),
            pos=(0.0, 0.0, 0.88),
            parent=self.root,
        )
        self.boss_hp_bg = DirectFrame(
            frameColor=(0.08, 0.02, 0.02, 0.80),
            frameSize=(-0.42, 0.42, -0.022, 0.022),
            parent=self.boss_hp_root,
        )
        self.boss_hp_fill = DirectFrame(
            frameColor=(0.86, 0.22, 0.20, 0.96),
            frameSize=(-0.418, 0.418, -0.018, 0.018),
            parent=self.boss_hp_root,
        )
        self.boss_hp_trim = DirectFrame(
            frameColor=(0.86, 0.72, 0.40, 0.58),
            frameSize=(-0.426, 0.426, -0.028, 0.028),
            parent=self.boss_hp_root,
        )
        self.boss_hp_name = OnscreenText(
            text="",
            pos=(0.0, 0.040),
            scale=0.030,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.86),
            align=TextNode.ACenter,
            parent=self.boss_hp_root,
            mayChange=True,
            font=title_font(self.app),
        )
        self.boss_hp_value = OnscreenText(
            text="",
            pos=(0.0, -0.011),
            scale=0.024,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.80),
            align=TextNode.ACenter,
            parent=self.boss_hp_root,
            mayChange=True,
            font=body_font(self.app),
        )
        for node in (
            self.boss_hp_root,
            self.boss_hp_bg,
            self.boss_hp_fill,
            self.boss_hp_trim,
            self.boss_hp_name,
            self.boss_hp_value,
        ):
            place_ui_on_top(node, 87)
        self.boss_hp_root.hide()

    def _update_boss_health_bar(self, target_info=None):
        resolver = getattr(type(self), "_resolve_boss_bar_target_info", None)
        if not callable(resolver):
            resolver = getattr(HUDOverlay, "_resolve_boss_bar_target_info", None)
        if callable(resolver):
            info = resolver(self, target_info)
        else:
            info = target_info if isinstance(target_info, dict) else {}
        is_enemy = str(info.get("kind", "") or "").strip().lower() == "enemy"
        is_boss = bool(info.get("is_boss", False))
        if not (is_enemy and is_boss):
            self.boss_hp_root.hide()
            self.boss_hp_name.setText("")
            self.boss_hp_value.setText("")
            return

        try:
            hp = max(0.0, float(info.get("hp", 0.0) or 0.0))
        except Exception:
            hp = 0.0
        try:
            max_hp = max(1.0, float(info.get("max_hp", 1.0) or 1.0))
        except Exception:
            max_hp = 1.0
        hp = min(max_hp, hp)
        ratio = float(info.get("hp_ratio", hp / max_hp) or (hp / max_hp))
        ratio = max(0.0, min(1.0, ratio))

        full_half = 0.418
        left = -full_half
        right = left + ((full_half * 2.0) * ratio)
        self.boss_hp_fill["frameSize"] = (left, max(left, right), -0.018, 0.018)

        name = str(info.get("name", "") or "").strip()
        title = self.app.data_mgr.t("hud.boss_health", "BOSS HP")
        self.boss_hp_name.setText(f"{title}: {name or 'Boss'}")
        self.boss_hp_value.setText(f"{int(round(hp))}/{int(round(max_hp))}")
        self.boss_hp_root.show()

    def _resolve_boss_bar_target_info(self, target_info=None):
        info = target_info if isinstance(target_info, dict) else {}
        is_enemy = str(info.get("kind", "") or "").strip().lower() == "enemy"
        is_boss = bool(info.get("is_boss", False))
        if is_enemy and is_boss:
            return info
        getter = getattr(getattr(self, "app", None), "get_active_boss_target_info", None)
        if callable(getter):
            try:
                resolved = getter()
            except Exception:
                resolved = None
            if isinstance(resolved, dict):
                return resolved
        return {}

    def _update_targeting_reticle(self, dt, target_info=None):
        dt = max(0.0, float(dt or 0.0))
        self._reticle_pulse = (self._reticle_pulse + dt * 4.0) % (math.pi * 4.0)
        base = (0.88, 0.86, 0.80, 0.34)
        line_color = base
        dot_color = (0.90, 0.88, 0.82, 0.45)
        label = ""
        hint = ""
        pulse_boost = 0.0
        track_target = False

        if isinstance(target_info, dict):
            track_target = True
            kind = str(target_info.get("kind", "")).strip().lower()
            name = str(target_info.get("name", "") or "").strip()
            locked = bool(target_info.get("locked", False))
            if locked:
                pulse_boost = 0.95
                line_color = (0.96, 0.42, 0.36, 0.95)
                dot_color = (1.0, 0.58, 0.52, 0.98)
                label = f"{self.app.data_mgr.t('hud.target_locked', 'LOCKED')}: {name or kind.title()}"
                hint = self.app.data_mgr.t(
                    "hud.target_lock_release",
                    f"Press {self._target_lock_hint_key} to release",
                )
            else:
                pulse_boost = 0.42
                tone = (0.95, 0.83, 0.44, 0.72)
                if kind == "enemy":
                    tone = (0.96, 0.57, 0.42, 0.76)
                elif kind == "npc":
                    tone = (0.62, 0.84, 0.98, 0.74)
                elif kind == "vehicle":
                    tone = (0.84, 0.94, 0.62, 0.70)
                elif kind == "story":
                    tone = (0.84, 0.80, 0.98, 0.78)
                line_color = tone
                dot_color = (tone[0], tone[1], tone[2], min(0.95, tone[3] + 0.12))
                label = name or kind.title()
                if kind == "story":
                    hint = self.app.data_mgr.t(
                        "hud.interact_hint",
                        f"Press {self._interact_hint_key} to interact",
                    )
                else:
                    hint = self.app.data_mgr.t(
                        "hud.target_lock_hint",
                        f"Press {self._target_lock_hint_key} to lock",
                    )

        pulse = (0.5 + 0.5 * math.sin(self._reticle_pulse * (2.4 if pulse_boost > 0.8 else 1.7))) if track_target else 0.0
        offset = (0.0012 + 0.0026 * pulse) * pulse_boost
        inner = 0.010 + offset
        outer = 0.026 + offset
        thickness = 0.0016 + (0.0003 * pulse * pulse_boost)
        dot_half = 0.0018 + (0.0007 * pulse * max(0.3, pulse_boost))
        new_scale = 1.0 + (0.07 * pulse * pulse_boost)
        if math.isfinite(new_scale):
            self.reticle_root.setScale(new_scale)
        self.reticle_line_top["frameSize"] = (-thickness, thickness, inner, outer)
        self.reticle_line_bottom["frameSize"] = (-thickness, thickness, -outer, -inner)
        self.reticle_line_left["frameSize"] = (-outer, -inner, -thickness, thickness)
        self.reticle_line_right["frameSize"] = (inner, outer, -thickness, thickness)
        self.reticle_dot["frameSize"] = (-dot_half, dot_half, -dot_half, dot_half)

        for node in (
            self.reticle_line_top,
            self.reticle_line_bottom,
            self.reticle_line_left,
            self.reticle_line_right,
        ):
            node["frameColor"] = line_color
        self.reticle_dot["frameColor"] = dot_color
        self.target_label.setText(label)
        self.target_hint.setText(hint)
        self._update_boss_health_bar(target_info)

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

    def _create_stealth_hint(self):
        self.stealth_text = OnscreenText(
            text="",
            pos=(-1.36, -0.72),
            scale=0.026,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.82),
            align=TextNode.ALeft,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.stealth_text, 84)

    def _create_tutorial_hint(self):
        self.tutorial_panel = DirectFrame(
            frameColor=(0.10, 0.09, 0.08, 0.66),
            frameSize=(0.0, 0.56, -0.135, 0.0),
            pos=(-1.34, 0, 0.93),
            parent=self.root,
        )
        self.tutorial_panel_border = DirectFrame(
            frameColor=(0.82, 0.70, 0.42, 0.66),
            frameSize=(0.002, 0.558, -0.133, -0.002),
            parent=self.tutorial_panel,
        )
        self.tutorial_panel_inset = DirectFrame(
            frameColor=(0.03, 0.03, 0.03, 0.20),
            frameSize=(0.010, 0.550, -0.127, -0.010),
            parent=self.tutorial_panel,
        )
        self.tutorial_header_text = OnscreenText(
            text="",
            pos=(0.03, -0.032),
            scale=0.022,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.82),
            align=TextNode.ALeft,
            parent=self.tutorial_panel,
            mayChange=True,
            font=body_font(self.app),
        )
        self.tutorial_progress_text = OnscreenText(
            text="",
            pos=(0.63, -0.032),
            scale=0.022,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.82),
            align=TextNode.ARight,
            parent=self.tutorial_panel,
            mayChange=True,
            font=body_font(self.app),
        )
        self.tutorial_title_text = OnscreenText(
            text="",
            pos=(0.03, -0.074),
            scale=0.029,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.88),
            align=TextNode.ALeft,
            parent=self.tutorial_panel,
            mayChange=True,
            font=title_font(self.app),
        )
        self.tutorial_body_text = OnscreenText(
            text="",
            pos=(0.03, -0.104),
            scale=0.020,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.82),
            align=TextNode.ALeft,
            parent=self.tutorial_panel,
            mayChange=True,
            font=body_font(self.app),
        )
        self.tutorial_keys_text = OnscreenText(
            text="",
            pos=(0.03, -0.123),
            scale=0.018,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.78),
            align=TextNode.ALeft,
            parent=self.tutorial_panel,
            mayChange=True,
            font=body_font(self.app),
        )
        self.tutorial_progress_bg = DirectFrame(
            frameColor=(0.10, 0.10, 0.12, 0.92),
            frameSize=(0.03, 0.53, -0.132, -0.122),
            parent=self.tutorial_panel,
        )
        self.tutorial_progress_fill = DirectFrame(
            frameColor=(0.84, 0.72, 0.36, 0.94),
            frameSize=(0.03, 0.03, -0.132, -0.122),
            parent=self.tutorial_panel,
        )
        self.tutorial_complete_overlay = DirectFrame(
            frameColor=(0.01, 0.02, 0.02, 0.0),
            frameSize=(-2.0, 2.0, -1.0, 1.0),
            parent=self.root,
        )
        self.tutorial_complete_panel = DirectFrame(
            frameColor=(0.08, 0.14, 0.10, 0.90),
            frameSize=(-0.54, 0.54, -0.12, 0.12),
            pos=(0.0, 0.0, 0.36),
            parent=self.tutorial_complete_overlay,
        )
        self.tutorial_complete_border = DirectFrame(
            frameColor=(0.62, 0.92, 0.72, 0.88),
            frameSize=(-0.538, 0.538, -0.118, 0.118),
            parent=self.tutorial_complete_panel,
        )
        self.tutorial_complete_title = OnscreenText(
            text="",
            pos=(0.0, 0.038),
            scale=0.054,
            fg=(0.76, 0.99, 0.85, 1.0),
            shadow=(0, 0, 0, 0.88),
            align=TextNode.ACenter,
            parent=self.tutorial_complete_panel,
            mayChange=True,
            font=title_font(self.app),
        )
        self.tutorial_complete_text = OnscreenText(
            text="",
            pos=(0.0, -0.012),
            scale=0.026,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.80),
            align=TextNode.ACenter,
            parent=self.tutorial_complete_panel,
            mayChange=True,
            font=body_font(self.app),
        )
        self.tutorial_complete_hint = OnscreenText(
            text="",
            pos=(0.0, -0.068),
            scale=0.023,
            fg=(0.72, 0.90, 0.78, 1.0),
            shadow=(0, 0, 0, 0.76),
            align=TextNode.ACenter,
            parent=self.tutorial_complete_panel,
            mayChange=True,
            font=body_font(self.app),
        )
        self._tutorial_progress_left = 0.03
        self._tutorial_progress_width = 0.50
        self._tutorial_flash_time = 0.0
        self._tutorial_complete_anim_t = 0.0
        self._tutorial_compact_mode = True

        # Legacy fallback for any systems still using plain tutorial text.
        self.tutorial_text = OnscreenText(
            text="",
            pos=(-1.36, 0.74),
            scale=0.028,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.80),
            align=TextNode.ALeft,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        self.tutorial_text.hide()

        for node in (
            self.tutorial_panel,
            self.tutorial_panel_border,
            self.tutorial_panel_inset,
            self.tutorial_header_text,
            self.tutorial_progress_text,
            self.tutorial_title_text,
            self.tutorial_body_text,
            self.tutorial_keys_text,
            self.tutorial_progress_bg,
            self.tutorial_progress_fill,
            self.tutorial_complete_overlay,
            self.tutorial_complete_panel,
            self.tutorial_complete_border,
            self.tutorial_complete_title,
            self.tutorial_complete_text,
            self.tutorial_complete_hint,
            self.tutorial_text,
        ):
            place_ui_on_top(node, 84)
        place_ui_on_top(self.tutorial_complete_overlay, 90)
        place_ui_on_top(self.tutorial_complete_panel, 91)
        place_ui_on_top(self.tutorial_complete_border, 92)
        place_ui_on_top(self.tutorial_complete_title, 93)
        place_ui_on_top(self.tutorial_complete_text, 93)
        place_ui_on_top(self.tutorial_complete_hint, 93)
        self.tutorial_complete_overlay.hide()

    def _set_tutorial_progress(self, ratio):
        pct = max(0.0, min(1.0, float(ratio or 0.0)))
        right = self._tutorial_progress_left + (self._tutorial_progress_width * pct)
        self.tutorial_progress_fill["frameSize"] = (
            self._tutorial_progress_left,
            max(self._tutorial_progress_left, right),
            -0.132,
            -0.122,
        )

    def _apply_tutorial_phase_style(self, phase, flash=False):
        phase_key = str(phase or "core").strip().lower()
        schemes = {
            "core": {
                "panel": (0.10, 0.09, 0.08, 0.78),
                "border": (0.82, 0.70, 0.42, 0.72),
                "title": THEME["gold_soft"],
                "keys": THEME["text_muted"],
                "fill": (0.84, 0.72, 0.36, 0.94),
            },
            "advanced": {
                "panel": (0.07, 0.09, 0.11, 0.80),
                "border": (0.42, 0.72, 0.90, 0.74),
                "title": (0.68, 0.86, 1.0, 1.0),
                "keys": (0.64, 0.82, 0.95, 1.0),
                "fill": (0.42, 0.74, 1.0, 0.95),
            },
            "await_advanced": {
                "panel": (0.11, 0.08, 0.06, 0.82),
                "border": (0.94, 0.70, 0.30, 0.76),
                "title": (1.00, 0.84, 0.48, 1.0),
                "keys": (0.95, 0.83, 0.64, 1.0),
                "fill": (0.95, 0.68, 0.28, 0.95),
            },
            "opening": {
                "panel": (0.08, 0.10, 0.12, 0.78),
                "border": (0.56, 0.78, 0.92, 0.72),
                "title": (0.74, 0.92, 1.0, 1.0),
                "keys": (0.74, 0.86, 0.95, 1.0),
                "fill": (0.48, 0.76, 0.96, 0.94),
            },
            "complete": {
                "panel": (0.06, 0.11, 0.08, 0.82),
                "border": (0.42, 0.82, 0.56, 0.74),
                "title": (0.72, 0.98, 0.80, 1.0),
                "keys": (0.70, 0.90, 0.78, 1.0),
                "fill": (0.44, 0.84, 0.56, 0.95),
            },
        }
        style = schemes.get(phase_key, schemes["core"])
        border = style["border"]
        if flash:
            # Flash is short-lived and only boosts the border for step completion feedback.
            border = (
                min(1.0, border[0] + 0.22),
                min(1.0, border[1] + 0.18),
                min(1.0, border[2] + 0.18),
                min(1.0, border[3] + 0.16),
            )
        self.tutorial_panel["frameColor"] = style["panel"]
        self.tutorial_panel_border["frameColor"] = border
        self.tutorial_title_text.setFg(style["title"])
        self.tutorial_keys_text.setFg(style["keys"])
        self.tutorial_progress_fill["frameColor"] = style["fill"]

    def _format_tutorial_keys(self, keys):
        if not isinstance(keys, list):
            return ""
        pretty = []
        for key in keys:
            token = str(key or "").strip().upper()
            if token and token not in pretty:
                pretty.append(token)
        if not pretty:
            return ""
        keys_label = self.app.data_mgr.t("ui.tutorial_keys", "Keys")
        chips = "  ".join(f"[{token}]" for token in pretty[:6])
        return f"{keys_label}: {chips}"

    def _clear_tutorial_hint(self):
        self.tutorial_header_text.setText("")
        self.tutorial_progress_text.setText("")
        self.tutorial_title_text.setText("")
        self.tutorial_body_text.setText("")
        self.tutorial_keys_text.setText("")
        self._set_tutorial_progress(0.0)
        self.tutorial_panel.hide()
        self.tutorial_complete_overlay.hide()
        self.tutorial_complete_title.setText("")
        self.tutorial_complete_text.setText("")
        self.tutorial_complete_hint.setText("")
        self._tutorial_complete_anim_t = 0.0
        self.tutorial_text.setText("")
        self.tutorial_text.hide()

    def _update_tutorial_completion_banner(self, dt, tutorial_state):
        if not isinstance(tutorial_state, dict) or str(tutorial_state.get("phase", "")).strip().lower() != "complete":
            self.tutorial_complete_overlay.hide()
            return

        self._tutorial_complete_anim_t += max(0.0, float(dt or 0.0))
        ttl = max(0.0, float(tutorial_state.get("completion_ttl", 0.0) or 0.0))
        pulse = 1.0 + (0.012 * math.sin(self._tutorial_complete_anim_t * 6.0))
        overlay_alpha = min(0.12, 0.02 + (ttl * 0.015))
        self.tutorial_complete_overlay["frameColor"] = (0.01, 0.02, 0.02, overlay_alpha)
        if math.isfinite(pulse):
            self.tutorial_complete_panel.setScale(pulse)
        self.tutorial_complete_overlay.show()
        self.tutorial_complete_title.setText(
            self.app.data_mgr.t("ui.tutorial_banner_title", "Training Completed")
        )
        self.tutorial_complete_text.setText(
            str(tutorial_state.get("text", "") or self.app.data_mgr.t("ui.tutorial_complete", "Tutorial complete"))
        )
        self.tutorial_complete_hint.setText(
            self.app.data_mgr.t("ui.tutorial_banner_hint", "Open journal and continue your path.")
        )

    def _update_tutorial_hint(self, dt, tutorial_state=None, tutorial_message=None):
        self._tutorial_flash_time = max(0.0, self._tutorial_flash_time - max(0.0, float(dt or 0.0)))

        if isinstance(tutorial_state, dict) and tutorial_state.get("visible", False):
            header = str(tutorial_state.get("header", "") or "").strip()
            title = str(tutorial_state.get("title", "") or "").strip()
            text = str(tutorial_state.get("text", "") or "").strip()
            progress_label = str(tutorial_state.get("progress_label", "") or "").strip()
            keys_line = self._format_tutorial_keys(tutorial_state.get("keys"))
            phase = str(tutorial_state.get("phase", "core") or "core")
            ratio = tutorial_state.get("progress_ratio", 0.0)
            if bool(tutorial_state.get("flash", False)):
                self._tutorial_flash_time = max(self._tutorial_flash_time, 0.24)
            compact = bool(self._tutorial_compact_mode)
            display_mode = str(tutorial_state.get("display_mode", "banner") or "banner").strip().lower()
            if display_mode == "card":
                compact = False

            self.tutorial_panel.show()
            self.tutorial_header_text.setText(header)
            if compact:
                headline = title
                if text:
                    headline = f"{title}: {text}" if title else text
                if len(headline) > 108:
                    headline = f"{headline[:107]}."
                self.tutorial_progress_text.setText(progress_label)
                self.tutorial_title_text.setText(headline)
                self.tutorial_body_text.setText("")
                self.tutorial_keys_text.setText(keys_line if self._tutorial_flash_time > 0.0 else "")
                self.tutorial_progress_bg.hide()
                self.tutorial_progress_fill.hide()
            else:
                self.tutorial_progress_text.setText(progress_label)
                self.tutorial_title_text.setText(title)
                self.tutorial_body_text.setText(text)
                self.tutorial_keys_text.setText(keys_line)
                self.tutorial_progress_bg.show()
                self.tutorial_progress_fill.show()
            self._set_tutorial_progress(ratio)
            self._apply_tutorial_phase_style(phase, flash=self._tutorial_flash_time > 0.0)
            self._update_tutorial_completion_banner(dt, tutorial_state)
            self.tutorial_text.setText("")
            self.tutorial_text.hide()
            return

        if isinstance(tutorial_message, str) and tutorial_message.strip():
            self.tutorial_panel.show()
            self.tutorial_header_text.setText(self.app.data_mgr.t("ui.tutorial_header", "Movement Tutorial"))
            message = tutorial_message.strip()
            if len(message) > 108:
                message = f"{message[:107]}."
            self.tutorial_progress_text.setText("")
            self.tutorial_title_text.setText(message)
            self.tutorial_body_text.setText("")
            self.tutorial_keys_text.setText("")
            self._set_tutorial_progress(0.0)
            self.tutorial_progress_bg.hide()
            self.tutorial_progress_fill.hide()
            self._apply_tutorial_phase_style("core", flash=False)
            self.tutorial_complete_overlay.hide()
            self.tutorial_text.setText("")
            self.tutorial_text.hide()
            return

        self._clear_tutorial_hint()

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
        if token in {"sword", "weapon", "weapon_sword", "melee", "fencing"}:
            return "S", (0.82, 0.84, 0.92, 1.0)
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

            is_active = idx == display_active_idx
            is_hover = isinstance(self._skill_hover_idx, int) and idx == int(self._skill_hover_idx)
            is_ult = idx == self._ultimate_skill_idx
            label.setText(raw.replace("_", " ").title())

            ring_color = (0.18, 0.18, 0.22, 0.92)
            plate_color = (0.11, 0.11, 0.14, 0.90)
            glow_color = (0.22, 0.24, 0.30, 0.18)
            icon_fg = tint
            icon_img_scale = (1.0, 1.0, 1.0, 1.0)
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

        self._refresh_control_hint_tokens()
        self.skill_controls_text.setText(
            f"Hold {self._skill_wheel_hint_key}: Skill Wheel  |  {self._attack_hint_key}: Attack/Cast ({self._cast_hint_key})"
        )

    def _fmt_key_hint(self, token):
        raw = str(token or "").strip().lower()
        if not raw:
            return "?"
        if raw == "mouse1":
            return "LMB"
        if raw == "mouse2":
            return "RMB"
        if raw in {"mouse3", "middlemouse"}:
            return "MMB"
        if raw.startswith("arrow_"):
            return raw.replace("arrow_", "ARROW ").upper()
        return raw.upper()

    def _refresh_control_hint_tokens(self):
        dm = getattr(self.app, "data_mgr", None)
        if not dm:
            return
        wheel = dm.get_binding("skill_wheel") or "tab"
        attack = dm.get_binding("attack_light") or "mouse1"
        lock = dm.get_binding("target_lock") or "t"
        interact = dm.get_binding("interact") or "f"
        self._skill_wheel_hint_key = self._fmt_key_hint(wheel)
        self._attack_hint_key = self._fmt_key_hint(attack)
        self._cast_hint_key = "wheel slot"
        self._target_lock_hint_key = self._fmt_key_hint(lock)
        self._interact_hint_key = self._fmt_key_hint(interact)

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

    def _create_npc_scene_debug(self):
        self.npc_scene_debug_text = OnscreenText(
            text="",
            pos=(-1.36, 0.64),
            scale=0.024,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.80),
            align=TextNode.ALeft,
            parent=self.root,
            mayChange=True,
            font=body_font(self.app),
        )
        place_ui_on_top(self.npc_scene_debug_text, 84)
        if not self._npc_scene_debug_enabled:
            self.npc_scene_debug_text.hide()
            return
        bus = getattr(self.app, "event_bus", None)
        if bus and hasattr(bus, "subscribe"):
            try:
                bus.subscribe("npc.micro_scene.started", self._on_npc_scene_started, priority=8)
            except Exception:
                pass

    def _on_npc_scene_started(self, event_name, payload):
        _ = event_name
        if not self._npc_scene_debug_enabled:
            return
        if not isinstance(payload, dict):
            return
        npc_id = str(payload.get("npc_id", "npc")).strip()
        activity = str(payload.get("activity", "idle")).strip()
        profile = str(payload.get("profile", "default")).strip()
        anchor = str(payload.get("anchor_id", "")).strip()
        intensity = payload.get("intensity", 0.0)
        try:
            intensity = float(intensity)
        except Exception:
            intensity = 0.0
        suffix = f" @ {anchor}" if anchor else ""
        line = f"[{profile}] {npc_id}: {activity}{suffix} ({intensity:.2f})"
        self._npc_scene_debug_entries.append({"line": line, "ttl": float(self._npc_scene_debug_ttl)})
        if len(self._npc_scene_debug_entries) > self._npc_scene_debug_max:
            self._npc_scene_debug_entries = self._npc_scene_debug_entries[-self._npc_scene_debug_max :]

    def _update_npc_scene_debug(self, dt):
        if not self._npc_scene_debug_enabled:
            self.npc_scene_debug_text.hide()
            return
        self.npc_scene_debug_text.show()
        kept = []
        lines = []
        for row in self._npc_scene_debug_entries:
            if not isinstance(row, dict):
                continue
            ttl = float(row.get("ttl", 0.0) or 0.0) - max(0.0, float(dt))
            if ttl <= 0.0:
                continue
            row["ttl"] = ttl
            kept.append(row)
            lines.append(str(row.get("line", "")))
        self._npc_scene_debug_entries = kept[-self._npc_scene_debug_max :]
        if lines:
            self.npc_scene_debug_text.setText("NPC SCENES\n" + "\n".join(lines[-self._npc_scene_debug_max :]))
        else:
            self.npc_scene_debug_text.setText("")

    def _create_video_bot_debug(self):
        """Initialize the specialized overlay for automated Video-Bot verification."""
        self._video_bot_debug_root = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-2, 2, -1, 1),
            parent=self.root,
        )
        place_ui_on_top(self._video_bot_debug_root, 90)

        t_font = title_font(self.app)
        b_font = body_font(self.app)

        # Bot "Brain" (Plan status)
        self.bot_plan_label = OnscreenText(
            text="VIDEO-BOT: ACTIVE",
            pos=(-1.30, 0.88),
            scale=0.038,
            fg=THEME["gold_primary"],
            shadow=(0, 0, 0, 1),
            align=TextNode.ALeft,
            parent=self._video_bot_debug_root,
            mayChange=True,
            font=t_font,
        )
        self.bot_action_label = OnscreenText(
            text="[No Plan]",
            pos=(-1.30, 0.83),
            scale=0.026,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.85),
            align=TextNode.ALeft,
            parent=self._video_bot_debug_root,
            mayChange=True,
            font=b_font,
        )

        # Bot status (Telemetry)
        self.bot_telemetry_label = OnscreenText(
            text="Pos: 0, 0, 0 | Vel: 0",
            pos=(-1.30, -0.78),
            scale=0.022,
            fg=THEME["text_muted"],
            shadow=(0, 0, 0, 0.75),
            align=TextNode.ALeft,
            parent=self._video_bot_debug_root,
            mayChange=True,
            font=b_font,
        )

        # Virtual Cursor Visualizer (Lines/Dot)
        self._bot_cursor_geom = self.app.aspect2d.attachNewNode("bot_cursor_debug")
        place_ui_on_top(self._bot_cursor_geom, 95)
        self._bot_cursor_visible = False
        
        self._video_bot_debug_root.hide()

    def _update_video_bot_debug(self, dt):
        """Update telemetry data and visual aids for the bot runtime."""
        bot_enabled = bool(getattr(self.app, "_video_bot_enabled", False))
        if not bot_enabled:
            if hasattr(self, "_video_bot_debug_root"):
                self._video_bot_debug_root.hide()
            if hasattr(self, "_bot_cursor_geom"):
                self._bot_cursor_geom.hide()
            return

        self._video_bot_debug_root.show()

        # Update labels from App state
        plan_name = str(getattr(self.app, "_video_bot_plan_name", "None"))
        idx = int(getattr(self.app, "_video_bot_event_idx", 0) or 0)
        plan = getattr(self.app, "_video_bot_plan", [])
        total = len(plan) if isinstance(plan, list) else 0
        
        self.bot_plan_label.setText(f"VIDEO-BOT: {plan_name.upper()}")
        
        curr_action = "IDLE/WAIT"
        if 0 <= idx < total:
            row = plan[idx]
            curr_action = f"STEP {idx+1}/{total}: {str(row.get('action', '???')).upper()}"
        elif getattr(self.app, "_video_bot_done", False):
            curr_action = "COMPLETED"
            
        self.bot_action_label.setText(curr_action)

        # Update Telemetry
        player = getattr(self.app, "player", None)
        if player and hasattr(player, "actor"):
            pos = player.actor.getPos(self.app.render)
            vel = 0.0
            if hasattr(player, "cs") and hasattr(player.cs, "velocity"):
                v = player.cs.velocity
                vel = math.sqrt(v.x**2 + v.y**2 + v.z**2)
            self.bot_telemetry_label.setText(
                f"XYZ: {pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f} | SPD: {vel:.2f} | "
                f"FPS: {int(globalClock.getAverageFrameRate())}"
            )

        # Update Virtual Cursor
        cx, cy = getattr(self.app, "_video_bot_cursor_pos", (0.0, 0.0))
        cursor_visible = bool(getattr(self.app, "_video_bot_cursor_visible", False))
        
        if cursor_visible:
            self._bot_cursor_geom.show()
            self._bot_cursor_geom.node().removeAllChildren()
            
            # Simple red cross/dot for the virtual cursor
            ls = LineSegs("bot_cursor")
            ls.setColor(1, 0, 0, 1)
            ls.setThickness(2.5)
            # Draw a small cross
            s = 0.03
            ls.moveTo(cx - s, 0, cy)
            ls.drawTo(cx + s, 0, cy)
            ls.moveTo(cx, 0, cy - s)
            ls.drawTo(cx, 0, cy + s)
            
            self._bot_cursor_geom.node().addChild(ls.create())
        else:
            self._bot_cursor_geom.hide()

    def show(self):
        self.root.show()

    def hide(self):
        self.root.hide()
        self._checkpoint_marker_root.hide()
        self._hide_breadcrumbs()
        self.minimap_pin.hide()
        self.minimap_hint.setText("")
        self.target_label.setText("")
        self.target_hint.setText("")
        self._update_boss_health_bar(None)
        self._clear_tutorial_hint()
        npc_scene_debug_text = getattr(self, "npc_scene_debug_text", None)
        if npc_scene_debug_text is not None:
            npc_scene_debug_text.setText("")

    def refresh_locale(self):
        self._refresh_control_hint_tokens()
        self.hp_label.setText(self.app.data_mgr.t("stats.health", "Health"))
        self.sp_label.setText(self.app.data_mgr.t("stats.stamina", "Stamina"))
        self.mp_label.setText(self.app.data_mgr.t("stats.mana", "Mana"))
        self.quest_header.setText(self.app.data_mgr.t("hud.active_quests", "ACTIVE QUESTS"))
        self.minimap_title.setText(self.app.data_mgr.t("hud.minimap", "MINIMAP"))
        self._xp_label_text = self.app.data_mgr.t("stats.xp", "XP")
        self._gold_label_text = self.app.data_mgr.t("stats.gold", "Gold")
        self._refresh_profile_text()
        if not self.boss_hp_root.isHidden():
            self.boss_hp_name.setText(self.app.data_mgr.t("hud.boss_health", "BOSS HP"))
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
        if fill is self.hp_fill:
            self._set_ring_fill(
                self._hp_ring_segments,
                pct,
                self._ring_style["hp"]["active"],
                self._ring_style["hp"]["inactive"],
            )
        elif fill is self.sp_fill:
            self._set_ring_fill(
                self._stamina_ring_segments,
                pct,
                self._ring_style["stamina"]["active"],
                self._ring_style["stamina"]["inactive"],
            )
        elif fill is self.mp_fill:
            self._set_ring_fill(
                self._mana_ring_segments,
                pct,
                self._ring_style["mana"]["active"],
                self._ring_style["mana"]["inactive"],
            )

    def _smooth_ratio(self, current, target, dt, speed=9.0):
        target = max(0.0, min(1.0, float(target or 0.0)))
        current = max(0.0, min(1.0, float(current or 0.0)))
        dt = max(0.0, float(dt or 0.0))
        if dt <= 0.0:
            return target
        alpha = 1.0 - math.exp(-max(0.01, float(speed)) * dt)
        return current + (target - current) * alpha

    def _refresh_profile_text(self):
        self.xp_text.setText(f"{self._xp_label_text}: {self._xp}")
        self.gold_text.setText(f"{self._gold_label_text}: {self._gold}")
        
    def set_location_name(self, name):
        """Update the displayed location/region name on the HUD."""
        if hasattr(self, "location_text"):
            clean_name = str(name or "").strip().upper()
            self.location_text.setText(clean_name)
            if clean_name:
                self.location_text.show()
            else:
                self.location_text.hide()

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

    def _update_checkpoint_tracker(self, dt, quest_data, player_pos):
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
            self._hide_breadcrumbs()
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
            self._hide_breadcrumbs()
            return

        try:
            tx = float(target[0])
            ty = float(target[1])
            tz = float(target[2])
        except Exception:
            self._checkpoint_marker_root.hide()
            self._hide_breadcrumbs()
            return

        self._checkpoint_pulse += max(0.0, float(dt)) * 5.0
        pulse = 1.0 + (0.12 * math.sin(self._checkpoint_pulse))
        self._checkpoint_marker_root.show()
        self._checkpoint_marker_root.setPos(tx, ty, tz + 2.2 + (0.12 * pulse))
        self._checkpoint_marker_root.setScale(0.95 * pulse)
        self._update_breadcrumbs(dt, player_pos, (tx, ty, tz))

    def update_cursed_effect(self, blend):
        """Update the reddish hue blend for Krimora."""
        val = float(blend if blend is not None else 0.0)
        self._cursed_blend = max(0.0, min(1.0, val if not (math.isnan(val) or math.isinf(val)) else 0.0))

    def trigger_screen_flash(self, color=(1, 1, 1), duration=0.25):
        """Triggers a full-screen color flash (e.g. for lightning or heavy hits)."""
        # Ensure color has an alpha component, default to 1.0 if not provided
        if len(color) == 3:
            color = (color[0], color[1], color[2], 1.0)
        self._flash_color = Vec4(color[0], color[1], color[2], color[3])
        self._flash_timer = float(duration)
        self._flash_total = float(duration)

    def _combo_banner_text(self, combo_state):
        payload = combo_state if isinstance(combo_state, dict) else {}
        try:
            count = max(0, int(payload.get("count", 0) or 0))
        except Exception:
            count = 0
        if count <= 0:
            return ""
        label = self.app.data_mgr.t("hud.combo", "COMBO")
        return f"{count}x {label}"

    def _combo_banner_color(self, combo_state):
        payload = combo_state if isinstance(combo_state, dict) else {}
        try:
            count = max(0, int(payload.get("count", 0) or 0))
        except Exception:
            count = 0
        kind = str(payload.get("kind", "melee") or "melee").strip().lower()
        if kind == "magic":
            if count >= 5:
                return (0.62, 0.88, 1.0, 0.98)
            if count >= 3:
                return (0.50, 0.80, 1.0, 0.96)
            return (0.42, 0.72, 0.98, 0.92)
        if count >= 5:
            return (1.0, 0.92, 0.44, 0.98)
        if count >= 3:
            return (0.98, 0.84, 0.34, 0.96)
        return THEME["gold_primary"]

    def _update_combo_banner(self, dt, combo_state):
        payload = combo_state if isinstance(combo_state, dict) else {}
        text = self._combo_banner_text(payload)
        remain = 0.0
        try:
            remain = max(0.0, float(payload.get("remain", 0.0) or 0.0))
        except Exception:
            remain = 0.0
        if (not text) or remain <= 0.0:
            self.combo_text.setText("")
            self.combo_text.hide()
            self._combo_banner_t = 0.0
            return
        self._combo_banner_t = max(0.0, float(getattr(self, "_combo_banner_t", 0.0) or 0.0)) + max(0.0, float(dt or 0.0))
        pulse = 1.0 + (0.04 * math.sin(self._combo_banner_t * 9.0))
        self.combo_text.setText(text)
        self.combo_text.setFg(self._combo_banner_color(payload))
        self.combo_text.setScale(0.08 * pulse)
        self.combo_text.show()

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
        player_pos=None,
        tutorial_message=None,
        tutorial_state=None,
        target_info=None,
        stealth_state=None,
        combo_state=None,
    ):
        if self._flash_timer > 0:
            self._flash_timer -= dt
            alpha = max(0, self._flash_timer / self._flash_total)
            self._flash_color.setW(alpha * self._flash_color.getX()) # using X as target alpha

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

        camera_fx = {}
        director = getattr(self.app, "camera_director", None)
        if director and hasattr(director, "get_screen_effect_state"):
            try:
                camera_fx = director.get_screen_effect_state() or {}
            except Exception:
                camera_fx = {}
        player = getattr(self.app, "player", None)
        damage_vignette = {}
        if player and hasattr(player, "get_damage_vignette_state"):
            try:
                damage_vignette = player.get_damage_vignette_state() or {}
            except Exception:
                damage_vignette = {}
        self._apply_context_vignette(
            boost=camera_fx.get("vignette_boost", 0.0) if isinstance(camera_fx, dict) else 0.0,
            fear=camera_fx.get("fear_tint", 0.0) if isinstance(camera_fx, dict) else 0.0,
            damage=camera_fx.get("damage_tint", 0.0) if isinstance(camera_fx, dict) else 0.0,
            damage_type=damage_vignette.get("type", "") if isinstance(damage_vignette, dict) else "",
            damage_intensity=damage_vignette.get("intensity", 0.0) if isinstance(damage_vignette, dict) else 0.0,
        )
        self._apply_screen_postfx(
            boost=camera_fx.get("vignette_boost", 0.0) if isinstance(camera_fx, dict) else 0.0,
            fear=camera_fx.get("fear_tint", 0.0) if isinstance(camera_fx, dict) else 0.0,
            damage=camera_fx.get("damage_tint", 0.0) if isinstance(camera_fx, dict) else 0.0,
            combat_heat=camera_fx.get("combat_heat", 0.0) if isinstance(camera_fx, dict) else 0.0,
            damage_type=damage_vignette.get("type", "") if isinstance(damage_vignette, dict) else "",
            damage_intensity=damage_vignette.get("intensity", 0.0) if isinstance(damage_vignette, dict) else 0.0,
        )
        if isinstance(mount_hint, str):
            self.mount_hint_text.setText(mount_hint)
        else:
            self.mount_hint_text.setText("")

        if isinstance(stealth_state, dict) and stealth_state.get("active", False):
            state_name = str(stealth_state.get("state", "exposed") or "exposed").strip().lower()
            stealth_lvl = max(0.0, min(1.0, float(stealth_state.get("stealth_level", 0.0) or 0.0)))
            noise_lvl = max(0.0, min(1.0, float(stealth_state.get("noise", 1.0) or 1.0)))
            header = self.app.data_mgr.t("hud.stealth", "STEALTH")
            if state_name == "hidden":
                state_label = self.app.data_mgr.t("hud.stealth_hidden", "Hidden")
                color = (0.50, 0.88, 0.62, 0.95)
            elif state_name == "cautious":
                state_label = self.app.data_mgr.t("hud.stealth_cautious", "Cautious")
                color = (0.92, 0.82, 0.42, 0.95)
            else:
                state_label = self.app.data_mgr.t("hud.stealth_exposed", "Exposed")
                color = (0.94, 0.54, 0.44, 0.95)
            pct = int(round(stealth_lvl * 100.0))
            noise_pct = int(round(noise_lvl * 100.0))
            self.stealth_text.setText(f"{header}: {state_label}  {pct}%  |  {self.app.data_mgr.t('hud.noise', 'Noise')}: {noise_pct}%")
            self.stealth_text.setFg(color)
        else:
            self.stealth_text.setText("")

        self._update_tutorial_hint(dt, tutorial_state=tutorial_state, tutorial_message=tutorial_message)
        self._update_npc_scene_debug(dt)
        self._update_video_bot_debug(dt)

        if isinstance(combat_event, dict):
            amount = int(combat_event.get("amount", 0) or 0)
            dmg_type = str(combat_event.get("type", "physical") or "physical")
            label = str(combat_event.get("label", "") or "").strip()
            prefix = label if label else dmg_type.upper()
            self.damage_text.setText(f"{prefix}: {amount}")
            self.damage_text["fg"] = self._damage_color(dmg_type)
        else:
            self.damage_text.setText("")

        self._update_combo_banner(dt, combo_state)

        if self._autosave_on and self.autosave_logo:
            self._logo_spin = (self._logo_spin + dt * 100.0) % 360.0
            self.autosave_logo.setR(self._logo_spin)

    def _create_video_bot_debug(self):
        """Initialize Video-Bot telemetry and visual aids."""
        self.bot_debug_root = DirectFrame(
            frameColor=(0, 0, 0, 0.45),
            frameSize=(-0.45, 0.45, -0.12, 0.12),
            pos=(1.05, 0, 0.88),
            parent=self.root,
        )
        place_ui_on_top(self.bot_debug_root, 90)
        self.bot_debug_root.hide()

        b_font = body_font(self.app)
        self.bot_plan_label = OnscreenText(
            text="BOT PLAN: None",
            pos=(-0.42, 0.08),
            scale=0.032,
            fg=(0.4, 0.9, 1.0, 1.0),
            align=TextNode.ALeft,
            parent=self.bot_debug_root,
            font=b_font,
        )
        self.bot_task_label = OnscreenText(
            text="TASK: Idle",
            pos=(-0.42, 0.04),
            scale=0.028,
            fg=THEME["text_muted"],
            align=TextNode.ALeft,
            parent=self.bot_debug_root,
            font=b_font,
        )
        self.bot_pos_label = OnscreenText(
            text="POS: 0, 0, 0",
            pos=(-0.42, 0.00),
            scale=0.026,
            fg=THEME["text_main"],
            align=TextNode.ALeft,
            parent=self.bot_debug_root,
            font=b_font,
        )

        # Virtual Cursor (2D aspect2d dot)
        self.bot_cursor = DirectFrame(
            frameColor=(1.0, 0.2, 0.2, 0.85),
            frameSize=(-0.015, 0.015, -0.015, 0.015),
            parent=self.app.aspect2d,
        )
        place_ui_on_top(self.bot_cursor, 95)
        self.bot_cursor.hide()

        # Navigation Visual Aids (3D Line & Marker)
        self.bot_nav_root = self.app.render.attachNewNode("bot_nav_visuals")
        self.bot_nav_root.setLightOff(1)
        self.bot_nav_root.setBin("fixed", 50)
        self.bot_nav_root.setDepthTest(False)
        self.bot_nav_root.setDepthWrite(False)
        self.bot_nav_root.hide()

        self._bot_nav_line_node = None

    def _is_valid_point(self, pt):
        """Check if all components of a vector/point are finite numbers."""
        from panda3d.core import Vec3
        if isinstance(pt, (list, tuple)):
            return all(math.isfinite(x) for x in pt)
        if hasattr(pt, "x") and hasattr(pt, "y") and hasattr(pt, "z"):
            return math.isfinite(pt.x) and math.isfinite(pt.y) and math.isfinite(pt.z)
        return False

    def _update_video_bot_debug(self, dt):
        """Update real-time bot telemetry and world-space debug lines."""
        bot_enabled = bool(getattr(self.app, "_video_bot_enabled", False))
        if not bot_enabled:
            self.bot_debug_root.hide()
            self.bot_cursor.hide()
            self.bot_nav_root.hide()
            return

        self.bot_debug_root.show()

        # Update Labels
        plan_name = str(getattr(self.app, "_video_bot_plan_name", "None"))
        idx = int(getattr(self.app, "_video_bot_event_idx", 0) or 0)
        plan = getattr(self.app, "_video_bot_plan", [])
        
        current_event = "Idle"
        if 0 <= idx < len(plan):
            evt = plan[idx]
            current_event = f"[{idx}] {evt.get('type', '???')} ({evt.get('action', evt.get('target', ''))})"
            
        self.bot_plan_label.setText(f"BOT PLAN: {plan_name}")
        self.bot_task_label.setText(f"TASK: {current_event}")
        
        player = getattr(self.app, "player", None)
        actor = getattr(player, "actor", None) if player else None
        if actor:
            pos = actor.getPos(self.app.render)
            self.bot_pos_label.setText(f"POS: {pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f}")

        # Update Virtual Cursor (2D)
        cx, cy = getattr(self.app, "_video_bot_cursor_pos", (0.0, 0.0))
        visible = bool(getattr(self.app, "_video_bot_cursor_visible", False))
        if visible and math.isfinite(cx) and math.isfinite(cy):
            self.bot_cursor.setPos(cx, 0, cy)
            self.bot_cursor.show()
            # Pulse color if clicking
            clicking = bool(getattr(self.app, "_video_bot_cursor_clicking", False))
            if clicking:
                self.bot_cursor["frameColor"] = (1.0, 1.0, 1.0, 1.0)
            else:
                self.bot_cursor["frameColor"] = (1.0, 0.2, 0.2, 0.85)
        else:
            self.bot_cursor.hide()

        # Update Navigation Line (3D)
        target = getattr(self.app, "_video_bot_move_target", None)
        if target and actor:
            ppos = actor.getPos(self.app.render)
            if self._is_valid_point(ppos) and self._is_valid_point(target):
                self.bot_nav_root.show()
                self._draw_bot_nav_line(ppos, target)
            else:
                self.bot_nav_root.hide()
        else:
            self.bot_nav_root.hide()

    def _draw_bot_nav_line(self, start, end):
        """Draw a 3D line from player to movement target."""
        if self._bot_nav_line_node:
            self._bot_nav_line_node.removeNode()

        ls = LineSegs("bot_nav_line")
        ls.setThickness(3.0)
        ls.setColor(0.4, 0.9, 1.0, 0.75)
        ls.moveTo(start.x, start.y, start.z + 0.5) # Elevation for visibility
        ls.drawTo(end.x, end.y, end.z + 0.2)
        
        # Add a small crosshair/X at the end
        ls.setColor(1.0, 0.8, 0.2, 0.9)
        size = 0.4
        ls.moveTo(end.x - size, end.y, end.z + 0.2)
        ls.drawTo(end.x + size, end.y, end.z + 0.2)
        ls.moveTo(end.x, end.y - size, end.z + 0.2)
        ls.drawTo(end.x, end.y + size, end.z + 0.2)
        
        self._bot_nav_line_node = self.bot_nav_root.attachNewNode(ls.create())

    def _create_npc_scene_debug(self):
        """Stub for NPC scene debug visualization."""
        pass

    def _update_npc_scene_debug(self, dt):
        """Stub for NPC scene debug update."""
        pass
