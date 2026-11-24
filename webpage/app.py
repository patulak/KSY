"""Occluded object test – Flask server.

Run locally:
    python webpage/app.py                 # http://localhost:5000
    python webpage/app.py --host 0.0.0.0  # also reachable from other devices on the network

Experiment settings (test mode, exposure time, zoom, answer type) are the
constants right below the imports.

Flow: intro (language choice, random seed, instructions, images preload) -> for every block
(one category of 4 objects): training page with the 4 objects laid out like the answer
buttons -> one page per trial -> ... -> end.
Every answered trial is appended immediately to results/<participant>.csv
(test mode: results/test_<participant>.csv), so partial data is kept even if
the participant leaves early.
"""

import argparse
import csv
import os
import secrets
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for

from generate_sequence import OBJECT_NAMES, ROOT, build_sequence, load_categories, load_images
from translations import DEFAULT_LANGUAGE, LANGUAGES, UI, item_name

# ---------- Experiment settings ----------
TEST_MODE = 0# True: red test panel, countdowns, slow transitions, Flask debugger. False for real participants.
EXPOSURE_MS = 1000      # how long each image is shown before the answers appear
NEXT_DELAY_S = 2        # test mode only: pause after an answer before the next image
ZOOM_LEVELS = [1, 2]    # each trial gets one of these (balanced, order random per seed); [1] = never zoom
MAX_PER_BLOCK = 30      # at most this many images per block (category) per participant, spread evenly over its objects
MAX_TOTAL = 60          # at most this many images in the whole test per participant (biggest blocks are cut first)
# Rough timing for the test length shown on the intro screen: per image the exposure plus this many
# seconds to answer and move on, plus this many seconds per block for its training screen.
SECONDS_PER_ANSWER = 2.5
SECONDS_PER_TRAINING = 15
ANSWER_MODE = "random"  # "random" = per block, half text / half image (random per participant); or force "text" / "image"
IMAGE_COLORS = "gray"   # "gray" = all images shown in grayscale, "color" = original colours
ITEMS_FILE = "dataset_items.md"  # answer item list, relative to the repository root (also: assets/items.md, alternate_items.md)

RESULTS_DIR = Path(__file__).resolve().parent / "results"
TRAINING_DIR = Path(__file__).resolve().parent / "static" / "images" / "training"
CSV_COLUMNS = [
    "participant", "seed", "language", "age_group", "device", "screen",
    "trial_order", "block", "image_id", "occlusion_percentage", "key_parts_shown",
    "options", "correct_answer", "chosen_answer", "is_correct", "reaction_time_ms", "exposure_ms", "zoom",
    "answer_mode", "colors", "timestamp",
]

# Asked on the intro screen (labels in translations.py). "screen" = screen size in px, filled in automatically.
AGE_GROUPS = ["<20", "20-29", "30-49", "50+"]
DEVICES = ["phone", "tablet", "computer", "other"]

# Test-panel choices (first value = default).
THEMES = ["dark", "light", "contrast"]
VIEWS = ["desktop", "phone"]
ZOOM_CHOICES = ["random", "1", "2"]   # "random" = use the per-trial zoom from the sequence
ANSWER_MODES = ["random", "text", "image"]
COLORS = ["gray", "color"]
TEST_PANEL_KEYS = ("theme", "view", "zoom", "answer_mode", "colors", "exposure_ms", "next_delay_s")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

IMAGES = load_images()
CATEGORIES = load_categories(ROOT / ITEMS_FILE)
# Czech item name -> its training image, for items that have one.
TRAINING_IMAGES = {name: f"images/training/{obj}.webp"
                   for obj, name in OBJECT_NAMES.items() if (TRAINING_DIR / f"{obj}.webp").exists()}


def current_trials() -> list[dict]:
    """The sequence is never stored – it is rebuilt from the seed in the session."""
    return build_sequence(session["seed"], IMAGES, CATEGORIES, ZOOM_LEVELS, MAX_PER_BLOCK, MAX_TOTAL)["trials"]


def duration_minutes(trials: list[dict], exposure_ms: int) -> tuple[int, int]:
    """Estimated test length as a range of whole minutes, e.g. (3, 4). Same formula as docs/app.js."""
    blocks = len({t["block"] for t in trials})
    seconds = len(trials) * (exposure_ms / 1000 + SECONDS_PER_ANSWER) + blocks * SECONDS_PER_TRAINING
    low = max(1, int(seconds // 60))
    return low, low + 1


def setting(key: str, default):
    """Overridable from the test panel in test mode, otherwise the default from the settings above."""
    if TEST_MODE:
        return session.get(key, default)
    return default


def trial_answer_mode(trial: dict) -> str:
    choice = setting("answer_mode", ANSWER_MODE)
    return trial["answer_mode"] if choice == "random" else choice


def trial_zoom(trial: dict) -> int:
    choice = str(setting("zoom", "random"))
    return int(choice) if choice in ZOOM_CHOICES and choice != "random" else trial["zoom"]


@app.context_processor
def template_globals():
    lang = session.get("lang", DEFAULT_LANGUAGE)
    return {
        "lang": lang, "t": UI[lang], "languages": LANGUAGES,
        "item": lambda name: item_name(name, lang),
        "test_mode": TEST_MODE,
        "theme": setting("theme", THEMES[0]), "view": setting("view", VIEWS[0]), "colors": setting("colors", IMAGE_COLORS),
        "zoom_choice": str(setting("zoom", "random")), "answer_mode": setting("answer_mode", ANSWER_MODE),
        "exposure_ms": setting("exposure_ms", EXPOSURE_MS), "next_delay_s": setting("next_delay_s", NEXT_DELAY_S),
        "themes": THEMES, "views": VIEWS, "zoom_choices": ZOOM_CHOICES, "answer_modes": ANSWER_MODES,
        "color_choices": COLORS,
    }


@app.get("/set")
def set_option():
    """Language is always switchable; everything else only in test mode."""
    if request.args.get("lang") in LANGUAGES:
        session["lang"] = request.args["lang"]
    if TEST_MODE:
        choices = (("theme", THEMES), ("view", VIEWS), ("zoom", ZOOM_CHOICES), ("answer_mode", ANSWER_MODES),
                   ("colors", COLORS))
        for key, allowed in choices:
            if request.args.get(key) in allowed:
                session[key] = request.args[key]
        for key, low, high in (("exposure_ms", 50, 10_000), ("next_delay_s", 0, 30)):
            value = request.args.get(key, type=int)
            if value is not None:
                session[key] = max(low, min(high, value))
    return redirect(request.referrer or url_for("intro"))


@app.get("/")
def intro():
    kept = {k: session[k] for k in ("lang", *TEST_PANEL_KEYS) if k in session}
    session.clear()
    session.update(kept)
    session["participant"] = secrets.token_hex(4)
    session["seed"] = secrets.randbelow(1_000_000)
    exposure_s = f"{setting('exposure_ms', EXPOSURE_MS) / 1000:g}"
    trials = current_trials()
    low, high = duration_minutes(trials, setting("exposure_ms", EXPOSURE_MS))
    return render_template("intro.html", trials=trials, exposure_s=exposure_s, minutes_low=low, minutes_high=high,
                           age_groups=AGE_GROUPS, devices=DEVICES)


@app.post("/start")
def start():
    if "seed" not in session:
        return redirect(url_for("intro"))
    age_group, device = request.form.get("age_group"), request.form.get("device")
    if age_group not in AGE_GROUPS or device not in DEVICES:
        return redirect(url_for("intro"))  # the form requires both; only reachable by tampering
    session["age_group"] = age_group
    session["device"] = device
    session["screen"] = request.form.get("screen", "")[:20]
    session["index"] = 0
    session["correct"] = 0
    session["trained_block"] = 0
    session["started_at"] = time.time()
    return redirect(url_for("trial"))


@app.route("/training", methods=["GET", "POST"])
def training():
    """Before each block: its 4 objects, unoccluded, in the same layout as the answer buttons."""
    if "index" not in session:
        return redirect(url_for("intro"))
    trials = current_trials()
    if session["index"] >= len(trials):
        return redirect(url_for("end"))
    t = trials[session["index"]]
    if request.method == "POST":
        session["trained_block"] = t["block"]
        return redirect(url_for("trial"))
    return render_template("training.html", items=t["options"], block=t["block"], blocks=trials[-1]["block"],
                           mode=trial_answer_mode(t), training_images=TRAINING_IMAGES)


@app.route("/trial", methods=["GET", "POST"])
def trial():
    if "index" not in session:
        return redirect(url_for("intro"))
    trials = current_trials()

    # Ignore repeated submits (double click, back button) of an already answered trial.
    if request.method == "POST" and request.form.get("trial") == str(session["index"]):
        t = trials[session["index"]]
        chosen = request.form.get("answer", "")
        is_correct = int(chosen == t["correct"])
        save_row({
            "participant": session["participant"],
            "seed": session["seed"],
            "language": session.get("lang", DEFAULT_LANGUAGE),
            "age_group": session.get("age_group", ""),
            "device": session.get("device", ""),
            "screen": session.get("screen", ""),
            "trial_order": session["index"] + 1,
            "block": t["block"],
            "image_id": t["image_id"],
            "occlusion_percentage": t["occlusion_percentage"],
            "key_parts_shown": t["key_parts_shown"],
            "options": "|".join(t["options"]),
            "correct_answer": t["correct"],
            "chosen_answer": chosen,
            "is_correct": is_correct,
            "reaction_time_ms": request.form.get("rt", ""),
            "exposure_ms": setting("exposure_ms", EXPOSURE_MS),
            "zoom": trial_zoom(t),
            "answer_mode": trial_answer_mode(t),
            "colors": setting("colors", IMAGE_COLORS),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        session["index"] += 1
        session["correct"] += is_correct
        return redirect(url_for("trial"))  # POST -> redirect -> GET, so reload doesn't resubmit

    if session["index"] >= len(trials):
        return redirect(url_for("end"))
    t = trials[session["index"]]
    if session.get("trained_block") != t["block"]:
        return redirect(url_for("training"))  # new block: show its objects first
    return render_template("trial.html", trial=t, index=session["index"], total=len(trials),
                           zoom=trial_zoom(t), mode=trial_answer_mode(t), training_images=TRAINING_IMAGES)


@app.get("/end")
def end():
    if "started_at" not in session:
        return redirect(url_for("intro"))
    return render_template("end.html", correct=session["correct"], total=session["index"],
                           seconds=round(time.time() - session["started_at"]))


def save_row(row: dict) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    prefix = "test_" if TEST_MODE else ""
    path = RESULTS_DIR / f"{prefix}{row['participant']}.csv"
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    # Auto-reload is always on, so edits to the settings above take effect without a manual restart.
    # The interactive debugger (shows code on errors) only in test mode.
    app.run(host=args.host, port=args.port, debug=TEST_MODE, use_reloader=True)

