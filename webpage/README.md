# KSY – Recognition of Partially Occluded Objects (Experiment Webpage)

*Comparing human perception with AI models* — Patrik Kolář, Richard Randák
KSY – Cognitive Systems, Topic 3.1 (summary of [`../KSY.pdf`](../KSY.pdf))

## Purpose of this webpage

This webpage will run the **human part of the experiment**: it shows the rendered
scenes to a participant and records how well and how quickly they recognise the
partially occluded object in each image.

## Experiment summary

### Goal
Compare how well humans and AI models recognise objects from incomplete visual
information, and how recognition accuracy changes as the object becomes more occluded.

### Hypotheses
- **H1:** Recognition accuracy decreases as the degree of occlusion increases.
- **H2:** The rate of that decrease differs between humans and AI.

### Stimuli
- 3D scenes built in **Blender** with common objects (e.g. phone, wallet, mug,
  remote control — currently a pen and a marker), each partly covered by another
  object (currently a book).
- Planned occlusion levels: **O ∈ {0 %, 25 %, 50 %, 75 %}**.
- Lighting, background and camera position stay constant across scenes.
- Roughly **10–20 images** with different objects, scene variants and occlusion levels.
- Rendered images live in [`../renders/`](../renders/) and are described in
  [`../renders/occlusion_database.json`](../renders/occlusion_database.json)
  (object, occluder, occlusion %, whether the object's key part is visible, …).

### Human testing (what this webpage does)
- About **10–20 participants**.
- Each image is shown **briefly**, then the participant picks the correct object
  from **four options (4AFC — four-alternative forced choice)**.
- For every trial we record **correctness** and **reaction time**.
- The **order of images** and the **order of answer options** are randomised.

### AI testing (outside this webpage)
- The same images and answer options are given to a **vision-language model**
  with a single fixed prompt; correctness is recorded for each answer.
- Optionally, an **object detector** is tested and its detection score is measured
  at each occlusion level.

### Evaluation
- Main measure — recognition accuracy:

  `A = N_correct / N_total × 100 %`

- Effect of occlusion and human-vs-AI differences: **logistic regression**, or a
  **mixed-effects logistic model** accounting for differences between participants
  and objects.
- Reaction times are analysed separately.
- Results shown as **accuracy vs. occlusion %** plots and **confusion matrices**
  per object.

### Expected contribution
Compare the robustness of human and machine recognition under incomplete visual
information; procedural scene generation in Blender keeps the experiment reproducible.

## Webpage

Current requirements: see [`specifications.md`](specifications.md).

## How to run (locally)

Works on Windows and Linux. Run the commands from the repository root with any Python 3.10+
environment that has the packages from `requirements.txt` (Flask, Pillow) – we use the existing
`../RPZ/.venv`, so `python` below means:

- Windows: `../RPZ/.venv/Scripts/python`
- Linux / macOS: `../RPZ/.venv/bin/python`

`blender` means the Blender 5.x executable (on PATH, or its full path on your system).

```bash
blender -b -P webpage/render_training.py                     # training renders (only after scene changes)
python webpage/convert_images.py                            # renders -> webpage/static/images/*.webp
python webpage/app.py                                       # open http://localhost:5000
```

Results are written to `webpage/results/<participant>.csv` (git-ignored).
Settings (test mode, exposure time, zoom levels, text/image answers) are the constants at the top of `app.py`.
Set `TEST_MODE = False` before running it with real participants.
`--host 0.0.0.0` makes it reachable from other devices on the same network.

Files: `app.py` (Flask server, flow, saving results), `generate_sequence.py` (seeded order + answer options), `render_training.py` (Blender script for training images),
`translations.py` (all Czech/English text and item names), `templates/` (pages), `static/style.css` (look, colours at the top), `static/trial.js` (timing + test-mode countdowns),
`specifications.md` (current requirements).
