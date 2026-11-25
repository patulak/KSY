"""Estimate how many mm of each writing-tool series object stick out from under the book.

Needs the outputs of series_blender.py (series_book_only.png, series_planes.json).
Writes series_visible_mm.json: {"unit_mm": ..., "visible_mm": {"book_pen_s01": 126.4, ...}}

Method
  1. Object mask = pixels that differ from the book-only render in colour (shadows mostly only darken,
     so they are left out). The pen is grey steel, so for it large brightness changes count too.
  2. Mask pixels are mapped onto a plane parallel to the table at the object's axis height
     (homography fitted to points projected by the Blender camera).
  3. Visible length = extent of those points along their main axis (PCA), in Blender units.
  4. Units -> mm from the ruler's printed scale: the "1" and "10" cm labels in Ruler frame 10 are 90 mm
     apart. The scene objects are not all to real-world scale, so these are "scene mm" as the ruler
     would read them. Expect roughly +-1 cm error per frame (mask edges, object height, perspective).
"""
import glob
import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HEIGHT = {"Pen": "0.07", "Marker": "0.08", "Pencil": "0.03", "Ruler": "0.01"}   # axis height above table
RULER_LABELS_PX = [[2343.75, 796.25], [2172.5, 751.25]]   # "1" and "10" labels in Ruler/0010


def fit_homography(src, dst):
    rows = []
    for (x, y), (u, v) in zip(src, dst):
        rows += [[-x, -y, -1, 0, 0, 0, u * x, u * y, u], [0, 0, 0, -x, -y, -1, v * x, v * y, v]]
    return np.linalg.svd(np.array(rows))[2][-1].reshape(3, 3)


planes = json.loads((HERE / "series_planes.json").read_text())
H = {k: fit_homography(np.array(v)[:, 2:4] / 1000, np.array(v)[:, 0:2]) for k, v in planes.items()}


def to_plane(xy, dz):
    xy = np.atleast_2d(xy) / 1000
    p = np.c_[xy, np.ones(len(xy))] @ H[dz].T
    return p[:, :2] / p[:, 2:]


a, b = to_plane(RULER_LABELS_PX, "0.01")
unit_mm = 90 / np.linalg.norm(a - b)

bg = np.asarray(Image.open(HERE / "series_book_only.png").convert("RGB"), float)
bg_chroma = bg / (bg.sum(2, keepdims=True) + 1)
visible = {}
for obj, dz in HEIGHT.items():
    files = sorted(glob.glob(str(ROOT / "renders" / f"{obj}-*" / obj / "*.png")))
    for i, f in enumerate(files, 1):
        im = np.asarray(Image.open(f).convert("RGB"), float)
        diff = np.abs(im - bg).sum(2)
        chroma = np.abs(im / (im.sum(2, keepdims=True) + 1) - bg_chroma).sum(2)
        mask = (diff > 60) & (chroma > 0.04)
        if obj == "Pen":
            mask |= (diff > 60) & (np.abs(im.mean(2) - bg.mean(2)) > 70)
        mask[:, :2000] = False      # only the area right of the book
        mask[:400] = False
        mask[1100:] = False
        ys, xs = np.nonzero(mask)
        pts = to_plane(np.c_[xs, ys], dz)
        c = pts - pts.mean(0)
        axis = np.linalg.eigh(c.T @ c)[1][:, -1]
        s = c @ axis
        visible[f"book_{obj.lower()}_s{i:02d}"] = round(float((np.percentile(s, 99.7) - np.percentile(s, 0.3)) * unit_mm), 1)
    print(obj, [visible[f"book_{obj.lower()}_s{i:02d}"] for i in range(1, 11)])

(HERE / "series_visible_mm.json").write_text(json.dumps({"unit_mm": unit_mm, "visible_mm": visible}, indent=1))
