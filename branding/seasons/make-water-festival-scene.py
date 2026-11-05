# Pixel-art river scene for the Water Festival season: full moon, stars, race boats, a lit float, waves.
# 1 unit = 1 "pixel"; rendered with crispEdges and scaled by CSS.
W, H = 320, 72
WATER = 46
out = []
def r(x, y, w, h, c, extra=""): out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}"{extra}/>')

# stars
for x, y in [(18,8),(44,18),(70,6),(102,14),(131,4),(160,20),(188,9),(214,16),(236,5),(306,22),(296,6),(8,26),(122,26)]:
    r(x, y, 1, 1, "#cfd8e8")
# moon: pixel disc r=10 at (266,16) + soft halo ring
import math
cx, cy, R = 266, 17, 10
for yy in range(-R-3, R+4):
    for xx in range(-R-3, R+4):
        d = math.hypot(xx+.5, yy+.5)
        if d <= R: r(cx+xx, cy+yy, 1, 1, "#f2c75c" if d < R-1.2 else "#e0a93c")
        elif d <= R+2.4 and (xx+yy) % 2 == 0: r(cx+xx, cy+yy, 1, 1, "#3a4f6e")
# craters
for x, y, w in [(262,12,3),(270,20,2),(259,20,2),(268,13,1)]: r(x, y, w, 1, "#d99d38")

g_water = []
# water bands
r(0, WATER, W, H-WATER, "#14304a")
r(0, WATER+9, W, H-WATER-9, "#112a41")
r(0, WATER+18, W, H-WATER-18, "#0e2337")
# moon reflection (broken gold dashes)
for i, (y, w) in enumerate([(WATER+2,8),(WATER+5,6),(WATER+8,10),(WATER+12,5),(WATER+15,8),(WATER+19,4),(WATER+22,6)]):
    r(cx - w//2 + (i%2)*2 - 1, y, w, 1, "#c99a3e" if i < 3 else "#8a6c33")

# waves: a repeating crest tile in a pattern, animated by shifting the group
waves = []
for row, (y, col, step, off) in enumerate([(WATER, "#2a8f97", 16, 0), (WATER+6, "#1f6f78", 20, 7), (WATER+13, "#1a5866", 24, 3), (WATER+20, "#174a58", 28, 11)]):
    for x in range(-32 + off, W + 32, step):
        waves.append(f'<rect x="{x}" y="{y}" width="5" height="1" fill="{col}"/><rect x="{x+1}" y="{y-1}" width="3" height="1" fill="{col}"/>')

def boat(x0, y0, length, hull, stripe, head, rower, flip=False):
    b = []
    def R(x, y, w, h, c): b.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}"/>')
    # hull: long and low, tapering ends
    R(x0+4, y0, length-8, 3, hull)
    R(x0+2, y0, 2, 2, hull); R(x0+length-4, y0, 2, 2, hull)
    R(x0+6, y0+3, length-12, 1, "#3b1f12")
    R(x0+4, y0, length-8, 1, stripe)
    # stern: curls up at the back
    R(x0, y0-1, 2, 2, hull); R(x0-1, y0-3, 2, 2, hull); R(x0-1, y0-4, 1, 1, stripe)
    # naga head prow: rises at the front
    px = x0 + length - 2
    R(px, y0-1, 2, 2, hull); R(px+1, y0-3, 2, 2, hull); R(px+2, y0-5, 2, 2, head); R(px+4, y0-5, 2, 1, head); R(px+3, y0-6, 1, 1, "#f4f5ed")
    # rowers: head + body, paddles alternate
    for i, rx in enumerate(range(x0+6, x0+length-8, 4)):
        R(rx, y0-3, 2, 2, rower); R(rx, y0-4, 2, 1, "#e8c9a0")
        if i % 2: R(rx-1, y0+1, 1, 4, "#c9a26b")
        else:     R(rx+2, y0+1, 1, 3, "#c9a26b")
    # cox standing at the back with a flag
    R(x0+3, y0-6, 1, 6, "#c9a26b"); R(x0+4, y0-6, 3, 2, stripe)
    return b

boats = [
    ('boat-a', boat(30, WATER-1, 96, "#7a2f1d", "#e0a93c", "#d9772b", "#2b2034")),
    ('boat-b', boat(150, WATER+4, 70, "#1d5a4f", "#f2c75c", "#3fb59a", "#2b2034")),
]
# illuminated float (pratip): a raft with a lit frame, glow, reflection
fl = []
def F(x, y, w, h, c): fl.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}"/>')
fx, fy = 226, WATER+8
F(fx, fy, 30, 2, "#3b1f12")
for i, x in enumerate(range(fx+2, fx+29, 3)):
    F(x, fy-1, 1, 1, "#f2c75c" if i % 2 else "#d9772b")
F(fx+3, fy-9, 1, 8, "#d9772b"); F(fx+26, fy-9, 1, 8, "#d9772b"); F(fx+3, fy-10, 24, 1, "#d9772b")
F(fx+9, fy-14, 12, 1, "#f2c75c"); F(fx+8, fy-13, 1, 3, "#f2c75c"); F(fx+21, fy-13, 1, 3, "#f2c75c")
F(fx+14, fy-17, 2, 3, "#f4f5ed")
for x in range(fx+5, fx+26, 4): F(x, fy-6, 1, 1, "#f4f5ed")
for i, x in enumerate(range(fx+1, fx+30, 3)): F(x, fy+3 + (i % 3), 1, 1, "#8a6c33")

svg = (f'<svg class="wf-scene" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges" role="img" '
       f'aria-label="Pixel-art river at night: a full moon, two long racing boats with rowers, and an illuminated float">'
       + "".join(out)
       + '<g class="wf-waves">' + "".join(waves) + '</g>'
       + "".join(f'<g class="wf-boat {n}">' + "".join(b) + '</g>' for n, b in boats)
       + '<g class="wf-float">' + "".join(fl) + '</g>'
       + '</svg>')
open('water-festival-scene.svg','w').write(svg)
print(len(svg))
