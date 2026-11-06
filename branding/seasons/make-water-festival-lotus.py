import math
W=H=128
grid=[[None]*W for _ in range(H)]
def put(x,y,c,over=True):
    xi,yi=int(x),int(y)
    if 0<=xi<W and 0<=yi<H and (over or grid[yi][xi] is None): grid[yi][xi]=c

cx=64.0
# ---- water pool + reflection behind the pad (subtle) ----
# lily pad: big round green pad with a notch, sitting low
pad_cy=96; pad_rx=44; pad_ry=15
for y in range(H):
    for x in range(W):
        dx=(x-cx)/pad_rx; dy=(y-pad_cy)/pad_ry
        if dx*dx+dy*dy<=1:
            # notch wedge on lower-right
            ang=math.atan2(y-pad_cy,x-cx)
            if -0.5<ang<0.25 and (dx*dx+dy*dy)>0.12:
                continue
            edge = dx*dx+dy*dy>0.8
            put(x,y,"#1f6f78" if edge else "#2f8f7a")
# pad vein lines
for a in range(-150,80,28):
    r=a*math.pi/180
    for t in range(6,int(pad_rx)):
        put(cx+math.cos(r)*t, pad_cy+math.sin(r)*t*pad_ry/pad_rx, "#2b7d6e",over=False)

# ---- petal rasteriser ----
def halfwidth(s, wmax):
    s=max(0.0,min(1.0,s))
    return wmax*((s+0.12)**0.5)*((1-s)**0.85)*1.65

def petal(angle_deg, length, wmax, fill, hi, ocx, ocy):
    a=math.radians(angle_deg)
    ca,sa=math.cos(a),math.sin(a)
    pts={}
    steps=length*3
    for i in range(int(steps)+1):
        s=i/steps; u=s*length
        hw=halfwidth(s,wmax)
        vv=-hw
        while vv<=hw:
            # local axis points "up" (tip away from center): local (v, -u)
            x=ocx + v_rot_x(vv,u,ca,sa)
            y=ocy + v_rot_y(vv,u,ca,sa)
            edge = abs(vv)>hw-1.3 or s>0.93
            put(x,y, fill if not edge else shade(fill))
            vv+=1
    # highlight down the middle, lower half
    for i in range(int(steps)+1):
        s=i/steps; u=s*length
        if 0.15<s<0.78:
            x=ocx+v_rot_x(0,u,ca,sa); y=ocy+v_rot_y(0,u,ca,sa)
            put(x,y,hi)
            x=ocx+v_rot_x(1,u,ca,sa); y=ocy+v_rot_y(1,u,ca,sa); put(x,y,hi,over=False)

def v_rot_x(v,u,ca,sa):  # local (v, -u) rotated by a
    return v*ca - (-u)*sa
def v_rot_y(v,u,ca,sa):
    return v*sa + (-u)*ca
def shade(c):
    return {"#f2b9d6":"#d98ab6","#e78fc0":"#c76aa0","#f7d9ea":"#e3a7cb"}.get(c,c)

ocx,ocy=cx,86
# back row (darker, wider)
for ang in (-74,-37,0,37,74):
    petal(ang,52,9,"#e78fc0","#f7d9ea",ocx,ocy)
# front row (lighter), tips a touch higher
for ang in (-55,-18,18,55):
    petal(ang,44,8.5,"#f2b9d6","#ffffff",ocx,ocy-2)
# small center front petal
petal(0,30,7,"#f7d9ea","#ffffff",ocx,ocy-1)

# ---- golden seed pod / center ----
for y in range(H):
    for x in range(W):
        dx=(x-cx)/9.0; dy=(y-(ocy-6))/7.0
        if dx*dx+dy*dy<=1:
            put(x,y,"#e0a93c" if dx*dx+dy*dy>0.55 else "#f2c75c")
for (sx,sy) in [(-4,-9),(0,-11),(4,-9),(-6,-6),(6,-6),(-2,-7),(2,-7)]:
    put(cx+sx,(ocy-6)+sy,"#8a6c33"); put(cx+sx,(ocy-6)+sy-1,"#f4f5ed",over=False)

# ---- two buds on stems at sides ----
def bud(bx,by):
    for y in range(H):
        for x in range(W):
            dx=(x-bx)/4.0; dy=(y-by)/6.5
            if dx*dx+dy*dy<=1: put(x,y,"#e78fc0" if dx*dx+dy*dy>0.5 else "#f2b9d6")
    put(bx,by-7,"#f7d9ea"); 
    for t in range(0,14): put(bx, by+6+t, "#2f8f7a")  # stem
bud(16,60); bud(112,62)

# merge horizontal runs -> rects
rects=[]
for y in range(H):
    x=0
    while x<W:
        c=grid[y][x]
        if c is None: x+=1; continue
        x2=x
        while x2<W and grid[y][x2]==c: x2+=1
        rects.append((x,y,x2-x,c)); x=x2
body="".join(f'<rect x="{x}" y="{y}" width="{w}" height="1" fill="{c}"/>' for (x,y,w,c) in rects)
svg=(f'<svg class="ctfc-hero-art" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
     f'shape-rendering="crispEdges" role="img" aria-label="Pixel-art lotus flower for the Water Festival">'
     f'{body}</svg>')
open('/tmp/claude-0/-home-claude/8f18fab1-9ab5-5b6a-ad3d-f8edaa33e8ea/scratchpad/lotus.svg','w').write(svg)
print("rects",len(rects),"bytes",len(svg))
