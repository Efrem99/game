import os

path = 'src/managers/npc_manager.py'
with open(path, 'rb') as f:
    lines = f.readlines()

# Line 104 (index 103) - Add Z offset
if b'actor.setPos(x, y, z)' in lines[103]:
    lines[103] = lines[103].replace(b'actor.setPos(x, y, z)', b'actor.setPos(x, y, z + 0.02)')

# Line 765 (index 764) - Ground Height
target_start = b'    def _ground_height(self, x, y, fallback=0.0):'
if target_start in lines[764]:
    new_logic = [
        b'    def _ground_height(self, x, y, fallback=0.0):\r\n',
        b'        # Precise check for Sandbox Ground (Z=5)\r\n',
        b'        world = getattr(self.app, "world", None)\r\n',
        b'        if world and hasattr(world, "world_type") and world.world_type == "ultimate_sandbox":\r\n',
        b'             return 5.0\r\n',
        b'\r\n'
    ]
    # Replace the next few lines that we are overwriting partially or just insert
    # To be safe, we'll replace lines 765-772 (indices 764-771)
    # Original 766: world = getattr(self.app, "world", None)
    # Original 767: if world and hasattr(world, "_th"):
    # ...
    # Original 772: return float(fallback)
    
    # Let's just construct the whole function block
    lines[764:773] = [
        b'    def _ground_height(self, x, y, fallback=0.0):\r\n',
        b'        # Precise check for Sandbox Ground (Z=5)\r\n',
        b'        world = getattr(self.app, "world", None)\r\n',
        b'        if world and hasattr(world, "world_type") and world.world_type == "ultimate_sandbox":\r\n',
        b'             return 5.0\r\n',
        b'\r\n',
        b'        if world and hasattr(world, "_th"):\r\n',
        b'            try:\r\n',
        b'                h = float(world._th(float(x), float(y)))\r\n',
        b'                return h if h > -200 else float(fallback)\r\n',
        b'            except Exception:\r\n',
        b'                pass\r\n',
        b'        return float(fallback)\r\n'
    ]

with open(path, 'wb') as f:
    f.writelines(lines)
print("Patch applied successfully.")
