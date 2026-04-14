
import os
import sys
import time

# Ensure we can import from src
sys.path.append(os.path.abspath('src'))

from app import KingWizardApp
from panda3d.core import Vec3

def test_companion_behavior_demo():
    print("Starting Companion Behavior Demo...")
    app = KingWizardApp()
    
    # Fast-forward past intro
    if hasattr(app, 'intro'):
        app.intro.cleanup()
    
    # 1. Force recruit a companion for testing
    cm = app.companion_mgr
    cm.acquire_member("mira_companion", source="hire", activate=True)
    
    # 2. Verify spawning
    app._sync_party_runtime()
    if "mira_companion" in app._active_party:
        print("Mira spawned successfully!")
    else:
        print("Mira failed to spawn.")
    
    # 3. Simulate World Update (Follow)
    player_pos = Vec3(10, 10, 0)
    app.player.actor.setPos(player_pos)
    
    for _ in range(30):
        app._update_party_units(1.0/60.0)
        time.sleep(0.01)
        
    mira = app._active_party["mira_companion"]
    dist = (mira.root.getPos() - player_pos).length()
    print(f"Mira distance to player after follow: {dist:.2f}")

    # 4. Simulate Combat
    # (In a real test we'd spawn an enemy, but here we just check logic)
    print("Simulating combat transition...")
    mira.state = "combat"
    app._update_party_units(0.1)
    
    print("Test Logic Completed.")

if __name__ == "__main__":
    # This is a light logic check before full game run
    # test_companion_behavior_demo()
    pass
