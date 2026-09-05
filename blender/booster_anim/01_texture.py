"""Paint the plume gradient strips.

One 256x8 RGBA strip per layer.  U runs from the nozzle throat (0) to the tip
of the plume (1); RGB is the flame colour (used as emissive) and A is opacity.
Tiny files, and because they're 1-D there's nothing for mipmapping to smear.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import numpy as np
from PIL import Image


def ramp_rgb(u):
    """Sample the shared flame-temperature ramp at u in [0,1]."""
    ts = [p[0] for p in RAMP]
    out = np.zeros((len(u), 3))
    for c in range(3):
        out[:, c] = np.interp(u, ts, [p[1][c] for p in RAMP])
    return out


def strip(layer):
    a = ALPHA[layer]
    t = (np.arange(TEX_W) + 0.5) / TEX_W

    lo, hi = a["slice"]
    rgb = ramp_rgb(lo + t * (hi - lo))

    # opacity: peak at the throat, power falloff, faded to nothing at the tip
    al = a["peak"] * (1.0 - t) ** a["fall"]
    al *= np.clip(t / 0.035, 0.0, 1.0)          # soften the very first ring
    fade = np.clip((t - 0.72) / 0.28, 0, 1)      # smootherstep out at the tip
    al *= 1.0 - fade ** 3 * (10 - 15 * fade + 6 * fade ** 2)

    # shock diamonds: bright/dark banding in the supersonic first third,
    # spacing widening downstream the way a real underexpanded jet does
    if a["shock"] > 0:
        phase = 2 * np.pi * (t ** 0.72) * 5.2
        band  = 0.5 + 0.5 * np.cos(phase)
        env   = np.exp(-(t / 0.34) ** 2)
        al  *= 1.0 + a["shock"] * (band - 0.35) * env
        rgb *= (1.0 + 0.45 * a["shock"] * (band - 0.5) * env)[:, None]

    px = np.clip(np.concatenate([rgb, al[:, None]], 1), 0, 1)
    px = (px * 255 + 0.5).astype(np.uint8)
    return Image.fromarray(np.repeat(px[None, :, :], 8, axis=0), "RGBA")


for name in PLUME:
    p = os.path.join(WORK, f"plume_{name.lower()}.png")
    strip(name).save(p)
    print("  ", os.path.basename(p))

# spark colour: a single warm ember pixel, no texture needed downstream
print("textures written")
