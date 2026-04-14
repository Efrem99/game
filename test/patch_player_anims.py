import json
from pathlib import Path

p = Path(r'C:/xampp/htdocs/king-wizard/data/actors/player_animations.json')
with open(p, 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

for source in data.get('manifest', {}).get('sources', []):
    if source.get('key') in ['idle', 'walk', 'run']:
        source['path'] = 'assets/models/xbot/Xbot.glb'

with open(p, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)
print("Updated player_animations.json successfully")
