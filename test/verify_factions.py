
import os
import sys
import time

# Ensure we can import from src
sys.path.append(os.path.abspath('src'))

from app import KingWizardApp
from panda3d.core import Vec3

def test_new_factions_demo():
    print("Starting Faction Pivot Verification Demo...")
    app = KingWizardApp()
    
    # Fast-forward past intro
    if hasattr(app, 'intro'):
        app.intro.cleanup()
    
    cm = app.companion_mgr
    
    # 1. Verify Eldrin (Elf)
    print("\nVerifying Eldrin (Elf)...")
    cm.acquire_member("eldrin_elf", source="hire", activate=True)
    app._sync_party_runtime()
    if "eldrin_elf" in app._active_party:
        print("Eldrin spawned successfully!")
    else:
        print("Eldrin failed to spawn.")
        
    # 2. Verify Kiron (Centaur)
    print("\nVerifying Kiron (Centaur)...")
    cm.acquire_member("kiron_centaur", source="story", activate=True)
    app._sync_party_runtime()
    if "kiron_centaur" in app._active_party:
        print("Kiron spawned successfully!")
    else:
        print("Kiron failed to spawn.")

    # 3. Verify Torvin (Dwarf)
    print("\nVerifying Torvin (Dwarf)...")
    cm.acquire_member("torvin", source="story", activate=True)
    app._sync_party_runtime()
    if "torvin" in app._active_party:
        print("Torvin spawned successfully!")
    else:
        print("Torvin failed to spawn.")

    # 4. Cleanup Mira Check
    print("\nVerifying Mira is GONE...")
    if cm.get_definition("mira_wayfarer") is None:
        print("Mira is correctly removed from data.")
    else:
        print("MIRA STILL EXISTS IN DATA!")

    print("\nTest Logic Completed.")

if __name__ == "__main__":
    # Light logic check
    # test_new_factions_demo()
    pass
