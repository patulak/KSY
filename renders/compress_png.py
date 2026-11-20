"""Losslessly recompress the renders: <name>.png -> <name>_compressed.png (needs ffmpeg on PATH).

Usage (from anywhere; works on Windows and Linux):
    python renders/compress_png.py

Skips files that already have a compressed version and deletes the output
again if it is not smaller than the original.
"""

import shutil
import subprocess
import sys
from pathlib import Path

RENDERS_DIR = Path(__file__).resolve().parent


def main() -> None:
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg not found on PATH")

    for source in sorted(RENDERS_DIR.glob("*.png")):
        if source.stem.endswith("_compressed"):
            continue
        target = source.with_name(f"{source.stem}_compressed.png")
        if target.exists():
            print(f"Skipping (already exists): {source.name}")
            continue

        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(source),
                                 "-c:v", "png", "-compression_level", "9", str(target)])
        if result.returncode != 0 or not target.exists():
            print(f"Failed: {source.name}")
            continue

        old_size, new_size = source.stat().st_size, target.stat().st_size
        if new_size >= old_size:
            target.unlink()
            print(f"No improvement: {source.name}")
        else:
            print(f"{source.name} -> {(1 - new_size / old_size) * 100:.2f}% smaller")


if __name__ == "__main__":
    main()
