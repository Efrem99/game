
import os

app_path = r"C:/xampp/htdocs/king-wizard/src/app.py"

if os.path.exists(app_path):
    with open(app_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    updated = False
    for i, line in enumerate(lines):
        if '"dwarven_caves_throne": Vec3(102.0, -24.0, 0.0)' in line:
            if '"ultimate_sandbox"' not in lines[i+1] and '"ultimate_sandbox"' not in line:
                lines.insert(i+1, '            "ultimate_sandbox": Vec3(150.0, 150.0, 5.0),\n')
                updated = True
                print("Patched app.py spawn locations via line search")
            break
    
    if updated:
        with open(app_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    else:
        print("Failed to find line or already patched")
