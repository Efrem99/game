## External Player Animations

Runtime animation sources are controlled by:

- `data/actors/player_animations.json`
- `manifest.strict_runtime_sources = true`

That means clips are loaded from explicit manifest entries only.
Dropping files here is not enough until the manifest is updated.

### Mounting naming (canonical keys)

Mount-related keys used by runtime:

- `mounting_horse`, `mounted_idle_horse`, `mounted_move_horse`, `dismounting_horse`
- `mounting_carriage`, `mounted_idle_carriage`, `mounted_move_carriage`, `dismounting_carriage`
- `mounting_boat`, `mounted_idle_boat`, `mounted_move_boat`, `dismounting_boat`

### Mixamo fetch helper

Use:

```bash
python scripts/mixamo_mount_fetch.py --token-env MIXAMO_ACCESS_TOKEN
```

The helper downloads target clips into this folder and patches manifest paths automatically.
