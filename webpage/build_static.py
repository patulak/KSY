"""Build the static (GitHub Pages) version of the experiment into docs/.

    python webpage/build_static.py              # 500 pre-generated sequences
    python webpage/build_static.py --count 1000

The Flask app (app.py) keeps working as before; this only exports what the
static page needs:

- docs/data.json – settings from app.py, translations, item names, training
  images and a pool of sequences (seeds 0 … count-1). Every participant gets
  one sequence picked at random; its seed is saved with every answer, so
  `python webpage/generate_sequence.py <seed>` rebuilds exactly what they saw.
- docs/style.css and docs/images/ – copied from webpage/static/.

Hand-written (not touched by this script): docs/index.html, docs/app.js and
docs/config.js (Google Sheets URL, test mode). Re-run this script after
changing images, the item list, translations or the settings at the top of
app.py, then commit docs/.
"""

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import app as flask_app  # settings, images and item list; importing does not start the server
from generate_sequence import OBJECT_NAMES, build_sequence
from translations import DEFAULT_LANGUAGE, ITEM_NAMES, LANGUAGES, UI

STATIC = Path(__file__).resolve().parent / "static"
DOCS = flask_app.ROOT / "docs"


def build_data(count: int) -> dict:
    images = flask_app.IMAGES
    image_index = {entry["id"]: i for i, entry in enumerate(images)}
    sequences = [build_sequence(seed, images, flask_app.CATEGORIES, flask_app.ZOOM_LEVELS) for seed in range(count)]
    items = sorted({option for seq in sequences for trial in seq["trials"] for option in trial["options"]})
    item_index = {name: i for i, name in enumerate(items)}

    return {
        "build": datetime.now().isoformat(timespec="seconds"),
        "settings": {
            "exposure_ms": flask_app.EXPOSURE_MS,
            "next_delay_s": flask_app.NEXT_DELAY_S,
            "answer_mode": flask_app.ANSWER_MODE,
            "colors": flask_app.IMAGE_COLORS,
            "items_file": flask_app.ITEMS_FILE,
        },
        "choices": {
            "theme": flask_app.THEMES, "view": flask_app.VIEWS, "zoom": flask_app.ZOOM_CHOICES,
            "answer_mode": flask_app.ANSWER_MODES, "colors": flask_app.COLORS,
        },
        "csv_columns": flask_app.CSV_COLUMNS,
        "age_groups": flask_app.AGE_GROUPS,
        "devices": flask_app.DEVICES,
        "languages": LANGUAGES,
        "default_language": DEFAULT_LANGUAGE,
        "ui": UI,
        "item_names": ITEM_NAMES,
        "training_images": flask_app.TRAINING_IMAGES,
        "images": [{
            "id": entry["id"],
            "correct": OBJECT_NAMES[entry["object"]],
            "occlusion_percentage": entry["occlusion_percentage"],
            "key_parts_shown": entry["key_parts_shown"],
        } for entry in images],
        "items": items,
        # Compact: one trial = [image index, zoom, [option indices into "items"], block, answer mode].
        "sequences": [{
            "seed": seq["seed"],
            "trials": [[image_index[t["image_id"]], t["zoom"], [item_index[o] for o in t["options"]],
                        t["block"], t["answer_mode"]]
                       for t in seq["trials"]],
        } for seq in sequences],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=500, help="Number of pre-generated sequences (default 500).")
    args = parser.parse_args()

    DOCS.mkdir(exist_ok=True)
    data = build_data(args.count)
    (DOCS / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    shutil.copy2(STATIC / "style.css", DOCS / "style.css")
    shutil.rmtree(DOCS / "images", ignore_errors=True)   # drop images that no longer exist
    shutil.copytree(STATIC / "images", DOCS / "images")
    (DOCS / ".nojekyll").touch()                          # serve files as they are, no Jekyll build

    # Cache busting: browsers (and GitHub Pages, ~10 min) cache files, so after a rebuild they could mix an
    # old style.css/app.js with the new data.json. A new ?v=… on every build forces the fresh files.
    version = data["build"].replace(":", "").replace("-", "")
    index = DOCS / "index.html"
    html = re.sub(r'(href="style\.css|src="(?:app|config)\.js)(\?v=[^"]*)?"', rf'\1?v={version}"',
                  index.read_text(encoding="utf-8"))
    index.write_text(html, encoding="utf-8")

    size_kb = (DOCS / "data.json").stat().st_size / 1024
    print(f"docs/: {args.count} sequences x {len(data['images'])} trials, data.json {size_kb:.0f} kB")


if __name__ == "__main__":
    main()
