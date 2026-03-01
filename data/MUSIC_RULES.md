# Music Routing Rules

Current runtime routing priority:

1. `MAIN_MENU` or `LOADING` state:
- Music: `menu`
- Ambient: off

2. Gameplay states (`PLAYING`, `PAUSED`, `INVENTORY`, `DIALOG`):
- If boss context active (engaged golem boss / boss manager): `boss`
- Else if combat active: `combat`
- Else if location override exists in `location_music`: that track
- Else: `overworld`

Ambient in gameplay:
- Base from `location_ambient` if set
- Else from biome mapping `biome_ambient`
- Hard overrides:
- If player in water: `water`
- Else if player is flying: `wind`

## Debug logging

Audio route changes are logged once per route switch:

- `[Audio] Route -> music='...' ambient='...' reason='...'`

This makes it clear exactly when and why each music track is selected.

## Fade without layering

Config keys in `data/audio/sound_config.json`:

- `music_no_overlap: true` -> fade-out old music, then fade-in new music (no simultaneous music layers)
- `ambient_no_overlap: true` -> same behavior for ambient loop channel
