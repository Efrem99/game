from ui.dialogue_ui import DialogueUI
from managers.runtime_data_access import load_data_recursive
from utils.logger import logger


class DialogueManager:
    """
    Manages loading NPC dialogue trees and driving the DialogueUI overlay.
    """

    def __init__(self, app):
        self.app = app
        self.ui = DialogueUI(app)
        self.active_npc = None
        self._dialogue_data = {}

        # Load dialogue files once during startup.
        self._load_dialogue_data()

    def _load_dialogue_data(self):
        self._dialogue_data = {}

        merged = {}
        for rel_dir in ("npc/dialogue", "dialogues"):
            payload = load_data_recursive(self.app, rel_dir, default={})
            if not isinstance(payload, dict):
                continue
            for key, data in payload.items():
                if not isinstance(data, dict):
                    continue
                source_key = str(key or "").strip()
                npc_key = str(data.get("npc_id", "") or "").strip()
                if source_key:
                    merged[source_key] = data
                if npc_key:
                    merged[npc_key] = data
        self._dialogue_data = merged
        logger.info(f"[DialogueManager] Загружено диалоговых записей: {len(self._dialogue_data)}")

    def start_dialogue(self, npc_id, speaker_name, default_text=None):
        """Begin a dialogue session with an NPC."""
        if self.ui.is_active():
            logger.info("[DialogueManager] Новый диалог не открыт: интерфейс диалога уже активен.")
            return

        self.active_npc = npc_id

        # Pull from data files or use a readable fallback line.
        entry = self._dialogue_data.get(npc_id, {})
        pages = entry.get("pages", [])
        used_fallback = False

        if not pages:
            if default_text:
                pages = [default_text]
            else:
                pages = ["Greetings. I have nothing more to say."]
            used_fallback = True

        logger.info(
            "[DialogueManager] Старт диалога: npc='%s', speaker='%s', pages=%d, fallback=%s",
            npc_id,
            speaker_name,
            len(pages),
            "yes" if used_fallback else "no",
        )

        if hasattr(self.app, "state_mgr"):
            self.app.state_mgr.set_state(self.app.GameState.MENU)

        # Trigger Piper TTS synthesis for the first page.
        if hasattr(self.app, "piper_tts") and pages:
            voice_wav = self.app.piper_tts.synthesize(pages[0], npc_id)
            if voice_wav and hasattr(self.app, "audio"):
                self.app.audio.play_voice_path(voice_wav)

        self.ui.show_dialogue(speaker_name, pages)

    def advance(self):
        """Pass input to UI. If dialogue finishes, clean up state."""
        if not self.ui.is_active():
            return False

        is_still_active = self.ui.advance()

        if is_still_active:
            next_page_idx = self.ui._current_page_idx
            logger.info(
                "[DialogueManager] Переход к следующей реплике: npc='%s', page=%d/%d",
                self.active_npc,
                next_page_idx + 1,
                len(self.ui._current_pages),
            )
            if hasattr(self.app, "piper_tts") and next_page_idx < len(self.ui._current_pages):
                text = self.ui._current_pages[next_page_idx]
                voice_wav = self.app.piper_tts.synthesize(text, self.active_npc)
                if voice_wav and hasattr(self.app, "audio"):
                    self.app.audio.play_voice_path(voice_wav)

        if not is_still_active:
            logger.info(f"[DialogueManager] Диалог завершён: npc='{self.active_npc}'")
            self.active_npc = None
            if hasattr(self.app, "state_mgr") and self.app.state_mgr.current_state == self.app.GameState.MENU:
                self.app.state_mgr.set_state(self.app.GameState.PLAYING)

        return True
