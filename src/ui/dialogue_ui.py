import copy
from direct.gui.DirectGui import DirectFrame, OnscreenText
from panda3d.core import TextNode
from direct.showbase.ShowBaseGlobal import globalClock
from ui.design_system import THEME, title_font, body_font, ParchmentPanel, place_ui_on_top


class DialogueUI:
    def __init__(self, app):
        self.app = app
        self._is_active = False
        self._current_pages = []
        self._current_page_idx = 0
        self._typewriter_progress = 0.0
        self._typewriter_speed = 35.0  # chars per second
        self._full_text = ""
        self._speaker_name = ""

        # Main Layout
        self.root = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-2, 2, -1, 1),
            parent=self.app.aspect2d
        )
        place_ui_on_top(self.root, 95)  # Very high, above HUD

        # Vignette behind the dialogue
        self.backdrop = DirectFrame(
            frameColor=(0, 0, 0, 0.45),
            frameSize=(-2, 2, -0.4, -1.0),
            parent=self.root
        )

        # Parchment background
        self.panel = ParchmentPanel(
            self.app,
            parent=self.root,
            frameSize=(-1.2, 1.2, -0.9, -0.45),
            pos=(0, 0, 0)
        )

        # Speaker Name
        self.speaker_text = OnscreenText(
            text="",
            pos=(-1.12, -0.52),
            scale=0.045,
            fg=THEME["gold_primary"],
            shadow=(0, 0, 0, 0.8),
            font=title_font(self.app),
            align=TextNode.ALeft,
            parent=self.panel,
            mayChange=True
        )

        # Dialogue text body
        self.body_text = OnscreenText(
            text="",
            pos=(-1.12, -0.62),
            scale=0.038,
            fg=THEME["text_main"],
            shadow=(0, 0, 0, 0.7),
            font=body_font(self.app),
            align=TextNode.ALeft,
            wordwrap=55,
            parent=self.panel,
            mayChange=True
        )

        # Continue prompt
        self.prompt_text = OnscreenText(
            text="Press [Enter] or [LMB] to continue...",
            pos=(1.12, -0.85),
            scale=0.03,
            fg=THEME["text_muted"],
            font=body_font(self.app),
            align=TextNode.ARight,
            parent=self.panel,
            mayChange=True
        )

        self.root.hide()

    def show_dialogue(self, speaker_name, pages):
        """Show the dialogue panel with a list of pages (strings)."""
        self._speaker_name = str(speaker_name).strip()
        self._current_pages = list(pages) if isinstance(pages, (list, tuple)) else [str(pages)]
        self._current_page_idx = 0

        self.speaker_text.setText(self._speaker_name)

        if not self._current_pages:
            self.hide_dialogue()
            return

        self._is_active = True
        self.root.show()

        if hasattr(self.app, 'state_mgr'):
            # Ideally switch to a dialogue state here, or disable player input
            pass

        self._load_page(0)
        
        # Start update task
        task_name = "dialogue_typewriter_update"
        self.app.taskMgr.remove(task_name)
        self.app.taskMgr.add(self._update_task, task_name)

    def _load_page(self, idx):
        self._current_page_idx = idx
        self._full_text = self._current_pages[idx]
        self._typewriter_progress = 0.0
        self.body_text.setText("")
        
        if self._current_page_idx < len(self._current_pages) - 1:
            self.prompt_text.setText("Press [Enter] or [LMB] to continue...")
        else:
            self.prompt_text.setText("Press [Enter] or [LMB] to close.")

    def advance(self):
        """Called when user presses Enter or clicks. Returns True if dialogue is still active, False if closed."""
        if not self._is_active:
            return False

        # If still typing, skip to end of page
        if self._typewriter_progress < len(self._full_text):
            self._typewriter_progress = len(self._full_text)
            self.body_text.setText(self._full_text)
            return True

        # Otherwise next page
        next_idx = self._current_page_idx + 1
        if next_idx < len(self._current_pages):
            self._load_page(next_idx)
            return True
        else:
            self.hide_dialogue()
            return False

    def hide_dialogue(self):
        self._is_active = False
        self.root.hide()
        self.app.taskMgr.remove("dialogue_typewriter_update")

    def is_active(self):
        return self._is_active

    def _update_task(self, task):
        if not self._is_active:
            return task.done

        # Handle typewriter effect
        if self._typewriter_progress < len(self._full_text):
            dt = globalClock.getDt()
            self._typewriter_progress += self._typewriter_speed * dt
            
            chars_to_show = int(self._typewriter_progress)
            if chars_to_show > len(self._full_text):
                chars_to_show = len(self._full_text)
                
            self.body_text.setText(self._full_text[:chars_to_show])

        # Pulsate the prompt text if typing is done
        if self._typewriter_progress >= len(self._full_text):
            t = globalClock.getFrameTime()
            alpha = 0.5 + 0.5 * (0.5 + 0.5 * __import__("math").sin(t * 5.0))
            self.prompt_text.setFg((THEME["gold_soft"][0], THEME["gold_soft"][1], THEME["gold_soft"][2], alpha))
        else:
            self.prompt_text.setFg((THEME["text_muted"][0], THEME["text_muted"][1], THEME["text_muted"][2], 1.0))

        return task.cont
