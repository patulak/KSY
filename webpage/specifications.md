# Webpage Specifications

Living list of requirements for the experiment webpage. Update this file with every requested change.
Current state: **minimum viable product** for local testing.

## Requirements

### Content & flow
- [x] Opening the page picks a random seed and builds the image order + answer order from it (server-side).
- [x] Intro screen lets the participant choose the language (Čeština / English) before starting, and explains the task: images are shown briefly, choose which object was hidden, answer quickly and accurately, guess if unsure. All images preload while the participant reads it.
- [x] Training screen between intro and test: each object that has a training render, unoccluded, with its name in the chosen language (so participants learn the answer labels). "Začít test" starts the test from there.
- [x] Each image is shown for **1 s** (`EXPOSURE_MS`), then hidden; the 4 answer options appear.
- [x] Answer type (`ANSWER_MODE`): `text` = item names, `image` = training images on the buttons (items without a training image fall back to their name). Image answers are small tiles (4 in a row, 2 × 2 on narrow screens) and the hidden test image gives up its space, so all answers fit on screen without scrolling.
- [x] 4 options (4AFC): the correct object + 3 other items from the **same category** of the item list (`ITEMS_FILE`, default `dataset_items.md`).
- [x] Answer positions stay fixed during a test: the answer order is shuffled once per participant (seed) and kept for every trial.
- [x] Alternate item list `alternate_items.md` (repo root, same format): replaces items whose names get mixed up (e.g. Zvýrazňovač → Křída, because people call a highlighter "fix"). Switch with `ITEMS_FILE = "alternate_items.md"`.
- [x] End screen with a short summary (correct count, total time).
- [x] No participant ID input – an anonymous random ID is generated.

### Sequence generation
- [x] `generate_sequence.py` builds the sequence; the same seed always gives the same image and answer order.
- [x] The app calls it directly; the CLI can still export `sequences/seed_<seed>.json` (e.g. to give the AI the same trials).
- [x] Expanded dataset: 21 images of 16 objects in `renders/occlusion_database.json`. `dataset_items.md` (repo root) groups exactly these 16 objects into 4 categories of 4 (Psací potřeby, Nářadí, Kuchyňské náčiní, Úklid a zahrada), so every answer option is a real dataset object.
- [x] Database objects map to Czech item names in `OBJECT_NAMES` (`generate_sequence.py`).

### Measurement & storage
- [x] Reaction time is measured in the browser, from the moment the answers appear to the click (ms).
- [x] Total test time is measured.
- [x] Each answered trial is appended immediately to `results/<participant>.csv` on the server (partial data kept).
- CSV columns: `participant, seed, language, trial_order, image_id, occlusion_percentage, key_parts_shown, options, correct_answer, chosen_answer, is_correct, reaction_time_ms, exposure_ms, zoom, answer_mode, colors, timestamp`.
- Answers are always stored by their Czech item name (from `assets/items.md`), whatever language was shown.
- [x] Double-submits / back button cannot record the same trial twice.

### Display
- [x] Czech and English UI; all text and item names live in `translations.py`.
- [x] Zoom into the image centre is applied per trial: each trial gets a level from `ZOOM_LEVELS` (default 1× and 2×), balanced across trials, order random per seed. `[1]` disables it. The zoomed image is cropped to its frame; the level is in the CSV.
- [x] Works on desktop and mobile browsers (responsive layout, large touch targets).
- [x] No participant-controlled zoom – stimulus size should stay as constant as possible (KSY.pdf: constant viewing conditions).
- [x] Colour theme: dark grey base, white / light grey text, one blue accent colour.
- [x] Images are shown in **grayscale by default** (`IMAGE_COLORS = "gray"`; test images, training and answer images). `"color"` shows the originals.

### Settings and test mode
- [x] All experiment settings are constants at the top of `app.py`: `TEST_MODE`, `EXPOSURE_MS`, `NEXT_DELAY_S`, `ZOOM_LEVELS`, `ANSWER_MODE`, `IMAGE_COLORS`, `ITEMS_FILE`.
- [x] `TEST_MODE = True` turns on the test panel, countdowns and the Flask debugger; `False` turns them off (for real participants). Auto-reload is always on, so saving `app.py` applies changes to a running server.
- [x] Red panel at the top: language, colour theme (dark / light / contrast), desktop / phone view (390 px), zoom (random / 1× / 2×), answer type (text / image), images gray / colour (overrides `IMAGE_COLORS`), exposure time (ms) and next-image delay (s), restart; shows participant ID and seed.
- [x] Visible countdown of the image exposure; correct answer and image ID shown.
- [x] After answering, the right/wrong answer is highlighted and the next image comes after a countdown (`NEXT_DELAY_S`, changeable in the panel).
- [x] Results are saved as `results/test_<participant>.csv` so they don't mix with real data.

### Performance
- [x] Images are served as WebP, resized to max 1920 px wide (`convert_images.py` → `static/images/`).

### Training images
- [x] Training images for all 16 objects. `render_training.py` (Blender 5.x) opens each object's test scene (`book_*.blend`, list in `SCENES`), hides the book and zooms the scene camera onto the object by focal length + lens shift only – same pose, perspective, lighting and table as in the test, just unoccluded and larger.
- [x] Output `renders/training/<object>.png` → `static/images/training/<object>.webp` via `convert_images.py`.

### Code
- [x] Python + Flask; HTML via Jinja templates. The only JavaScript is `static/trial.js` (timing + test-mode countdowns).
- [x] All code and comments in English.
- [x] Runs locally (we use the existing `../RPZ/.venv`); can later be hosted for participants on their own devices.
- [x] Cross-platform (Windows + Linux): all paths are built relative to the script files with `pathlib`, no fixed absolute paths, no shell-specific scripts.

## Open questions / not yet implemented
- Occlusion levels in renders (10 %, 25 %) differ from KSY.pdf (0 / 25 / 50 / 75 %); no 0 % baseline yet.
- "Key part visible" condition exists in renders but is not mentioned in KSY.pdf.
- Whether `occlusion_percentage` means covered or visible area is still unverified.
- No consent screen yet.
- The number in the render filenames (`occlusion_percentage`) looks like the *visible* share of the object, not the covered share – verify.
- The 15 new renders use a different (closer, angled) camera than the first 6 renders.
- Online hosting: needs a real `SECRET_KEY` env var and persistent storage for `results/`.
