#!/usr/bin/env python3
"""Rebuild blender/astronaut_animated.glb from blender/astronaut.glb.

Run with a Python that has Blender available as a module:

    pip install "bpy==4.2.23" pillow numpy     # needs Python 3.11
    python3 booster_anim/build.py

or with Blender itself:

    blender --background --python-expr "import runpy;runpy.run_path('booster_anim/build.py')"

Add --verify to also re-import the finished glb and render _work/preview/loop.gif
(slow: ~3 min on CPU).
"""
import os, subprocess, sys

HERE  = os.path.dirname(os.path.abspath(__file__))
STEPS = ("00_probe.py", "01_texture.py", "02_plumes.py", "03_anim.py", "04_export.py")

for step in STEPS:
    print(f"\n=== {step} ===", flush=True)
    if subprocess.run([sys.executable, os.path.join(HERE, step)]).returncode:
        sys.exit(f"{step} failed")

if "--verify" in sys.argv:
    print("\n=== 05_verify.py ===", flush=True)
    subprocess.run([sys.executable, os.path.join(HERE, "05_verify.py")])

print("\nastronaut_animated.glb rebuilt.")
