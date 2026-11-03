"""Convert the PNG renders into small WebP files the webpage can load quickly.

Usage (run from the repository root or from webpage/):
    python webpage/convert_images.py
    python webpage/convert_images.py --max-width 1920 --quality 85

Reads every image listed in renders/occlusion_database.json and writes
webpage/static/images/<id>.webp; training renders (renders/training/<object>.png,
from render_training.py) go to webpage/static/images/training/<object>.webp
"""

import argparse
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATABASE = ROOT / "renders" / "occlusion_database.json"
OUTPUT_DIR = Path(__file__).resolve().parent / "static" / "images"
TRAINING_SOURCE = ROOT / "renders" / "training"
TRAINING_OUTPUT = OUTPUT_DIR / "training"


def convert(source: Path, target: Path, max_width: int, quality: int) -> None:
    if not source.exists():
        print(f"MISSING  {source}")
        return

    with Image.open(source) as img:
        img = img.convert("RGB")
        if img.width > max_width:
            new_height = round(img.height * max_width / img.width)
            img = img.resize((max_width, new_height), Image.LANCZOS)
        img.save(target, "WEBP", quality=quality, method=6)

    print(f"OK       {target.name}  ({target.stat().st_size // 1024} KB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-width", type=int, default=1920, help="Resize wider images down to this width (px).")
    parser.add_argument("--quality", type=int, default=85, help="WebP quality 0-100.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    images = json.loads(DATABASE.read_text(encoding="utf-8"))["images"]

    for entry in images:
        convert(ROOT / entry["image_path"], OUTPUT_DIR / f"{entry['id']}.webp", args.max_width, args.quality)

    TRAINING_OUTPUT.mkdir(exist_ok=True)
    for source in sorted(TRAINING_SOURCE.glob("*.png")):
        convert(source, TRAINING_OUTPUT / f"{source.stem}.webp", args.max_width, args.quality)

if __name__ == "__main__":
    main()
