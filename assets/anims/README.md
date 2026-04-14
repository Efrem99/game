## External Player Animations

Runtime animation sources are controlled by:

- `data/actors/player_animations.json`
- `manifest.strict_runtime_sources = true`
- `manifest.auto_source_dirs` (Mixamo drop folders)

Strict mode still keeps explicit manifest keys authoritative, but auto source dirs
are scanned and merged for missing keys. This allows dropping extra Mixamo clips
without overriding canonical entries.

Default/standard folders:

- `assets/anims/mixamo`
- `assets/anims/mixamo/player`
- `assets/anims/mixamo/hero`

### Mounting naming (canonical keys)

Mount-related keys used by runtime:

- `mounting_horse`, `mounted_idle_horse`, `mounted_move_horse`, `dismounting_horse`
- `mounting_carriage`, `mounted_idle_carriage`, `mounted_move_carriage`, `dismounting_carriage`
- `mounting_boat`, `mounted_idle_boat`, `mounted_move_boat`, `dismounting_boat`

### Mixamo fetch helper

Use:

```bash
python scripts/mixamo_mount_fetch.py --token-env MIXAMO_ACCESS_TOKEN
python scripts/mixamo_player_fetch.py --token-env MIXAMO_ACCESS_TOKEN
```

The helper downloads target clips into this folder and patches manifest paths automatically.

### Auto key aliases (Mixamo-friendly)

Runtime aliasing now recognizes common Mixamo naming patterns:

- `stealth/sneak/crouch` -> `crouch_idle` or `crouch_move`
- `spell/cast prepare` -> `cast_prepare`
- `spell/cast channel` -> `cast_channel`
- `spell/cast release` -> `cast_release`
