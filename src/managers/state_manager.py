from enum import Enum

class GameState(Enum):
    MAIN_MENU = 1
    LOADING = 2
    PLAYING = 3
    INVENTORY = 4
    DIALOG = 5
    PAUSED = 6

class StateManager:
    def __init__(self, app):
        self.app = app
        self.current_state = GameState.MAIN_MENU
        self.previous_state = None

    def set_state(self, new_state):
        if new_state == self.current_state:
            return

        print(f"[StateManager] Transitioning from {self.current_state.name} to {new_state.name}")
        self.previous_state = self.current_state
        self.current_state = new_state

        self._on_state_change(self.previous_state, self.current_state)

    def _on_state_change(self, old_state, new_state):
        # Logic to enable/disable UI, pause/resume game, etc.
        if new_state == GameState.PLAYING:
            self.app.disableMouse()
        else:
            self.app.enableMouse()

    def is_playing(self):
        return self.current_state == GameState.PLAYING
