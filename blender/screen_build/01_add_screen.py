
# Fit a clean projectable screen panel onto the Tripo scan and add it as a
# second mesh. The original mesh, material and JPEG atlas pass through
# byte-for-byte; only new accessors/mesh/node/material are appended.
import json, struct, sys
from collections import deque
from pathlib import Path
import numpy as np

RES = 820
RING_PCT = 95.0
RING_GAP = 0.004
OFFSET = 0.0040
INSET = 0.004
AXIS, SIGN, UP = 0, 1, 1          # screen faces +X, device up is +Y

CT = {5120:(np.int8,1),5121:(np.uint8,1),5122:(np.int16,2),
      5123:(np.uint16,2),5125:(np.uint32,4),5126:(np.float32,4)}
NC = {"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}

def load_glb(p):
    raw = Path(p).read_bytes()
    magic, ver, _ = struct.unpack_from("<III", raw, 0)
    assert magic == 0x46546C67 and ver == 2, "not glTF 2.0 binary"
    g, blob, off = None, b"", 12
    while off < len(raw):
        clen, ctype = struct.unpack_from("<II", raw, off)
        d = raw[off+8:off+8+clen]
        if ctype == 0x4E4F534A: g = json.loads(d.decode("utf-8"))
        elif ctype == 0x004E4942: blob = d
        off += 8 + clen + (-clen % 4)
    return g, bytearray(blob)

def write_glb(p, g, blob):
    js = json.dumps(g, separators=(",",":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    bn = bytes(blob) + b"\x00" * (-len(blob) % 4)
    out = struct.pack("<III", 0x46546C67, 2, 12+8+len(js)+8+len(bn))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(bn), 0x004E4942) + bn
    Path(p).write_bytes(out)
    return len(out)

def acc_read(g, blob, i):
    a = g["accessors"][i]
    dt, cs = CT[a["componentType"]]; n = NC[a["type"]]
    v = g["bufferViews"][a["bufferView"]]
    base = v.get("byteOffset",0) + a.get("byteOffset",0)
    stride = v.get("byteStride") or n*cs
    if stride == n*cs:
        return np.frombuffer(bytes(blob), dtype=dt, count=a["count"]*n,
                             offset=base).reshape(a["count"], n).astype(np.float64)
    o = np.zeros((a["count"], n))
    for k in range(a["count"]):
        o[k] = np.frombuffer(bytes(blob), dtype=dt, count=n, offset=base+k*stride)
    return o

def rasterise(pos, tri):
    u, v = [i for i in range(3) if i != AXIS]
    lo = np.array([pos[:,u].min(), pos[:,v].min()])
    hi = np.array([pos[:,u].max(), pos[:,v].max()])
    pad = 0.03*(hi-lo); lo -= pad; hi += pad
    W = RES; H = max(2, int(RES*(hi[1]-lo[1])/(hi[0]-lo[0])))
    P = pos[tri]
    sx = (P[:,:,u]-lo[0])/(hi[0]-lo[0])*(W-1)
    sy = (1-(P[:,:,v]-lo[1])/(hi[1]-lo[1]))*(H-1)
    z = P[:,:,AXIS]*SIGN
    zb = np.full((H,W), -1e9, np.float32); fb = np.full((H,W), -1, np.int64)
    for t in range(len(tri)):
        ax, ay = sx[t], sy[t]
        x0 = int(max(0, np.floor(ax.min()))); x1 = int(min(W-1, np.ceil(ax.max())))
        y0 = int(max(0, np.floor(ay.min()))); y1 = int(min(H-1, np.ceil(ay.max())))
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0,x1+1), np.arange(y0,y1+1))
        d = ((ay[1]-ay[2])*(ax[0]-ax[2]) + (ax[2]-ax[1])*(ay[0]-ay[2]))
        if abs(d) < 1e-9: continue
        w0 = ((ay[1]-ay[2])*(gx-ax[2]) + (ax[2]-ax[1])*(gy-ay[2]))/d
        w1 = ((ay[2]-ay[0])*(gx-ax[2]) + (ax[0]-ax[2])*(gy-ay[2]))/d
        w2 = 1-w0-w1
        m = (w0>=-1e-4)&(w1>=-1e-4)&(w2>=-1e-4)
        if not m.any(): continue
        zz = (w0*z[t,0]+w1*z[t,1]+w2*z[t,2])[m]
        yy, xx = gy[m], gx[m]
        up = zz > zb[yy,xx]
        if not up.any(): continue
        zb[yy[up],xx[up]] = zz[up]; fb[yy[up],xx[up]] = t
    return zb, fb, (lo, hi, W, H)

def flood(zb, fb):
    H, W = zb.shape
    valid = fb >= 0
    ring = np.percentile(zb[valid], RING_PCT)
    body = np.percentile(zb[valid], 40)
    mask = valid & (zb < ring-RING_GAP) & (zb > body-0.05)
    seed = (H//2, W//2)
    if not mask[seed]:
        ys, xs = np.where(mask)
        dd = (ys-seed[0])**2 + (xs-seed[1])**2
        seed = (ys[dd.argmin()], xs[dd.argmin()])
    vis = np.zeros_like(mask); vis[seed] = True; q = deque([seed])
    while q:
        cy, cx = q.popleft()
        for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
            ny, nx = cy+dy, cx+dx
            if 0 <= ny < H and 0 <= nx < W and mask[ny,nx] and not vis[ny,nx]:
                vis[ny,nx] = True; q.append((ny,nx))
    return vis

def max_rect(mask):
    H, W = mask.shape
    h = np.zeros(W, dtype=int); best = (0, None)
    for r in range(H):
        h = np.where(mask[r], h+1, 0); st = []
        for c in range(W+1):
            cur = h[c] if c < W else 0; start = c
            while st and st[-1][1] >= cur:
                s, hh = st.pop()
                if hh*(c-s) > best[0]: best = (hh*(c-s), (r-hh+1, r, s, c-1))
                start = s
            st.append((start, cur))
    return best[1]

def append(g, blob, arr, ctype, typ, target):
    while len(blob) % 4: blob.append(0)
    off = len(blob); blob.extend(arr.tobytes())
    g["bufferViews"].append({"buffer":0,"byteOffset":off,
                             "byteLength":len(arr.tobytes()),"target":target})
    a = {"bufferView":len(g["bufferViews"])-1,"componentType":ctype,
         "count":int(len(arr)),"type":typ}
    if typ != "SCALAR":
        a["min"] = [float(x) for x in arr.min(axis=0)]
        a["max"] = [float(x) for x in arr.max(axis=0)]
    else:
        a["min"] = [int(arr.min())]; a["max"] = [int(arr.max())]
    g["accessors"].append(a)
    return len(g["accessors"])-1

def run(src, dst):
    g, blob = load_glb(src)
    prim = g["meshes"][0]["primitives"][0]
    pos = acc_read(g, blob, prim["attributes"]["POSITION"])[:, :3]
    tri = acc_read(g, blob, prim["indices"]).ravel().astype(np.int64).reshape(-1,3)
    print("source: %d verts, %d tris" % (len(pos), len(tri)))

    zb, fb, (lo, hi, W, H) = rasterise(pos, tri)
    vis = flood(zb, fb)
    print("glass pixels: %d" % vis.sum())
    y0, y1, x0, x1 = max_rect(vis)
    u, v = [i for i in range(3) if i != AXIS]
    to_u = lambda px: lo[0] + px/(W-1)*(hi[0]-lo[0])
    to_v = lambda py: lo[1] + (1-py/(H-1))*(hi[1]-lo[1])
    umin, umax = sorted([to_u(x0), to_u(x1)]); umin += INSET; umax -= INSET
    vmin, vmax = sorted([to_v(y1), to_v(y0)]); vmin += INSET; vmax -= INSET

    faces = np.unique(fb[vis]); faces = faces[faces >= 0]
    verts = np.unique(tri[faces].ravel()); P = pos[verts]
    ins = (P[:,u]>umin)&(P[:,u]<umax)&(P[:,v]>vmin)&(P[:,v]<vmax)
    depth = P[ins, AXIS] if ins.sum() > 20 else P[:, AXIS]
    plane = float(np.percentile(depth, 50))
    place = float(np.percentile(depth, 99.5)) + OFFSET
    print("glass plane x=%.4f  panel x=%.4f  sd=%.5f" % (plane, place, np.std(depth)))

    lim = {u:(umin,umax), v:(vmin,vmax)}
    up_lo, up_hi = lim[UP]
    right = u if UP == v else v
    fwd = np.zeros(3); fwd[AXIS] = -SIGN
    upv = np.zeros(3); upv[UP] = 1.0
    rv = np.cross(fwd, upv)
    r_lo, r_hi = lim[right]
    r0, r1 = (r_lo, r_hi) if rv[right] > 0 else (r_hi, r_lo)
    print("panel %.4f x %.4f  aspect %.3f" % (abs(r1-r0), up_hi-up_lo,
          abs(r1-r0)/(up_hi-up_lo)))

    QP, QT = [], []
    for j in range(2):
        for i in range(2):
            s, t = float(i), float(j)
            p = np.zeros(3); p[AXIS] = place
            p[right] = r0 + (r1-r0)*s
            p[UP] = up_hi + (up_lo-up_hi)*t
            QP.append(p); QT.append([s,t])
    QP = np.array(QP, np.float32); QT = np.array(QT, np.float32)
    I = np.array([0,2,1,1,2,3], np.uint16)
    n0 = np.cross(QP[I[1]]-QP[I[0]], QP[I[2]]-QP[I[0]])
    if n0[AXIS]*SIGN < 0:
        I = I.reshape(-1,3)[:, ::-1].ravel().astype(np.uint16)
    N = np.zeros_like(QP); N[:, AXIS] = SIGN

    ip = append(g, blob, QP, 5126, "VEC3", 34962)
    inr = append(g, blob, N, 5126, "VEC3", 34962)
    it = append(g, blob, QT, 5126, "VEC2", 34962)
    ii = append(g, blob, I, 5123, "SCALAR", 34963)
    g.setdefault("materials", []).append({
        "name":"Screen_Display",
        "pbrMetallicRoughness":{"baseColorFactor":[0.02,0.02,0.025,1.0],
                                "metallicFactor":0.0,"roughnessFactor":0.35},
        "emissiveFactor":[0.0,0.0,0.0],"doubleSided":False})
    g["meshes"].append({"name":"Screen","primitives":[{
        "attributes":{"POSITION":ip,"NORMAL":inr,"TEXCOORD_0":it},
        "indices":ii,"material":len(g["materials"])-1}]})
    g["nodes"].append({"name":"Screen","mesh":len(g["meshes"])-1})
    g["scenes"][g.get("scene",0)]["nodes"].append(len(g["nodes"])-1)
    g["buffers"][0]["byteLength"] = len(blob) + (-len(blob) % 4)
    size = write_glb(dst, g, blob)
    print("wrote %s (%.2f MB)" % (dst, size/1e6))
