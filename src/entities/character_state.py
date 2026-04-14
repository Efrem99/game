from panda3d.core import Vec3

class CharacterState:
    """Python fallback for CharacterState when game_core.pyd is missing."""
    def __init__(self):
        self.health = 100.0
        self.maxHealth = 100.0
        self.stamina = 100.0
        self.maxStamina = 100.0
        self.mana = 100.0
        self.maxMana = 100.0
        self.position = Vec3(0, 0, 0)
        self.velocity = Vec3(0, 0, 0)
        self.alive = True

    def __repr__(self):
        return f"<CharacterState HP={self.health}/{self.maxHealth}>"
