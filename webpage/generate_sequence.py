"""Build a reproducible image sequence for one seed.

The Flask app (app.py) calls build_sequence() with a random seed for every
participant. The command line is for looking at / exporting a sequence,
e.g. to give the AI model exactly the same trials:

    python webpage/generate_sequence.py 42
    python webpage/generate_sequence.py 1 2 3 --out sequences
    python webpage/generate_sequence.py 42 --items alternate_items.md

For each trial the 4 answer options are the correct object plus 3 other
items from the same category of the item list (dataset_items.md by default),
and a zoom level (balanced across trials, random order). The answer order is
shuffled once per seed and then kept for every trial, so an item never moves
to another button position during one participant's test.
The same seed always gives the same sequence.
"""

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATABASE = ROOT / "renders" / "occlusion_database.json"
ITEMS = ROOT / "dataset_items.md"

# Czech name (as written in the item list) of each object in the database.
OBJECT_NAMES = {
    "pen": "Pero",
    "marker": "Fix",
    "pencil": "Tužka",
    "ruler": "Pravítko",
    "hammer": "Kladivo",
    "screwdriver": "Šroubovák",
    "pliers": "Kleště",
    "wrench": "Klíč na matice",
    "spoon": "Lžička",
    "spatula": "Stěrka",
    "whisk": "Metla",
    "tongs": "Kleštičky",
    "broom": "Koště",
    "bucket": "Kbelík",
    "rake": "Hrábě",
    "shovel": "Lopata",
}
OPTIONS_PER_TRIAL = 4
ZOOM_LEVELS = [1, 2]  # default; app.py passes its own setting


def load_images() -> list[dict]:
    return json.loads(DATABASE.read_text(encoding="utf-8"))["images"]


def load_categories(path: Path = ITEMS) -> list[list[str]]:
    """Parse an item list (e.g. assets/items.md) into a list of categories, each a list of item names."""
    categories = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().strip("`")
        if line[:1].isdigit():                      # "3. Psací potřeby"
            categories.append([])
        elif line.startswith("- ") and categories:  # "- Pero (2) – psací hrot, klip"
            categories[-1].append(line[2:].split(" (")[0].strip())
    return categories


def build_sequence(seed: int, images: list[dict], categories: list[list[str]],
                   zoom_levels: list[int] = ZOOM_LEVELS) -> dict:
    rng = random.Random(seed)

    order = images[:]
    rng.shuffle(order)

    # Zoom per trial: every level equally often (as far as the count allows), in random order.
    zooms = [zoom_levels[i % len(zoom_levels)] for i in range(len(order))]
    rng.shuffle(zooms)

    # One answer order per participant: options are always sorted by it, so positions stay fixed.
    answer_order = sorted({item for category in categories for item in category})
    rng.shuffle(answer_order)

    trials = []
    for entry, zoom in zip(order, zooms):
        correct = OBJECT_NAMES[entry["object"]]
        category = next((c for c in categories if correct in c), None)
        if category is None:
            raise ValueError(f"'{correct}' ({entry['id']}) is not in the item list – add it or use another ITEMS_FILE")
        options = rng.sample([o for o in category if o != correct], OPTIONS_PER_TRIAL - 1) + [correct]
        options.sort(key=answer_order.index)
        trials.append({
            "image_id": entry["id"],
            "image": f"images/{entry['id']}.webp",
            "correct": correct,
            "options": options,
            "occlusion_percentage": entry["occlusion_percentage"],
            "key_parts_shown": entry["key_parts_shown"],
            "zoom": zoom,
        })

    return {"seed": seed, "trials": trials}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("seeds", nargs="+", type=int, help="One or more integer seeds.")
    parser.add_argument("--items", type=Path, default=ITEMS, help="Item list (default: dataset_items.md).")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "sequences",
                        help="Output directory for seed_<seed>.json files.")
    args = parser.parse_args()

    args.out.mkdir(exist_ok=True)
    images, categories = load_images(), load_categories(args.items)

    for seed in args.seeds:
        target = args.out / f"seed_{seed}.json"
        target.write_text(json.dumps(build_sequence(seed, images, categories), indent=2, ensure_ascii=False),
                          encoding="utf-8")
        print(f"Wrote {target}")


if __name__ == "__main__":
    main()
