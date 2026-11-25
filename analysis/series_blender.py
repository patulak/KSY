"""Blender helper for measure_series.py (run once):

    blender -b book_pencil.blend -P analysis/series_blender.py

The series renders (renders/<Object>-.../<Object>/0001..0010) use the same camera as book_pencil.blend.
This script writes two files into analysis/:
  * series_book_only.png - the scene with the pencil hidden (clean background for masking)
  * series_planes.json   - table-plane points (at several heights) and their image pixels,
                           used to map image pixels to positions on the table
"""
import json
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

OUT = Path(__file__).resolve().parent
TABLE_Z = 2.091          # table top height in book_pencil.blend
HEIGHTS = [0.0, 0.01, 0.02, 0.03, 0.05, 0.07, 0.08]   # object axis heights above the table

scene = bpy.context.scene
camera = scene.camera
w, h = scene.render.resolution_x, scene.render.resolution_y

planes = {}
for dz in HEIGHTS:
    points = []
    for x in range(-20, 31, 2):
        for y in range(-20, 31, 2):
            p = Vector((x * 0.1, y * 0.1, TABLE_Z + dz))
            v = world_to_camera_view(scene, camera, p)
            points.append([p.x, p.y, v.x * w, (1 - v.y) * h])
    planes[str(dz)] = points
(OUT / "series_planes.json").write_text(json.dumps(planes))

for obj in scene.objects:
    if obj.name == "Pencil":
        obj.hide_render = True
scene.render.filepath = str(OUT / "series_book_only.png")
scene.render.image_settings.file_format = "PNG"
bpy.ops.render.render(write_still=True)
