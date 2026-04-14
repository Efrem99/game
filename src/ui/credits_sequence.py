
from direct.gui.DirectGui import DirectFrame, OnscreenText
from panda3d.core import TextNode
from ui.design_system import THEME, title_font, body_font, place_ui_on_top

class CreditsSequence:
    def __init__(self, app):
        self.app = app
        self.root = DirectFrame(
            frameColor=(0.02, 0.01, 0.01, 1.0),
            frameSize=(-2, 2, -1, 1),
            parent=self.app.aspect2d
        )
        place_ui_on_top(self.root, 100)
        
        self.credits_list = [
            ("GAME COMPLETED", 0.12, THEME["gold_primary"], title_font(app)),
            ("THANK YOU FOR PLAYING", 0.05, THEME["text_main"], body_font(app)),
            ("", 0.05, THEME["text_main"], body_font(app)),
            ("KING WIZARD", 0.08, THEME["gold_soft"], title_font(app)),
            ("A Premium RPG Experience", 0.04, THEME["text_muted"], body_font(app)),
            ("", 0.05, THEME["text_main"], body_font(app)),
            ("DEVELOPED BY", 0.04, THEME["text_muted"], body_font(app)),
            ("ANTIGRAVITY AI", 0.06, THEME["gold_primary"], title_font(app)),
            ("", 0.05, THEME["text_main"], body_font(app)),
            ("DIRECTOR", 0.04, THEME["text_muted"], body_font(app)),
            ("User", 0.06, THEME["text_main"], body_font(app)),
            ("", 0.05, THEME["text_main"], body_font(app)),
            ("ART & LEVEL DESIGN", 0.04, THEME["text_muted"], body_font(app)),
            ("Procedural Magic Engine", 0.05, THEME["text_main"], body_font(app)),
            ("", 0.05, THEME["text_main"], body_font(app)),
            ("SPECIAL THANKS", 0.04, THEME["text_muted"], body_font(app)),
            ("The Google Deepmind Team", 0.05, THEME["text_main"], body_font(app)),
            ("All The Brave Wizards", 0.05, THEME["text_main"], body_font(app)),
            ("", 0.2, THEME["text_main"], body_font(app)),
            ("FIN", 0.15, THEME["gold_primary"], title_font(app)),
        ]
        
        self.nodes = []
        self._scroll_y = -1.2
        self._is_active = False
        
        self._create_content()
        self.root.hide()

    def _create_content(self):
        curr_y = 0.0
        for text, scale, color, font in self.credits_list:
            if text:
                node = OnscreenText(
                    text=text,
                    pos=(0, curr_y),
                    scale=scale,
                    fg=color,
                    shadow=(0, 0, 0, 0.8),
                    align=TextNode.ACenter,
                    parent=self.root,
                    font=font,
                    mayChange=False
                )
                self.nodes.append((node, curr_y))
            curr_y -= (scale * 2.2)

    def start(self):
        self._is_active = True
        self._scroll_y = -1.2
        self.root.show()
        # Mute game music if needed
        if hasattr(self.app, "audio"):
            try:
                self.app.audio.play_music("credits", volume=0.8, loop=False)
            except:
                pass

    def stop(self):
        self._is_active = False
        self.root.hide()

    def update(self, dt):
        if not self._is_active:
            return
            
        self._scroll_y += dt * 0.16
        for node, orig_y in self.nodes:
            y = orig_y + self._scroll_y
            node.setPos(0, y)
            
            # Fade based on position
            alpha = 1.0
            if y > 0.8:
                alpha = max(0.0, 1.0 - (y - 0.8) * 5.0)
            elif y < -0.8:
                alpha = max(0.0, 1.0 - (-0.8 - y) * 5.0)
            node.setFg((node.getFg()[0], node.getFg()[1], node.getFg()[2], alpha))

        if self._scroll_y > 4.5:
            # End of credits
            self.stop()
            if hasattr(self.app, "on_credits_finished"):
                self.app.on_credits_finished()
