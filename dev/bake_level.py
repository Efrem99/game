
import sqlite3, msgpack, os, json
from pathlib import Path

ROOT = Path(r"C:/xampp/htdocs/king-wizard")
DEV_DB = ROOT / "dev/dev_editor.sqlite3"
MAIN_DB = ROOT / "cache/data_store.sqlite3"
LAYOUT_JSON = ROOT / "data/world/layout.json"

def bake():
    if not DEV_DB.exists(): return print("No dev db.")
    conn_dev = sqlite3.connect(str(DEV_DB))
    layout = {}
    if MAIN_DB.exists():
        conn_m = sqlite3.connect(str(MAIN_DB))
        row = conn_m.execute("SELECT payload FROM entries WHERE path=?", ("world/layout.json",)).fetchone()
        if row: layout = msgpack.unpackb(row[0], raw=False)
        conn_m.close()
    if not layout and LAYOUT_JSON.exists():
        layout = json.loads(LAYOUT_JSON.read_text(encoding='utf-8'))

    mod = False
    for k, p in conn_dev.execute("SELECT key, payload FROM bridge").fetchall():
        if k.startswith("inspector_feedback"): continue
        d = msgpack.unpackb(p, raw=False)
        eid = d.get("entity_id")
        if not eid: continue
        for cat in ["props", "npcs", "locations"]:
            for item in layout.get(cat, []):
                if str(item.get("id")) == str(eid) or str(item.get("name")) == str(eid):
                    if "pos" in d: item["pos"] = d["pos"]
                    if "hpr" in d: item["hpr"] = d["hpr"]
                    if "scale" in d: item["scale"] = d["scale"]
                    mod = True
                    print(f"Baking {eid}")
        if eid == "terrain" and "heightmap" in d:
            layout.setdefault("terrain", {})["heightmap"] = d["heightmap"]
            mod = True
            print("Baking Terrain heights")
    conn_dev.close()

    if mod:
        packed = msgpack.packb(layout, use_bin_type=True)
        conn_m = sqlite3.connect(str(MAIN_DB))
        conn_m.execute("UPDATE entries SET payload=? WHERE path=?", (sqlite3.Binary(packed), "world/layout.json"))
        conn_m.commit() ; conn_m.close()
        LAYOUT_JSON.write_text(json.dumps(layout, indent=4), encoding='utf-8')
        print("BAKE COMPLETE")

if __name__ == "__main__": bake()
