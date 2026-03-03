# Shervard Hero Asset Slot

Put exported hero files here:

- `sherward.glb` (required for runtime hero replacement)
- `textures/sherward_albedo.png` (optional)
- `textures/sherward_normal.png` (optional)
- `textures/sherward_roughness.png` (optional)
- `textures/sherward_metallic.png` (optional)
- `textures/sherward_ao.png` (optional)

Runtime config currently checks:
- `data/actors/player.json` -> `player.model` / `player.model_candidates`

If `sherward.glb` is missing, runtime falls back to:
- `assets/models/xbot/Xbot.glb`
