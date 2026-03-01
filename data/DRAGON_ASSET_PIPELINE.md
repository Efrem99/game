# Dragon Asset Pipeline

The upgraded dragon uses this priority:

1. External model + clips from `data/actors/dragon_animations.json`
2. Procedural high-detail fallback dragon (auto-generated at runtime)

## External Asset Paths

Default expected files:

- `assets/models/dragon/elder_dragon.glb`
- `assets/anims/dragon/dragon_idle.fbx`
- `assets/anims/dragon/dragon_fly_loop.fbx`
- `assets/anims/dragon/dragon_fire_breath.fbx`
- `assets/anims/dragon/dragon_roar.fbx`
- `assets/anims/dragon/dragon_death.fbx`

If these files are missing, the game will still run and use procedural visuals/animation.

## Where to edit

- Dragon runtime behavior: `src/entities/dragon_boss.py`
- Enemy tuning (damage/range/cooldowns/spawn): `data/enemies/dragon.json`
- Animation mapping: `data/actors/dragon_animations.json`
- Dragon state definitions: `data/states/dragon_states.json`

