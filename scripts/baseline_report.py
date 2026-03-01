"""Generate a lightweight project baseline report."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INCLUDE_EXT = {".py", ".json", ".md", ".h", ".hpp", ".cpp", ".c", ".glsl", ".vert", ".frag"}
EXCLUDE_DIRS = {".git", "__pycache__", "build", "build-cpp", "logs", "saves"}


def _iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        parts = {p.lower() for p in rel.parts}
        if parts.intersection(EXCLUDE_DIRS):
            continue
        if path.suffix.lower() not in INCLUDE_EXT:
            continue
        yield path


def _count_lines(path):
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return 0
    return len(text.splitlines())


def main():
    files = list(_iter_files())
    total_lines = 0
    per_ext = {}
    top = []

    for path in files:
        lines = _count_lines(path)
        total_lines += lines
        ext = path.suffix.lower()
        per_ext[ext] = per_ext.get(ext, 0) + lines
        top.append((lines, path.relative_to(ROOT).as_posix()))

    top.sort(reverse=True)
    print(f"[Baseline] Files: {len(files)}")
    print(f"[Baseline] Total lines: {total_lines}")
    print("[Baseline] Lines by extension:")
    for ext, lines in sorted(per_ext.items(), key=lambda it: it[1], reverse=True):
        print(f"  {ext}: {lines}")

    print("[Baseline] Top 20 largest files:")
    for lines, rel in top[:20]:
        print(f"  {lines:6d}  {rel}")


if __name__ == "__main__":
    main()
