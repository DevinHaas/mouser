"""Shared paths + tunables for the chest_animated build."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)              # <repo>/blender
SRC_GLB  = os.path.join(BLENDER_DIR, "chest.glb")
WORK     = os.path.join(HERE, "_work")
OUT_GLB  = os.path.join(BLENDER_DIR, "chest_animated.glb")
os.makedirs(WORK, exist_ok=True)

# --- tunables -------------------------------------------------------------
SEAM      = 0.168     # z of the lid seam on the source mesh
WALL      = 0.030     # interior wall thickness
CAVITY    = 0.20      # cavity depth below the seam (smaller = contents sit higher)
DIV_H     = 0.088     # divider wall height
DIV_T     = 0.012     # divider wall thickness
DIV_AT    = (0.38, 0.66)   # divider positions along the long axis
LID_TOP   = 0.228     # z of the lid's inner panel
ATLAS_W, ATLAS_H = 2048, 2560   # exterior 2048x2048 on top, interior 2048x512 below
TILE_Y    = 2048
FPS       = 24
OPEN_KEYS = [(0, 0.0), (5, -6.0), (26, -105.0), (33, -95.5), (40, -99.0)]  # frame, degrees

# bpy-as-a-module installs need site-packages on the path when run with -S
if not sys.path or '/usr/local/lib/python3.11/dist-packages' not in sys.path:
    pass
