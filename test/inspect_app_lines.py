with open('src/app.py', 'rb') as f:
    lines = f.readlines()
    print(f"Line 206: {repr(lines[205])}")
    print(f"Line 207: {repr(lines[206])}")
    print(f"Line 208: {repr(lines[207])}")
    print(f"Line 300: {repr(lines[299])}")
