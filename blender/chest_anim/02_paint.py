import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import *
import math, random, json
from PIL import Image, ImageDraw, ImageFilter, ImageChops
random.seed(7)
TW,TH=2048,512
REG = {   # x0,y0,x1,y1 inside tile
 "A":(8,8,748,504),      # tray floor + contents
 "B":(756,8,1496,504),   # lid inner panel
 "C":(1504,8,2040,260),  # inner walls
 "D":(1504,268,1772,504),# rim / metal
 "E":(1780,268,2040,504),# divider walls
}
col=Image.new("RGB",(TW,TH),(20,22,25))
emi=Image.new("RGB",(TW,TH),(0,0,0))
dc=ImageDraw.Draw(col); de=ImageDraw.Draw(emi)

def noise(size, amt=14, seed=1):
    r=random.Random(seed)
    n=Image.new("L",(size[0]//4 or 1,size[1]//4 or 1))
    n.putdata([r.randint(128-amt,128+amt) for _ in range(n.width*n.height)])
    return n.resize(size, Image.BICUBIC)

import numpy as _np
def grain(img, box, amt=12, seed=3):
    x0,y0,x1,y1=box; w,h=x1-x0,y1-y0
    n=_np.asarray(noise((w,h),amt,seed)).astype(_np.int16)-128
    reg=_np.asarray(img.crop(box)).astype(_np.int16)
    reg=_np.clip(reg+n[:,:,None],0,255).astype(_np.uint8)
    img.paste(Image.fromarray(reg),box)

def lerp(a,b,t): return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))

def vgrad(draw, box, c0, c1, horiz=False):
    x0,y0,x1,y1=box
    if horiz:
        for x in range(x0,x1): draw.line([(x,y0),(x,y1)], fill=lerp(c0,c1,(x-x0)/max(1,x1-x0-1)))
    else:
        for y in range(y0,y1): draw.line([(x0,y),(x1,y)], fill=lerp(c0,c1,(y-y0)/max(1,y1-y0-1)))

def radial(img, cx,cy,r, inner, outer, alpha=1.0):
    s=Image.new("RGB",(2*r,2*r),outer); d=ImageDraw.Draw(s)
    for i in range(r,0,-1):
        t=i/r
        d.ellipse([r-i,r-i,r+i,r+i], fill=lerp(inner,outer,t**1.6))
    m=Image.new("L",(2*r,2*r),0); ImageDraw.Draw(m).ellipse([0,0,2*r-1,2*r-1],fill=int(255*alpha))
    m=m.filter(ImageFilter.GaussianBlur(r*0.18))
    img.paste(s,(cx-r,cy-r),m)

# ---------------- A : tray floor with contents ----------------
ax0,ay0,ax1,ay1=REG["A"]; AW,AH=ax1-ax0,ay1-ay0
dc.rectangle(REG["A"], fill=(26,28,31))
# divider positions along tile-x  (t of inner-y range)
DT=[0.38,0.66]; DWpx=10
comp=[(ax0, ax0+int(AW*DT[0])), (ax0+int(AW*DT[0]), ax0+int(AW*DT[1])), (ax0+int(AW*DT[1]), ax1)]
for (cx0,cx1) in comp:
    vgrad(dc,(cx0+4,ay0+4,cx1-4,ay1-4),(38,40,44),(22,24,27))
    grain(col,(cx0+4,ay0+4,cx1-4,ay1-4),10,random.randint(1,999))
    # inset AO
    for i in range(16):
        t=i/16; a=int(70*(1-t))
        dc.rectangle([cx0+4+i,ay0+4+i,cx1-5-i,ay1-5-i], outline=(a//4,a//4,a//4+2))

grain(col,REG["A"],8,42)
# --- compartment 1: cyan orb devices
c0,c1=comp[0]
orbs=[(0.30,0.20,58),(0.70,0.26,54),(0.24,0.55,56),(0.66,0.62,52),(0.45,0.85,50)]
for (u,v,r) in orbs:
    ox=int(c0+ (c1-c0)*u); oy=int(ay0+AH*v)
    # dark body / housing
    dc.ellipse([ox-r-8,oy-r-8,ox+r+8,oy+r+8], fill=(30,34,38))
    dc.ellipse([ox-r-3,oy-r-3,ox+r+3,oy+r+3], fill=(52,58,64), outline=(78,86,94), width=3)
    # segmented ring
    for k in range(8):
        a0=k*45+6; a1=a0+33
        dc.arc([ox-r+4,oy-r+4,ox+r-4,oy+r-4], a0,a1, fill=(96,106,116), width=6)
    radial(col, ox,oy, int(r*0.72), (235,255,255),(10,110,130))
    radial(emi, ox,oy, int(r*0.95), (150,255,255),(0,25,32))
    dc.ellipse([ox-r*0.28,oy-r*0.40,ox+r*0.02,oy-r*0.10], fill=(255,255,255))
# --- compartment 2: orange crystal cluster
c0,c1=comp[1]
mx=(c0+c1)//2; my=ay0+AH//2
dc.rectangle([c0+10,ay0+10,c1-10,ay1-10], fill=(30,25,22))
random.seed(11)
# dense cluster of coral shards, larger in the middle
cl=[]
for i in range(70):
    a=random.uniform(0,math.pi*2); rr=random.random()**0.55
    sx=mx+math.cos(a)*(c1-c0)*0.36*rr
    sy=my+math.sin(a)*AH*0.40*rr
    ln=random.uniform(46,120)*(1.15-0.45*rr); wd=random.uniform(16,34)*(1.1-0.35*rr)
    ang=random.uniform(-0.55,0.55)+ (0 if random.random()<0.75 else random.uniform(-1.4,1.4))
    cl.append((sy,sx,sy,ln,wd,ang,rr))
cl.sort()
for (_,sx,sy,ln,wd,ang,rr) in cl:
    ca,sa=math.cos(ang),math.sin(ang)
    def P(dx,dy): return (sx+dx*ca-dy*sa, sy+dx*sa+dy*ca)
    tip=P(0,-ln*0.62); ml=P(-wd*0.5,-ln*0.06); mr=P(wd*0.5,-ln*0.06)
    bl=P(-wd*0.42,ln*0.38); br=P(wd*0.42,ln*0.38)
    base=(232,112,58); top=(255,196,132); dark=(158,58,28)
    dc.polygon([tip,mr,br,bl,ml], fill=base, outline=(126,44,18))
    dc.polygon([tip,ml,bl], fill=lerp(base,top,0.6))
    dc.polygon([tip,mr,br], fill=lerp(base,dark,0.45))
    dc.line([tip,P(0,ln*0.3)], fill=lerp(top,(255,255,255),0.4), width=2)
    de.polygon([tip,mr,br,bl,ml], fill=(150,58,18))
    de.polygon([tip,ml,bl], fill=(205,96,32))
emi.paste(emi.crop((c0,ay0,c1,ay1)).filter(ImageFilter.GaussianBlur(7)),(c0,ay0))
# --- compartment 3: PCB stacks
c0,c1=comp[2]
random.seed(23)
for s in range(4):
    off=s*7
    bx0,by0=c0+26+off, ay0+40+off*2
    bx1,by1=c1-26+off//2, ay0+AH//2-10+off*2
    dc.rectangle([bx0+4,by0+4,bx1+4,by1+4], fill=(12,14,13))
    dc.rectangle([bx0,by0,bx1,by1], fill=(22,58,34), outline=(10,28,16), width=3)
    for i in range(9):
        yy=by0+8+i*((by1-by0-16)//8)
        dc.line([(bx0+8,yy),(bx1-8,yy)], fill=(168,140,60), width=2)
    for i in range(6):
        px=random.randint(bx0+14,bx1-40); py=random.randint(by0+10,by1-24)
        dc.rectangle([px,py,px+random.randint(18,34),py+random.randint(10,18)], fill=(18,18,20), outline=(60,60,64))
    for i in range(14):
        px=random.randint(bx0+8,bx1-10); py=random.randint(by0+6,by1-8)
        dc.ellipse([px,py,px+4,py+4], fill=(198,168,80))
for s in range(3):
    off=s*7
    bx0,by0=c0+30+off, ay0+AH//2+16+off*2
    bx1,by1=c1-22+off//2, ay1-32+off*2
    dc.rectangle([bx0+4,by0+4,bx1+4,by1+4], fill=(12,14,13))
    dc.rectangle([bx0,by0,bx1,by1], fill=(26,64,38), outline=(10,28,16), width=3)
    for i in range(8):
        yy=by0+8+i*max(1,(by1-by0-16)//7)
        dc.line([(bx0+8,yy),(bx1-8,yy)], fill=(178,148,66), width=2)
    for i in range(5):
        px=random.randint(bx0+14,max(bx0+15,bx1-40)); py=random.randint(by0+10,max(by0+11,by1-24))
        dc.rectangle([px,py,px+26,py+14], fill=(18,18,20), outline=(60,60,64))
# divider shadows over floor
for t in DT:
    dx=ax0+int(AW*t)
    dc.rectangle([dx-DWpx//2,ay0,dx+DWpx//2,ay1], fill=(30,32,36))
    for i in range(22):
        a=int(120*(1-i/22))
        dc.line([(dx+DWpx//2+i,ay0),(dx+DWpx//2+i,ay1)], fill=(a//6,a//6,a//6+2))

# ---------------- B : lid inner panel (teal -> magenta) ----------------
bx0,by0,bx1,by1=REG["B"]; BW,BH=bx1-bx0,by1-by0
import numpy as np2
_gx=np2.linspace(0,1,BW)[None,:,None]
_c0=np2.array([26,150,162],dtype=np2.float32); _c1=np2.array([186,70,150],dtype=np2.float32)
_g=(_c0*(1-_gx)+_c1*_gx)
_gy=np2.linspace(1.0,0.62,BH)[:,None,None]
_g=np2.clip(_g*_gy,0,255).astype(np2.uint8)
_g=np2.repeat(_g,BH,axis=0) if _g.shape[0]==1 else _g
col.paste(Image.fromarray(np2.broadcast_to(_g,(BH,BW,3)).copy()),(bx0,by0))
# darker recessed frame
for i in range(30):
    a=1-i/30
    dc.rectangle([bx0+i,by0+i,bx1-1-i,by1-1-i], outline=(int(18+30*a),int(24+34*a),int(30+38*a)))
inner=(bx0+34,by0+34,bx1-34,by1-34)
dc.rectangle(inner, outline=(240,240,240), width=2)
# chevrons like the reference
cym=(by0+by1)//2
for k in range(2):
    x=bx0+300+k*130
    dc.line([(x,by0+80),(x+78,cym),(x,by1-80)], fill=(16,46,56), width=11)
    dc.line([(x+16,by0+80),(x+94,cym),(x+16,by1-80)], fill=(225,240,244), width=4)
# horizontal liner seams
for yy in (by0+70, by1-70):
    dc.line([(bx0+50,yy),(bx1-50,yy)], fill=(255,255,255), width=2)
import numpy as _v
_vy,_vx=_v.mgrid[0:BH,0:BW]
_r=_v.sqrt(((_vx-BW/2)/(BW/2))**2+((_vy-BH/2)/(BH/2))**2)
_m=_v.clip(1.0-0.30*_v.clip(_r-0.35,0,None)**1.5,0,1)
_ar=_v.asarray(col.crop(REG["B"])).astype(_v.float32)*_m[:,:,None]
col.paste(Image.fromarray(_ar.astype("uint8")),(bx0,by0))
grain(col,REG["B"],6,77)
be=emi.crop(REG["B"])
be=Image.blend(be, col.crop(REG["B"]).point(lambda v:int(v*0.34)), 1.0)
emi.paste(be,(bx0,by0))

# ---------------- C : inner walls ----------------
cx0,cy0,cx1,cy1=REG["C"]
vgrad(dc,(cx0,cy0,cx1,cy1),(74,78,84),(24,26,30))
grain(col,REG["C"],16,101)
random.seed(5)
for i in range(120):
    x=random.randint(cx0,cx1-2); y=random.randint(cy0,cy1-2)
    l=random.randint(4,30)
    dc.line([(x,y),(x+l,y+random.randint(-2,2))], fill=(random.randint(80,130),)*3)
for i in range(9):
    x=cx0+int((cx1-cx0)*i/9)
    dc.line([(x,cy0),(x,cy1)], fill=(96,100,106), width=3)
# ---------------- D : rim / generic metal ----------------
dx0,dy0,dx1,dy1=REG["D"]
vgrad(dc,(dx0,dy0,dx1,dy1),(120,124,130),(58,60,66))
grain(col,REG["D"],14,202)
# ---------------- E : divider walls ----------------
ex0,ey0,ex1,ey1=REG["E"]
vgrad(dc,(ex0,ey0,ex1,ey1),(96,100,108),(34,36,40))
grain(col,REG["E"],12,303)
dc.rectangle([ex0,ey0,ex1-1,ey0+10], fill=(150,152,158))

col.save(os.path.join(WORK, "interior_col.png"))
emi.filter(ImageFilter.GaussianBlur(1)).save(os.path.join(WORK, "interior_emi.png"))
json.dump(REG, open(os.path.join(WORK, "regions.json"),"w"))
print("painted")
