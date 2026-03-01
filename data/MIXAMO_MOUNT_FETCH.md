# Mixamo Mount Fetch

This project has a helper script:

`scripts/mixamo_mount_fetch.py`

It fetches mount/riding clips from Mixamo API and updates:

- `assets/anims/*`
- `data/actors/player_animations.json`

## 1) Get access token from browser

1. Open `https://www.mixamo.com/` and log in.
2. Open DevTools (`F12`) -> `Console`.
3. Run:

```js
localStorage.getItem("access_token")
```

4. Copy token value.

## 2) Run fetch

PowerShell:

```powershell
$env:MIXAMO_ACCESS_TOKEN="<paste token>"
python scripts/mixamo_mount_fetch.py --token-env MIXAMO_ACCESS_TOKEN
```

If Mixamo returns `429 Too Many Requests`, rerun with slower pacing:

```powershell
python scripts/mixamo_mount_fetch.py --token-env MIXAMO_ACCESS_TOKEN --request-delay-sec 2.5 --max-retries 8
```

Dry run (no downloads, no manifest patch):

```powershell
python scripts/mixamo_mount_fetch.py --token-env MIXAMO_ACCESS_TOKEN --dry-run
```

Subset fetch:

```powershell
python scripts/mixamo_mount_fetch.py --token-env MIXAMO_ACCESS_TOKEN --only mounting_horse,mounted_move_horse
```

## Notes

- Default character id is Mixamo XBot.
- Script resolves best candidate per target using query fallbacks.
- If a target fails to resolve, current manifest entries stay unchanged.
