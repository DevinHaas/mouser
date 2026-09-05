"""Shared paths + tunables for the astronaut booster build."""
import os

HERE        = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)                       # <repo>/blender
SRC_GLB     = os.path.join(BLENDER_DIR, "astronaut.glb")
OUT_GLB     = os.path.join(BLENDER_DIR, "astronaut_animated.glb")
WORK        = os.path.join(HERE, "_work")
os.makedirs(WORK, exist_ok=True)

# --- where the thrusters are ---------------------------------------------
# 00_probe.py re-derives these from the mesh and writes _work/nozzles.json.
# These are the fallback / sanity values (Blender space, Z up, model back = -X).
NOZZLE_SEED = [
    {"name": "L", "seed_xy": (-0.113, -0.025)},
    {"name": "R", "seed_xy": (-0.113,  0.048)},
]
PROBE_Z      = (0.125, 0.175)   # z slab the nozzle mouths live in
PROBE_R      = 0.019            # search radius around the seed
RECESS       = 0.010            # start the plume this far *inside* the nozzle

# extra aim applied on top of the measured nozzle axis: pushing the plumes
# back and out keeps them off the legs and reads as a forward-hover burn
AIM          = dict(back_deg=19.0, out_deg=6.0)

# --- plume shape ----------------------------------------------------------
# r(t) and length are in model units; the model is 1.0 unit tall (~1.85 m),
# so 0.01 unit ~= 1.85 cm.  R is the nozzle throat radius from the probe.
PLUME = {
    # r(t) = (r0 + grow*t**gpow) * (1 - t**tpow)**taper * (1 + wave*sin(pi*wf*t))
    # ...times the probed nozzle radius.  Six nested shells: a white-hot dart
    # wrapped in progressively wider, fainter orange sleeves.  Nested at every
    # *world* distance, so the stack accumulates into a soft volumetric falloff
    # instead of reading as a stack of hard-edged cones.
    "Core":  dict(length=0.070, rings=30, sides=24, emit=2.20,
                  r0=0.80, grow=0.22, gpow=1.40, tpow=2.0, taper=0.62, wave=0.07, wf=2.4),
    "Inner": dict(length=0.110, rings=28, sides=26, emit=1.95,
                  r0=0.95, grow=0.70, gpow=0.90, tpow=2.0, taper=0.60, wave=0.05, wf=2.0),
    "Mid":   dict(length=0.160, rings=28, sides=28, emit=1.60,
                  r0=1.12, grow=1.30, gpow=0.85, tpow=2.0, taper=0.60, wave=0.04, wf=1.7),
    "Wash":  dict(length=0.215, rings=26, sides=28, emit=1.30,
                  r0=1.35, grow=2.00, gpow=0.85, tpow=2.0, taper=0.58, wave=0.03, wf=1.4),
    "Veil":  dict(length=0.268, rings=24, sides=28, emit=1.15,
                  r0=1.62, grow=2.70, gpow=0.88, tpow=2.0, taper=0.57, wave=0.02, wf=1.2),
    "Halo":  dict(length=0.318, rings=22, sides=28, emit=1.00,
                  r0=1.95, grow=3.40, gpow=0.90, tpow=2.0, taper=0.56, wave=0.02, wf=1.1),
}
R_FALLBACK = 0.0115

# --- colour ramp (t, r, g, b, a) ------------------------------------------
# One shared "flame temperature" ramp; each layer takes a slice of it and its
# own alpha curve, so core / mid / wash stay in the same family.
RAMP = [
    (0.000, (1.00, 0.94, 0.78)),   # white-hot throat (a very short stretch)
    (0.045, (1.00, 0.82, 0.42)),
    (0.120, (1.00, 0.62, 0.18)),   # bright orange-yellow
    (0.300, (1.00, 0.44, 0.07)),   # orange -- the colour the plume mostly is
    (0.520, (0.98, 0.30, 0.03)),
    (0.750, (0.78, 0.16, 0.02)),   # deep red-orange
    (1.000, (0.30, 0.05, 0.01)),   # ember
]
ALPHA = {                          # peak opacity, falloff exponent, ramp slice
    "Core":  dict(peak=0.92,  fall=0.95, slice=(0.02, 0.62), shock=0.46),
    "Inner": dict(peak=0.50,  fall=1.05, slice=(0.08, 0.72), shock=0.26),
    "Mid":   dict(peak=0.280, fall=1.20, slice=(0.16, 0.84), shock=0.12),
    "Wash":  dict(peak=0.150, fall=1.35, slice=(0.28, 0.92), shock=0.00),
    "Veil":  dict(peak=0.085, fall=1.35, slice=(0.40, 0.97), shock=0.00),
    "Halo":  dict(peak=0.045, fall=1.50, slice=(0.52, 1.00), shock=0.00),
}
TEX_W = 256                        # gradient texture width (t axis)

# --- turbulence (shape keys) ---------------------------------------------
TURB = dict(amp=0.40, lat=0.60, seed=7)   # radial %, lateral sway %, rng seed

# --- sparks ---------------------------------------------------------------
SPARKS      = 5                    # embers per nozzle riding the plume
SPARK_SIZE  = 0.0026
SPARK_EMIT  = 1.55

# --- animation ------------------------------------------------------------
FPS     = 24
FRAMES  = 48                       # 2.00 s seamless loop (frame 0 == frame 48)
CLIP    = "BoosterLoop"
PULSE   = [                        # (cycles per loop, amplitude) per layer
    ("Core",  [(3, 0.105), (5, 0.064), (8, 0.036)]),
    ("Inner", [(3, 0.092), (4, 0.055), (7, 0.030)]),
    ("Mid",   [(2, 0.082), (5, 0.046), (7, 0.028)]),
    ("Wash",  [(2, 0.066), (3, 0.041), (6, 0.023)]),
    ("Veil",  [(2, 0.055), (3, 0.034), (5, 0.020)]),
    ("Halo",  [(1, 0.046), (3, 0.028), (5, 0.016)]),
]
SPIN    = {"Core": 26.0, "Inner": -21.0, "Mid": -15.0,
           "Wash": 11.0, "Veil": -8.0, "Halo": 6.0}   # degrees of roll per loop