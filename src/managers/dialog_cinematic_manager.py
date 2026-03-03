"""Cinematic Dialog Manager — event-driven, letterbox-subtitled conversations.

Architecture:
  • DialogCinematicManager.start_dialogue(npc_id, dialogue_data, npc_actor)
      - Enters DIALOG game state
      - Slides in cinematic letterbox bars (top + bottom)
      - Runs speech lines one by one  (duration = chars / reading_speed + min)
      - Shows subtitles on the bottom letterbox bar
      - Switches camera between speaker ↔ listener each line
      - Plays voiceover audio from  data/audio/voices/<npc_id>/<node_id>.ogg
      - For NPC→NPC scenes: no player choice menu
      - For Player dialogues: shows choice buttons after last NPC line
      - Each node ends → auto-advance OR waits for player choice
      - Boss confrontation scenes: no choices, pure cinematic sequence

  JSON node format (extends existing schema):
    {
      "speaker": "Guard Captain Marcus",
      "text":    "Halt! State your business, citizen.",
      "animation": "salute",
      "voice":   "guard_city/start",        ← optional, relative to data/audio/voices/
      "camera":  "npc",                     ← npc | player | side | wide (default auto)
      "duration": 3.5,                      ← override auto duration
      "choices": [ ... ]                    ← triggers choice UI (interactive mode)
    }
"""

from __future__ import annotations

import math
import os

from direct.gui.DirectGui import (
    DirectButton,
    DirectFrame,
    OnscreenText,
)
from direct.interval.IntervalGlobal import (
    Func,
    LerpColorScaleInterval,
    LerpPosInterval,
    Parallel,
    Sequence,
    Wait,
)
from panda3d.core import (
    LPoint3,
    TextNode,
    TransparencyAttrib,
    Vec3,
)

from ui.design_system import THEME, body_font, title_font, place_ui_on_top
from utils.logger import logger


# ─────────────────────────────────────────────────────────────────────────
# Config constants
# ─────────────────────────────────────────────────────────────────────────

CHARS_PER_SECOND   = 18.0    # reading speed — chars per second
MIN_LINE_DURATION  = 2.0     # minimum seconds a subtitle stays on screen
MAX_LINE_DURATION  = 9.0     # maximum auto-duration (player can still advance)
LETTERBOX_H        = 0.14    # height of each letterbox bar (0..1 screen units)
BAR_SLIDE_DURATION = 0.55    # letterbox slide-in/out duration
SUBTITLE_FADE_IN   = 0.22    # subtitle text fade in
SUBTITLE_FADE_OUT  = 0.18    # subtitle text fade out
CAMERA_BLEND_SPEED = 5.5     # camera lerp speed during dialog (lower = smoother)
VOICE_BASE_PATH    = "data/audio/voices"
SPEAKER_BOX_H      = 0.06    # height of speaker name band above subtitle


def _line_duration(text: str, override: float | None = None) -> float:
    if override and override > 0:
        return float(override)
    chars = len(str(text or ""))
    return max(MIN_LINE_DURATION, min(MAX_LINE_DURATION, chars / CHARS_PER_SECOND))


def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _lerp_pt3(a, b, t):
    return LPoint3(
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


# ─────────────────────────────────────────────────────────────────────────
# DialogCinematicManager
# ─────────────────────────────────────────────────────────────────────────

class DialogCinematicManager:
    """Full cinematic dialog system with letterbox, subtitles, camera cuts, and VO."""

    def __init__(self, app):
        self.app = app

        # Runtime state
        self._active        = False
        self._sequence      = None
        self._ui_nodes      = []
        self._choice_btns   = []
        self._current_node  = None
        self._dialogue_data = None
        self._npc_actor     = None
        self._npc_id        = ""
        self._on_end        = None

        # Camera blend state
        self._cam_target_pos  = None
        self._cam_target_look = None
        self._cam_blend_t     = 0.0

        # Input lock
        self._can_advance     = False
        self._advance_queued  = False

        # Bars and subtitle widgets (built lazily)
        self._bar_top    = None
        self._bar_bot    = None
        self._sub_bg     = None
        self._sub_text   = None
        self._spk_text   = None
        self._bars_built = False

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────

    def is_active(self) -> bool:
        return self._active

    def start_dialogue(self, npc_id: str, dialogue_data: dict,
                       npc_actor=None, on_end=None) -> bool:
        """Start a cinematic dialogue.

        Args:
            npc_id:        Identifier used for voice file lookup.
            dialogue_data: Full dialogue JSON dict (keys: npc_name, dialogue_tree).
            npc_actor:     Panda3D NodePath of the NPC (for camera targeting).
            on_end:        Optional callback when dialogue finishes.
        """
        if self._active:
            logger.warning("[DialogCinematic] Already active — ignoring new start.")
            return False

        tree = dialogue_data.get("dialogue_tree")
        if not isinstance(tree, dict) or "start" not in tree:
            logger.warning(f"[DialogCinematic] Invalid dialogue data for '{npc_id}'.")
            return False

        self._active        = True
        self._npc_id        = str(npc_id or "")
        self._npc_actor     = npc_actor
        self._dialogue_data = dialogue_data
        self._on_end        = on_end
        self._can_advance   = False
        self._advance_queued = False

        self._build_ui()
        self._enter_dialog_state()
        self._play_bars_in()
        self.app.taskMgr.doMethodLater(BAR_SLIDE_DURATION + 0.05,
                                       self._task_start_node, "dialog_start_node",
                                       extraArgs=["start"], appendTask=False)
        self.app.accept("space", self._on_advance)
        self.app.accept("e",     self._on_advance)
        logger.info(f"[DialogCinematic] Started '{npc_id}'")
        return True

    def finish(self):
        if not self._active:
            return
        self._active = False
        self._clear_choices()
        self._play_bars_out()
        self.app.taskMgr.doMethodLater(BAR_SLIDE_DURATION + 0.1,
                                       self._task_cleanup, "dialog_cleanup",
                                       extraArgs=[], appendTask=False)

    # ─────────────────────────────────────────────────────────────────
    # UI building
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        if self._bars_built:
            return

        base_z_top = 1.0 + LETTERBOX_H
        base_z_bot = -(1.0 + LETTERBOX_H)

        # Top letterbox
        self._bar_top = DirectFrame(
            frameColor=(0, 0, 0, 1),
            frameSize=(-2, 2, 0, LETTERBOX_H),
            pos=(0, 0, base_z_top),
            parent=self.app.aspect2d,
        )
        place_ui_on_top(self._bar_top, 50)

        # Bottom letterbox  (subtitle zone)
        self._bar_bot = DirectFrame(
            frameColor=(0, 0, 0, 0.92),
            frameSize=(-2, 2, -LETTERBOX_H, 0),
            pos=(0, 0, base_z_bot),
            parent=self.app.aspect2d,
        )
        place_ui_on_top(self._bar_bot, 50)

        # Speaker name  (shown in top portion of bottom bar)
        self._spk_text = OnscreenText(
            text="",
            pos=(0.0, -(1.0 - LETTERBOX_H * 0.22)),
            scale=0.042,
            fg=THEME["gold_soft"],
            shadow=(0, 0, 0, 0.9),
            align=TextNode.ACenter,
            parent=self.app.aspect2d,
            mayChange=True,
            font=title_font(self.app),
        )
        self._spk_text.setColorScale(1, 1, 1, 0)
        place_ui_on_top(self._spk_text, 51)

        # Subtitle text
        self._sub_text = OnscreenText(
            text="",
            pos=(0.0, -(1.0 - LETTERBOX_H * 0.62)),
            scale=0.050,
            fg=(1, 1, 1, 1),
            shadow=(0, 0, 0, 0.85),
            align=TextNode.ACenter,
            wordwrap=28,
            parent=self.app.aspect2d,
            mayChange=True,
            font=body_font(self.app),
        )
        self._sub_text.setColorScale(1, 1, 1, 0)
        place_ui_on_top(self._sub_text, 51)

        self._ui_nodes = [self._bar_top, self._bar_bot, self._spk_text, self._sub_text]
        self._bars_built = True

    def _destroy_ui(self):
        self._clear_choices()
        for node in self._ui_nodes:
            try:
                node.destroy()
            except Exception:
                pass
        self._ui_nodes = []
        self._bars_built = False
        self._bar_top = self._bar_bot = None
        self._sub_text = self._spk_text = None

    # ─────────────────────────────────────────────────────────────────
    # Letterbox animation
    # ─────────────────────────────────────────────────────────────────

    def _play_bars_in(self):
        if not self._bar_top or not self._bar_bot:
            return
        target_top = 1.0 - LETTERBOX_H
        target_bot = -(1.0 - LETTERBOX_H)
        Parallel(
            LerpPosInterval(self._bar_top, BAR_SLIDE_DURATION,
                            (0, 0, target_top), blendType="easeOut"),
            LerpPosInterval(self._bar_bot, BAR_SLIDE_DURATION,
                            (0, 0, target_bot), blendType="easeOut"),
        ).start()

    def _play_bars_out(self):
        if not self._bar_top or not self._bar_bot:
            return
        Parallel(
            LerpPosInterval(self._bar_top, BAR_SLIDE_DURATION,
                            (0, 0, 1.0 + LETTERBOX_H), blendType="easeIn"),
            LerpPosInterval(self._bar_bot, BAR_SLIDE_DURATION,
                            (0, 0, -(1.0 + LETTERBOX_H)), blendType="easeIn"),
        ).start()

    # ─────────────────────────────────────────────────────────────────
    # Node / line playback
    # ─────────────────────────────────────────────────────────────────

    def _task_start_node(self, node_id):
        if not self._active:
            return
        tree = self._dialogue_data.get("dialogue_tree", {})
        node = tree.get(str(node_id or ""), tree.get("start"))
        if not isinstance(node, dict):
            self.finish()
            return
        self._current_node = dict(node)
        self._current_node["_id"] = node_id
        self._play_node(self._current_node)

    def _play_node(self, node: dict):
        speaker  = str(node.get("speaker", "") or "")
        text     = str(node.get("text",    "") or "")
        duration = _line_duration(text, node.get("duration"))
        choices  = node.get("choices", [])
        node_id  = node.get("_id", "unknown")

        # ── Speaker name + subtitle ─────────────────────────────
        self._show_subtitle(speaker, text)

        # ── Camera cut ──────────────────────────────────────────
        cam_hint = str(node.get("camera", "auto") or "auto").lower()
        self._do_camera_cut(speaker, cam_hint)

        # ── Animation on NPC actor ──────────────────────────────
        anim = str(node.get("animation", "idle") or "idle")
        self._play_npc_anim(anim)

        # ── Voiceover ───────────────────────────────────────────
        vo_key = str(node.get("voice", f"{self._npc_id}/{node_id}") or "")
        vo_played = self._play_voice(vo_key)

        # ── Schedule next step ──────────────────────────────────
        if isinstance(choices, list) and choices:
            # Interactive: show choices after subtitle has settled
            self._can_advance = False
            self.app.taskMgr.doMethodLater(
                max(duration * 0.6, MIN_LINE_DURATION),
                self._task_show_choices, "dialog_choices",
                extraArgs=[choices], appendTask=False,
            )
        else:
            # Auto-advance: wait for line duration then next node
            self._can_advance = True
            self._advance_queued = False
            self.app.taskMgr.doMethodLater(
                duration, self._task_auto_next, "dialog_auto_next",
                extraArgs=[node], appendTask=False,
            )

    def _task_auto_next(self, node):
        if not self._active:
            return
        # If player pressed advance early, already handled
        next_id = self._find_single_next(node)
        if next_id and next_id != "end":
            self._hide_subtitle(then=lambda: self._task_start_node(next_id))
        else:
            self._hide_subtitle(then=self.finish)

    def _on_advance(self):
        """Called when player presses Space or E."""
        if not self._active:
            return
        if not self._can_advance:
            return
        # Cancel pending auto_next task → advance immediately
        self.app.taskMgr.remove("dialog_auto_next")
        self._can_advance = False
        node = self._current_node or {}
        next_id = self._find_single_next(node)
        if next_id and next_id != "end":
            self._hide_subtitle(then=lambda: self._task_start_node(next_id))
        else:
            self._hide_subtitle(then=self.finish)

    # ─────────────────────────────────────────────────────────────────
    # Choice UI
    # ─────────────────────────────────────────────────────────────────

    def _task_show_choices(self, choices):
        if not self._active:
            return
        self._clear_choices()
        self._can_advance = False

        # Filter by conditions
        valid = [c for c in choices if self._check_condition(c.get("condition"))]
        if not valid:
            self.finish()
            return

        btn_y_start = -(1.0 - LETTERBOX_H) + 0.06
        btn_spacing = 0.075
        for idx, choice in enumerate(valid):
            txt = str(choice.get("text", "...") or "...")
            y   = btn_y_start - idx * btn_spacing
            btn = DirectButton(
                text=txt,
                text_scale=0.045,
                text_fg=THEME["gold_soft"],
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0.0),
                relief=None,
                pos=(-0.85, 0, y),
                parent=self.app.aspect2d,
                command=self._on_choice_picked,
                extraArgs=[choice],
            )
            place_ui_on_top(btn, 52)
            self._choice_btns.append(btn)

    def _on_choice_picked(self, choice):
        if not self._active:
            return
        self._clear_choices()
        action   = str(choice.get("action", "") or "")
        next_id  = str(choice.get("next_node", "end") or "end")

        if action:
            self._execute_action(action)

        if "end_dialogue" in action or next_id == "end":
            self._hide_subtitle(then=self.finish)
        else:
            self._hide_subtitle(then=lambda: self._task_start_node(next_id))

    def _clear_choices(self):
        for btn in self._choice_btns:
            try:
                btn.destroy()
            except Exception:
                pass
        self._choice_btns = []

    # ─────────────────────────────────────────────────────────────────
    # Subtitle helpers
    # ─────────────────────────────────────────────────────────────────

    def _show_subtitle(self, speaker: str, text: str):
        if self._spk_text:
            self._spk_text["text"] = speaker.upper()
            LerpColorScaleInterval(self._spk_text, SUBTITLE_FADE_IN,
                                   (1, 1, 1, 1), startColorScale=(1, 1, 1, 0),
                                   blendType="easeOut").start()
        if self._sub_text:
            self._sub_text["text"] = text
            LerpColorScaleInterval(self._sub_text, SUBTITLE_FADE_IN,
                                   (1, 1, 1, 1), startColorScale=(1, 1, 1, 0),
                                   blendType="easeOut").start()

    def _hide_subtitle(self, then=None):
        seq_list = []
        if self._sub_text:
            seq_list.append(
                LerpColorScaleInterval(self._sub_text, SUBTITLE_FADE_OUT,
                                       (1, 1, 1, 0), blendType="easeIn")
            )
        if self._spk_text:
            seq_list.append(
                LerpColorScaleInterval(self._spk_text, SUBTITLE_FADE_OUT,
                                       (1, 1, 1, 0), blendType="easeIn")
            )
        if not seq_list:
            if then:
                then()
            return
        seq = Sequence(Parallel(*seq_list))
        if then:
            seq.append(Func(then))
        seq.start()

    # ─────────────────────────────────────────────────────────────────
    # Camera direction
    # ─────────────────────────────────────────────────────────────────

    def _do_camera_cut(self, speaker: str, hint: str):
        """Issue a cinematic camera shot toward the current speaker."""
        cam_dir = self.app.camera_director
        if not cam_dir:
            return

        player = getattr(self.app, "player", None)
        npc    = self._npc_actor

        # Determine who is speaking to decide camera side
        npc_name = str(self._dialogue_data.get("npc_name", "") or "")
        is_npc_speaker = (speaker == npc_name) or (hint == "npc")
        is_player_speaker = (hint == "player")

        if hint == "wide" or not (player or npc):
            cam_dir.play_camera_shot("dialog_wide", duration=0.0,
                                     profile="cinematic", side=0.0, yaw_bias_deg=0.0)
            return

        # Over-the-shoulder: if NPC speaking → camera looks at NPC from player POV
        # If player speaking → camera looks at player from NPC POV
        if is_npc_speaker:
            cam_dir.play_camera_shot(
                "dialog_npc", duration=0.0,
                profile="dialog", side=2.3, yaw_bias_deg=8.0,
            )
        elif is_player_speaker:
            cam_dir.play_camera_shot(
                "dialog_player", duration=0.0,
                profile="dialog", side=-2.3, yaw_bias_deg=-8.0,
            )
        else:
            # auto: alternate based on current node index parity
            side_mod = getattr(self, "_cut_counter", 0) % 2
            self._cut_counter = getattr(self, "_cut_counter", 0) + 1
            side = 2.3 if side_mod == 0 else -2.3
            yaw  = 8.0 if side_mod == 0 else -8.0
            cam_dir.play_camera_shot(
                "dialog_auto", duration=0.0,
                profile="dialog", side=side, yaw_bias_deg=yaw,
            )

    # ─────────────────────────────────────────────────────────────────
    # Voiceover
    # ─────────────────────────────────────────────────────────────────

    def _play_voice(self, vo_key: str) -> bool:
        """Attempt to play voiceover audio for a dialogue line.

        Searches data/audio/voices/<vo_key>.ogg  (or .wav, .mp3).
        """
        if not vo_key:
            return False
        audio_dir = getattr(self.app, "audio_director", None)
        if not audio_dir:
            return False

        for ext in (".ogg", ".wav", ".mp3"):
            path = os.path.join(VOICE_BASE_PATH, vo_key.replace("/", os.sep) + ext)
            if os.path.exists(path):
                try:
                    snd = self.app.loader.loadSfx(path)
                    if snd:
                        snd.setVolume(0.88)
                        snd.play()
                        logger.debug(f"[DialogCinematic] VO playing: {path}")
                        return True
                except Exception as exc:
                    logger.debug(f"[DialogCinematic] VO failed {path}: {exc}")
        return False

    # ─────────────────────────────────────────────────────────────────
    # NPC animation
    # ─────────────────────────────────────────────────────────────────

    def _play_npc_anim(self, anim: str):
        actor = self._npc_actor
        if not actor:
            return
        try:
            anims = set(str(n) for n in actor.getAnimNames())
        except Exception:
            return
        clip = anim if anim in anims else ("idle" if "idle" in anims else None)
        if not clip:
            return
        try:
            actor.loop(clip)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────
    # Navigation helpers
    # ─────────────────────────────────────────────────────────────────

    def _find_single_next(self, node: dict) -> str | None:
        choices = node.get("choices", [])
        if not isinstance(choices, list) or not choices:
            return None
        for ch in choices:
            if isinstance(ch, dict):
                nxt = str(ch.get("next_node", "end") or "end")
                if self._check_condition(ch.get("condition")):
                    return nxt
        return "end"

    def _check_condition(self, condition) -> bool:
        if not condition:
            return True
        cond = str(condition).strip()
        try:
            if cond.startswith("level:"):
                rest = cond[6:].strip()
                op   = ">=" if ">=" in rest else (">" if ">" in rest else "==")
                val  = int(rest.replace(op, "").strip())
                plvl = int(getattr(getattr(self.app, "player", None), "level", 1) or 1)
                return eval(f"{plvl} {op} {val}", {}, {})
            if cond.startswith("quest_active:"):
                qid = cond[13:].strip()
                qm  = getattr(self.app, "quest_manager", None)
                return bool(qm and qm.is_active(qid))
            if cond.startswith("quest_complete:"):
                qid = cond[15:].strip()
                qm  = getattr(self.app, "quest_manager", None)
                return bool(qm and qm.is_complete(qid))
            if cond.startswith("has_item:"):
                iid = cond[9:].strip()
                inv = getattr(getattr(self.app, "player", None), "inventory", None)
                return bool(inv and inv.has(iid))
        except Exception:
            pass
        return True  # unknown condition → allow

    def _execute_action(self, action: str):
        if not action:
            return
        try:
            if action.startswith("give_quest:"):
                qid = action[11:].strip()
                qm  = getattr(self.app, "quest_manager", None)
                if qm and hasattr(qm, "start_quest"):
                    qm.start_quest(qid)
            elif action.startswith("complete_quest:"):
                qid = action[15:].strip()
                qm  = getattr(self.app, "quest_manager", None)
                if qm and hasattr(qm, "complete_quest"):
                    qm.complete_quest(qid)
            elif action.startswith("give_item:"):
                parts  = action[10:].split(":")
                iid    = parts[0].strip() if parts else ""
                count  = int(parts[1].strip()) if len(parts) > 1 else 1
                inv    = getattr(getattr(self.app, "player", None), "inventory", None)
                if inv and hasattr(inv, "add"):
                    inv.add(iid, count)
            elif action.startswith("give_gold:"):
                amount = int(action[10:].strip())
                player = getattr(self.app, "player", None)
                if player:
                    player.gold = getattr(player, "gold", 0) + amount
            elif action == "open_shop":
                shop_mgr = getattr(self.app, "shop_manager", None)
                if shop_mgr and hasattr(shop_mgr, "open"):
                    shop_mgr.open(self._npc_id)
        except Exception as exc:
            logger.debug(f"[DialogCinematic] Action error '{action}': {exc}")

    # ─────────────────────────────────────────────────────────────────
    # Game state
    # ─────────────────────────────────────────────────────────────────

    def _enter_dialog_state(self):
        state_mgr = getattr(self.app, "state_mgr", None)
        gs        = getattr(self.app, "GameState", None)
        if state_mgr and gs and hasattr(state_mgr, "set_state"):
            try:
                state_mgr.set_state(gs.DIALOG)
            except Exception:
                pass

    def _exit_dialog_state(self):
        state_mgr = getattr(self.app, "state_mgr", None)
        gs        = getattr(self.app, "GameState", None)
        if state_mgr and gs and hasattr(state_mgr, "set_state"):
            try:
                state_mgr.set_state(gs.PLAYING)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────
    # Cleanup
    # ─────────────────────────────────────────────────────────────────

    def _task_cleanup(self):
        self.app.ignore("space")
        self.app.ignore("e")
        self.app.taskMgr.remove("dialog_start_node")
        self.app.taskMgr.remove("dialog_auto_next")
        self.app.taskMgr.remove("dialog_choices")
        self._destroy_ui()
        self._exit_dialog_state()
        if self._on_end:
            try:
                self._on_end()
            except Exception:
                pass
        self._npc_actor  = None
        self._on_end     = None
        logger.info("[DialogCinematic] Finished.")
