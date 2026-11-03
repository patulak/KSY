"""Render training images: each answer object alone on the table, not occluded.

Run from the repository root with Blender 4.x (base_scene.blend is a Blender 4.2 file);
"blender" = the Blender executable (on PATH, or its full path on your system):
    blender -b base_scene.blend -P webpage/render_training.py

Then convert to WebP for the webpage:
    python webpage/convert_images.py

Uses the table, lighting and HDR from base_scene.blend, hides the book,
appends each model from assets/models/, places it in the middle of the
table top and renders it with its own camera so the whole object is visible.
Output: renders/training/<object>.png
"""

import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(bpy.data.filepath).resolve().parent
OUTPUT_DIR = ROOT / "renders" / "training"

# Database object -> model file in assets/models and its rotation on the table (degrees around Z).
MODELS = {
    "pen": ("fountain-pen-ste_*/*.blend", 110),
    "marker": ("red-whiteboard-m_*/*.blend", 20),
}
SCALE = 7.061              # base_scene objects are ~7x real size (table: 0.72 m -> 5.08 units)
TABLE_CENTER = Vector((0.264, -0.288, 2.084))  # middle of the table top in base_scene
CAMERA_DISTANCE = 2.5
CAMERA_ELEVATION_DEG = 35
RESOLUTION = (1920, 1080)
SAMPLES = 64


def world_bbox(objects) -> tuple[Vector, Vector]:
    points = [o.matrix_world @ Vector(c) for o in objects if o.type == "MESH" and not o.hide_render
              for c in o.bound_box]
    lo = Vector(min(p[i] for p in points) for i in range(3))
    hi = Vector(max(p[i] for p in points) for i in range(3))
    return lo, hi


def append_model(path: Path) -> list:
    with bpy.data.libraries.load(str(path), link=False) as (data_from, data_to):
        data_to.objects = data_from.objects
    for obj in data_to.objects:
        bpy.context.scene.collection.objects.link(obj)
    return data_to.objects


def place(objects, rotation_deg: float) -> None:
    roots = [o for o in objects if o.parent is None]
    for o in roots:
        o.scale = [s * SCALE for s in o.scale]
        o.location = o.location * SCALE
        o.rotation_euler.z += math.radians(rotation_deg)
    bpy.context.view_layer.update()

    # Centre the object on the table, resting on the top.
    lo, hi = world_bbox(objects)
    offset = TABLE_CENTER - Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    for o in roots:
        o.location += offset
    bpy.context.view_layer.update()


def make_camera(target: Vector):
    elevation = math.radians(CAMERA_ELEVATION_DEG)
    camera = bpy.data.objects.new("TrainingCamera", bpy.data.cameras.new("TrainingCamera"))
    camera.location = target + Vector((0, -math.cos(elevation), math.sin(elevation))) * CAMERA_DISTANCE
    bpy.context.scene.collection.objects.link(camera)
    track = camera.constraints.new("TRACK_TO")
    track.target = bpy.data.objects.new("TrainingTarget", None)
    track.target.location = target
    bpy.context.scene.collection.objects.link(track.target)
    track.track_axis, track.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    return camera


def fix_missing_images() -> None:
    """External images saved with another computer's path (e.g. the HDR) -> same file name under assets/."""
    for image in bpy.data.images:
        if image.packed_file or not image.filepath or Path(bpy.path.abspath(image.filepath)).exists():
            continue
        local = next((ROOT / "assets").rglob(Path(image.filepath.replace("\\", "/")).name), None)
        if local:
            image.filepath = str(local)
            image.reload()
            print(f"Relinked {image.name} -> {local}")


def main() -> None:
    fix_missing_images()
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.eevee.taa_render_samples = SAMPLES

    # Hide the occluder (book) – training shows the object on its own.
    for o in bpy.data.objects:
        if "Book" in o.name:
            o.hide_render = True

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, (pattern, rotation) in MODELS.items():
        path = next((ROOT / "assets" / "models").glob(pattern))
        objects = append_model(path)
        place(objects, rotation)

        lo, hi = world_bbox(objects)
        scene.camera = make_camera((lo + hi) / 2)
        scene.render.filepath = str(OUTPUT_DIR / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {scene.render.filepath}")

        for o in objects:
            o.hide_render = True  # keep the scene clean for the next model


if __name__ == "__main__":
    main()
