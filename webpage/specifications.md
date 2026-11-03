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
- [x] 4 options (4AFC): the correct object + 3 other items from the **same category** of `assets/items.md`, shuffled.
- [x] End screen with a short summary (correct count, total time).
- [x] No participant ID input – an anonymous random ID is generated.

### Sequence generation
- [x] `generate_sequence.py` builds the sequence; the same seed always gives the same image and answer order.
- [x] The app calls it directly; the CLI can still export `sequences/seed_<seed>.json` (e.g. to give the AI the same trials).
- [x] Database objects map to Czech item names in `OBJECT_NAMES` (pen → Pero, marker → Fix).

### Measurement & storage
- [x] Reaction time is measured in the browser, from the moment the answers appear to the click (ms).
- [x] Total test time is measured.
- [x] Each answered trial is appended immediately to `results/<participant>.csv` on the server (partial data kept).
- CSV columns: `participant, seed, language, trial_order, image_id, occlusion_percentage, key_parts_shown, options, correct_answer, chosen_answer, is_correct, reaction_time_ms, exposure_ms, zoom, answer_mode, timestamp`.
- Answers are always stored by their Czech item name (from `assets/items.md`), whatever language was shown.
- [x] Double-submits / back button cannot record the same trial twice.

### Display
- [x] Czech and English UI; all text and item names live in `translations.py`.
- [x] Zoom into the image centre is applied per trial: each trial gets a level from `ZOOM_LEVELS` (default 1× and 2×), balanced across trials, order random per seed. `[1]` disables it. The zoomed image is cropped to its frame; the level is in the CSV.
- [x] Works on desktop and mobile browsers (responsive layout, large touch targets).
- [x] No participant-controlled zoom – stimulus size should stay as constant as possible (KSY.pdf: constant viewing conditions).
- [x] Colour theme: dark grey base, white / light grey text, one blue accent colour.

### Settings and test mode
- [x] All experiment settings are constants at the top of `app.py`: `TEST_MODE`, `EXPOSURE_MS`, `NEXT_DELAY_S`, `ZOOM_LEVELS`, `ANSWER_MODE`.
- [x] `TEST_MODE = True` turns on the test panel, countdowns and the Flask debugger; `False` turns them off (for real participants). Auto-reload is always on, so saving `app.py` applies changes to a running server.
- [x] Red panel at the top: language, colour theme (dark / light / contrast), desktop / phone view (390 px), zoom (random / 1× / 2×), answer type (text / image), exposure time (ms) and next-image delay (s), restart; shows participant ID and seed.
- [x] Visible countdown of the image exposure; correct answer and image ID shown.
- [x] After answering, the right/wrong answer is highlighted and the next image comes after a countdown (`NEXT_DELAY_S`, changeable in the panel).
- [x] Results are saved as `results/test_<participant>.csv` so they don't mix with real data.

### Performance
- [x] Images are served as WebP, resized to max 1920 px wide (`convert_images.py` → `static/images/`).

### Training images
- [x] `render_training.py` (run inside Blender 4.4 on `base_scene.blend`) renders each answer object alone on the table, no occluder, same lighting/HDR and scale as the test scenes, own camera framing the object.
- [x] Output `renders/training/<object>.png` → `static/images/training/<object>.webp` via `convert_images.py`.
- The test scenes (`book_*.blend`) are Blender 5.0 files, so their exact camera isn't reused.

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
- Training only covers pen and marker; the distractor items (Tužka, Zvýrazňovač, …) have no models, so they have no training image.
- Online hosting: needs a real `SECRET_KEY` env var and persistent storage for `results/`.
