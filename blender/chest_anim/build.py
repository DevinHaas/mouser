#!/usr/bin/env python3
"""Rebuild blender/chest_animated.glb from blender/chest.glb.

Run with a Python that has Blender available as a module:

    pip install "bpy==4.2.23" pillow numpy     # needs Python 3.11
    python3 chest_anim/build.py

or with Blender itself:

    blender --background --python-expr "import runpy;runpy.run_path('chest_anim/build.py')"
"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
for step in ("00_split.py", "01_interior.py", "02_paint.py", "03_atlas.py", "04_export.py"):
    print(f"\n=== {step} ===", flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, step)])
    if r.returncode:
        sys.exit(f"{step} failed")
print("\nchest_animated.glb rebuilt.")
