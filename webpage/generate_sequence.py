"""Build a reproducible image sequence for one seed.

The Flask app (app.py) calls build_sequence() with a random seed for every
participant. The command line is for looking at / exporting a sequence,
e.g. to give the AI model exactly the same trials:

    python webpage/generate_sequence.py 42
    python webpage/generate_sequence.py 1 2 3 --out sequences
    python webpage/generate_sequence.py 42 --items alternate_items.md

For each trial the 4 answer options are the correct object plus 3 other
items from the same category of the item list (dataset_items.md by default),
and a zoom level (balanced across trials, random order). Trials are grouped
into one block per category (block order and order within a block random);
a block with more than MAX_PER_BLOCK images gets a random subset, spread
evenly over the block's objects, and the whole test has at most MAX_TOTAL
images (taken from the biggest blocks first);
each block answers either with names or with images (half of the blocks each).
The answer order is shuffled once per seed and then kept for every trial, so
an item never moves to another button position during one participant's test.
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
MAX_PER_BLOCK = 30    # default; app.py passes its own setting. At most this many images per block (category).
MAX_TOTAL = 60        # default; app.py passes its own setting. At most this many images in the whole test.
ANSWER_MODES = ["text", "image"]  # each block answers in one of these (balanced across blocks, random order)


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


def category_index(entry: dict, categories: list[list[str]]) -> int:
    correct = OBJECT_NAMES[entry["object"]]
    for i, category in enumerate(categories):
        if correct in category:
            return i
    raise ValueError(f"'{correct}' ({entry['id']}) is not in the item list – add it or use another ITEMS_FILE")


def pick_images(group: list[dict], limit: int, rng: random.Random) -> list[dict]:
    """At most `limit` images of one block, spread evenly over its objects.

    Each object's images are shuffled, then taken round-robin (objects in random order), so with
    e.g. 49 images of 4 objects and limit 30 every object gets 7 or 8 and the rest are left out.
    """
    if len(group) <= limit:
        return group[:]
    by_object: dict[str, list[dict]] = {}
    for entry in group:
        by_object.setdefault(entry["object"], []).append(entry)
    queues = list(by_object.values())
    for queue in queues:
        rng.shuffle(queue)
    rng.shuffle(queues)
    picked = []
    while len(picked) < limit:
        for queue in queues:
            if queue and len(picked) < limit:
                picked.append(queue.pop())
    return picked


def build_sequence(seed: int, images: list[dict], categories: list[list[str]],
                   zoom_levels: list[int] = ZOOM_LEVELS, max_per_block: int = MAX_PER_BLOCK,
                   max_total: int = MAX_TOTAL) -> dict:
    rng = random.Random(seed)

    # Trials are grouped by category (one block per category), so the 4 answer buttons stay the
    # same for a whole block. The blocks come in random order, and so do the images within a block.
    blocks: dict[int, list[dict]] = {}
    for entry in images:
        blocks.setdefault(category_index(entry, categories), []).append(entry)
    block_order = sorted(blocks)
    rng.shuffle(block_order)
    # Images per block: at most max_per_block, and together at most max_total. If the total is too
    # high, the biggest block gives up one image at a time, so the blocks end up as even as possible.
    limits = {b: min(len(blocks[b]), max_per_block) for b in block_order}
    while sum(limits.values()) > max_total:
        biggest = max(block_order, key=lambda b: limits[b])
        if limits[biggest] <= 1:
            break  # never drop a whole block
        limits[biggest] -= 1

    order = []
    for b in block_order:
        group = pick_images(blocks[b], limits[b], rng)
        rng.shuffle(group)
        order += group

    # Answer mode per block: text names or images, each used for equally many blocks, in random order.
    modes = [ANSWER_MODES[i % len(ANSWER_MODES)] for i in range(len(block_order))]
    rng.shuffle(modes)

    # Zoom per trial: every level equally often (as far as the count allows), in random order.
    zooms = [zoom_levels[i % len(zoom_levels)] for i in range(len(order))]
    rng.shuffle(zooms)

    # One answer order per participant: options are always sorted by it, so positions stay fixed.
    answer_order = sorted({item for category in categories for item in category})
    rng.shuffle(answer_order)

    trials = []
    for entry, zoom in zip(order, zooms):
        b = category_index(entry, categories)
        correct = OBJECT_NAMES[entry["object"]]
        options = rng.sample([o for o in categories[b] if o != correct], OPTIONS_PER_TRIAL - 1) + [correct]
        options.sort(key=answer_order.index)
        trials.append({
            "image_id": entry["id"],
            "image": f"images/{entry['id']}.webp",
            "correct": correct,
            "options": options,
            "block": block_order.index(b) + 1,
            "answer_mode": modes[block_order.index(b)],
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
