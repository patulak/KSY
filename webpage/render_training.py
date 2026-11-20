"""Render training images: each object exactly as in its test scene, but without the book.

Run from the repository root with Blender 5.x (the test scenes are Blender 5 files);
"blender" = the Blender executable (on PATH, or its full path on your system):
    blender -b -P webpage/render_training.py              # all objects
    blender -b -P webpage/render_training.py -- pen rake  # only some objects

Then convert to WebP for the webpage:
    python webpage/convert_images.py

For every object this opens its test scene (book_*.blend), hides the book and
zooms the scene camera onto the object by changing only the focal length and
lens shift. The camera stays where it is, so the object keeps the same pose,
perspective, lighting and table as in the test images – just unoccluded and larger.
Output: renders/training/<object>.png
"""

import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "renders" / "training"

# Database object -> test scene it is taken from (any scene of that object works; the pose is the same).
SCENES = {
    "pen": "book_pen_25.blend",
    "marker": "book_marker_10.blend",
    "pencil": "book_pencil.blend",
    "ruler": "book_crayon.blend",
    "hammer": "book_hammer.blend",
    "screwdriver": "book_screwdriver.blend",
    "pliers": "book_pliers.blend",
    "wrench": "book_wrench.blend",
    "spoon": "book_spoon.blend",
    "spatula": "book_spatula.blend",
    "whisk": "book_whisk.blend",
    "tongs": "book_tongs.blend",
    "broom": "book_broom.blend",
    "bucket": "book_mop.blend",
    "rake": "book_rake.blend",
    "shovel": "book_shovel.blend",
}
STATIC_ROOTS = ("Vintage Office Dictionary Book", "Table")  # everything else in the scene is the object
BOOK = "Vintage Office Dictionary Book"
FILL = 0.6                 # object takes up this share of the image width/height
RESOLUTION = (1920, 1080)  # same 16:9 aspect as the test renders
SAMPLES = 64


def fix_missing_images() -> None:
    """External images saved with another computer's path (e.g. the HDR) -> same file name under assets/."""
    for image in bpy.data.images:
        if image.packed_file or not image.filepath or Path(bpy.path.abspath(image.filepath)).exists():
            continue
        local = next((ROOT / "assets").rglob(Path(image.filepath.replace("\\", "/")).name), None)
        if local:
            image.filepath = str(local)
            image.reload()


def object_meshes(scene) -> list:
    roots = [o for o in scene.objects if o.parent is None and o.type in ("MESH", "EMPTY")
             and not o.name.startswith(STATIC_ROOTS)]
    objects = [o for root in roots for o in (root, *root.children_recursive)]
    return [o for o in objects if o.type == "MESH" and not o.hide_render]


def frame_object(scene, meshes) -> None:
    """Zoom the scene camera onto the meshes without moving it (focal length + lens shift)."""
    camera = scene.camera
    points = [world_to_camera_view(scene, camera, o.matrix_world @ Vector(c)) for o in meshes for c in o.bound_box]
    lo_x, hi_x = min(p.x for p in points), max(p.x for p in points)
    lo_y, hi_y = min(p.y for p in points), max(p.y for p in points)

    zoom = FILL / max(hi_x - lo_x, hi_y - lo_y)
    aspect = scene.render.resolution_y / scene.render.resolution_x  # shift is measured in image widths
    data = camera.data
    offset_x = (lo_x + hi_x) / 2 - 0.5 + data.shift_x
    offset_y = ((lo_y + hi_y) / 2 - 0.5) * aspect + data.shift_y
    data.lens *= zoom
    data.shift_x, data.shift_y = offset_x * zoom, offset_y * zoom


def render(name: str, scene_file: str) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / scene_file))
    fix_missing_images()
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.eevee.taa_render_samples = SAMPLES

    for o in bpy.data.objects[BOOK].children_recursive + [bpy.data.objects[BOOK]]:
        o.hide_render = True
    frame_object(scene, object_meshes(scene))

    scene.render.filepath = str(OUTPUT_DIR / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")


def main() -> None:
    wanted = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else list(SCENES)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in wanted:
        render(name, SCENES[name])


if __name__ == "__main__":
    main()
