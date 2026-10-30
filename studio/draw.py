"""Drawing toolkit for B-roll: cairo for antialiased shapes, PIL for text from font files, easing, and reusable
pieces (titles, pills, phones, maps, stamps, marks). Colours come from the project brand via configure()."""
import math
import cairo, numpy as np
from PIL import Image, ImageDraw, ImageFont
from .config import font_path, hex_rgb

W, H = 1080, 1920
RED, GOLD, INK, WHITE = (0.784, 0.063, 0.180), (0.831, 0.686, 0.216), (0.055, 0.055, 0.063), (1, 1, 1)
EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"          # macOS colour emoji; other systems: no emoji
_fonts = {}


def configure(brand, size=(1080, 1920)):
    """Set brand colours (accent -> RED, highlight -> GOLD, ink -> INK) and canvas size. Call before importing pieces."""
    global RED, GOLD, INK, W, H
    RED, GOLD, INK = hex_rgb(brand["accent"], 1), hex_rgb(brand["highlight"], 1), hex_rgb(brand["ink"], 1)
    W, H = size


def font(name, px):
    if (name, px) not in _fonts:
        _fonts[(name, px)] = ImageFont.truetype(EMOJI if name == "emoji" else font_path(name), px)
    return _fonts[(name, px)]


def new(alpha=False, bg=None):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H); c = cairo.Context(s)
    if not alpha: c.set_source_rgb(*(bg or INK)); c.paint()
    return s, c


def to_rgba(surface):
    a = np.ndarray((H, W, 4), np.uint8, surface.get_data()).copy()
    rgba = a[..., [2, 1, 0, 3]].astype(np.float32); al = rgba[..., 3:4] / 255.0
    rgba[..., :3] = np.where(al > 0, rgba[..., :3] / np.maximum(al, 1e-6), 0)
    return np.clip(rgba, 0, 255).astype(np.uint8)


def rrect(c, x, y, w, h, r):
    r = min(r, w / 2, h / 2); c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0); c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi); c.arc(x + r, y + r, r, math.pi, 1.5 * math.pi); c.close_path()


def fill(c, rgb, a=1.0): c.set_source_rgba(*rgb, a); c.fill()
def stroke(c, rgb, w, a=1.0): c.set_source_rgba(*rgb, a); c.set_line_width(w); c.stroke()


def text_img(s, name, px, rgb=WHITE, alpha=1.0, stroke_w=0, stroke_rgb=(0, 0, 0)):
    f = font(name, px)
    if name == "emoji":                                       # Apple Color Emoji only has fixed bitmap sizes
        im = Image.new("RGBA", (int(px * 1.4), int(px * 1.4)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((0, 0), s, font=f, embedded_color=True); return im.crop(im.getbbox())
    l, t, r, b = f.getbbox(s, stroke_width=stroke_w)
    im = Image.new("RGBA", (r - l + 4, b - t + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - l, 2 - t), s, font=f, fill=tuple(int(v * 255) for v in rgb) + (int(alpha * 255),),
                            stroke_width=stroke_w, stroke_fill=tuple(int(v * 255) for v in stroke_rgb) + (int(alpha * 255),))
    return im


def paste(c, im, x, y, anchor="lt", alpha=1.0, scale=1.0, rotate=0.0):
    """Paint a PIL RGBA image onto the cairo context. anchor: l/c/r + t/m/b. Follows the current transform."""
    if scale != 1.0: im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    arr = np.asarray(im).astype(np.float32); al = arr[..., 3:4] / 255.0
    pm = np.concatenate([arr[..., [2, 1, 0]] * al, arr[..., 3:4]], -1).astype(np.uint8)
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, im.width)
    buf = np.zeros((im.height, stride // 4, 4), np.uint8); buf[:, : im.width] = pm
    surf = cairo.ImageSurface.create_for_data(memoryview(buf), cairo.FORMAT_ARGB32, im.width, im.height, stride)
    dx = {"l": 0, "c": -im.width / 2, "r": -im.width}[anchor[0]]; dy = {"t": 0, "m": -im.height / 2, "b": -im.height}[anchor[1]]
    c.save(); c.translate(x, y); c.rotate(rotate); c.set_source_surface(surf, dx, dy); c.paint_with_alpha(alpha); c.restore()
    return im.width, im.height


def text(c, s, x, y, name="Montserrat-ExtraBold", px=60, rgb=WHITE, anchor="lt", alpha=1.0, scale=1.0, rotate=0.0, **kw):
    return paste(c, text_img(s, name, px, rgb, 1.0, **kw), x, y, anchor, alpha, scale, rotate)


# ---- easing ----
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3
def ease_in_out(x): x = clamp(x); return 3 * x * x - 2 * x * x * x
def back_out(x, s=1.7): x = clamp(x) - 1; return x * x * ((s + 1) * x + s) + 1
def prog(t, start, dur): return clamp((t - start) / dur)


class scaled:
    """with scaled(c, x, y, s): draw in a local frame scaled by s, origin at (x, y)."""
    def __init__(self, c, x, y, s): self.c, self.x, self.y, self.s = c, x, y, max(s, 0.01)
    def __enter__(self): self.c.save(); self.c.translate(self.x, self.y); self.c.scale(self.s, self.s)
    def __exit__(self, *a): self.c.restore()


# ---- reusable pieces ----
def vignette_bg(c, top=(0.09, 0.09, 0.11), bottom=None):
    g = cairo.LinearGradient(0, 0, 0, H); g.add_color_stop_rgb(0, *top); g.add_color_stop_rgb(1, *(bottom or INK))
    c.set_source(g); c.paint()
    r = cairo.RadialGradient(W / 2, H * 0.4, 200, W / 2, H * 0.4, 1300)
    r.add_color_stop_rgba(0, 0, 0, 0, 0); r.add_color_stop_rgba(1, 0, 0, 0, 0.55); c.set_source(r); c.paint()


def grid(c, step=60, a=0.05):
    c.set_line_width(1)
    for x in range(0, W, step): c.move_to(x, 0); c.line_to(x, H)
    for y in range(0, H, step): c.move_to(0, y); c.line_to(W, y)
    c.set_source_rgba(1, 1, 1, a); c.stroke()


def title(c, s, y, t, t0, px=92, rgb=WHITE, sub=None):
    p = ease_out(prog(t, t0, 0.35))
    text(c, s, W / 2, y + 40 * (1 - p), "Anton", px, rgb, "ct", alpha=p)
    if sub: text(c, sub, W / 2, y + px * 1.25 + 30 * (1 - p), "Inter-SemiBold", 34, (0.8, 0.8, 0.85), "ct", alpha=p)


def pill(c, s, x, y, rgb, fg=None, px=30, anchor="ct", outline=False, alpha=1.0):
    im = text_img(s, "Montserrat-ExtraBold", px, rgb if outline else (fg or INK))
    w, h = im.width + 44, im.height + 22; dx = {"l": 0, "c": -w / 2, "r": -w}[anchor[0]]
    rrect(c, x + dx, y, w, h, h / 2)
    if outline: stroke(c, rgb, 3, alpha)
    else: fill(c, rgb, alpha)
    paste(c, im, x + dx + w / 2, y + h / 2, "cm", alpha); return w, h


def status_bar(c, x, y, w, clock="9:41"):
    text(c, clock, x + 34, y + 14, "Inter-SemiBold", 26, WHITE)
    bx = x + w - 92
    rrect(c, bx, y + 18, 46, 22, 6); stroke(c, WHITE, 2); rrect(c, bx + 4, y + 22, 32, 14, 3); fill(c, WHITE)
    rrect(c, bx + 47, y + 25, 4, 8, 1); fill(c, WHITE)
    for i in range(4): h = 6 + i * 5; rrect(c, bx - 74 + i * 9, y + 40 - h, 6, h, 1.5); fill(c, WHITE)
    c.save(); c.translate(bx - 26, y + 39)
    for r in (18, 12, 6): c.arc(0, 0, r, -2.4, -0.74); stroke(c, WHITE, 3)
    c.restore()


def phone(c, x, y, w, h, kind="iphone"):
    """Phone body; returns (sx, sy, sw, sh, screen_radius). iPhone-like titanium frame or Android-like black frame."""
    r = w * (0.16 if kind == "iphone" else 0.11); frame = (0.62, 0.60, 0.57) if kind == "iphone" else (0.10, 0.10, 0.11)
    rrect(c, x - 6, y - 6, w + 12, h + 12, r + 6); fill(c, (0, 0, 0), 0.45); rrect(c, x, y, w, h, r); fill(c, frame)
    b = 12 if kind == "iphone" else 10; sx, sy, sw, sh = x + b, y + b, w - 2 * b, h - 2 * b
    rrect(c, sx, sy, sw, sh, r - b); fill(c, (0.02, 0.02, 0.03)); return sx, sy, sw, sh, r - b


def phone_notch(c, sx, sy, sw, kind):
    if kind == "iphone": rrect(c, sx + sw / 2 - 62, sy + 16, 124, 36, 18); fill(c, (0, 0, 0))
    else: c.arc(sx + sw / 2, sy + 30, 11, 0, 2 * math.pi); fill(c, (0, 0, 0))


def along(pts, k):
    seg = [math.dist(a, b) for a, b in zip(pts, pts[1:])]; d = k * sum(seg)
    for (a, b), L in zip(zip(pts, pts[1:]), seg):
        if d <= L: f = d / L; return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        d -= L
    return pts[-1]


def map_view(c, x, y, w, h, t, route, traffic=0, seed=3):
    """Stylised dark map: road grid, route line, moving car, optional traffic dots. route: [(u, v)] in 0..1."""
    c.save(); rrect(c, x, y, w, h, 0); c.clip(); c.set_source_rgb(0.11, 0.12, 0.14); c.paint()
    rng = np.random.default_rng(seed); c.set_line_cap(cairo.LINE_CAP_ROUND)
    for _ in range(9):
        u = rng.uniform(0, 1); c.move_to(x + u * w, y); c.line_to(x + (u + rng.uniform(-.2, .2)) * w, y + h)
        stroke(c, (0.24, 0.25, 0.29), rng.choice([6, 10, 14]))
        v = rng.uniform(0, 1); c.move_to(x, y + v * h); c.line_to(x + w, y + (v + rng.uniform(-.1, .1)) * h)
        stroke(c, (0.24, 0.25, 0.29), rng.choice([6, 10, 14]))
    for _ in range(5):
        bx, by = rng.uniform(0, .8), rng.uniform(0, .8); rrect(c, x + bx * w, y + by * h, w * .14, h * .08, 8); fill(c, (0.15, 0.20, 0.16), 0.8)
    pts = [(x + u * w, y + v * h) for u, v in route]
    c.move_to(*pts[0]); [c.line_to(*p) for p in pts[1:]]; stroke(c, GOLD, 9)
    for i in range(traffic):
        px, py = along(pts, (i * 0.137 + t * 0.12 * (1 + i % 3)) % 1.0)
        c.arc(px + (i % 2) * 14 - 7, py, 6, 0, 2 * math.pi); fill(c, [(0.9, 0.2, 0.2), (0.95, 0.75, 0.2), (0.3, 0.85, 0.4)][i % 3], 0.9)
    c.arc(*pts[0], 13, 0, 2 * math.pi); fill(c, (0.2, 0.8, 0.4)); c.arc(*pts[0], 6, 0, 2 * math.pi); fill(c, WHITE)
    ex, ey = pts[-1]; c.move_to(ex, ey); c.arc(ex, ey - 26, 16, math.pi * 0.85, math.pi * 2.15); c.close_path(); fill(c, RED)
    c.arc(ex, ey - 26, 6, 0, 2 * math.pi); fill(c, WHITE)
    cx, cy = along(pts, (t * 0.18) % 1.0)
    rrect(c, cx - 16, cy - 10, 32, 20, 6); fill(c, WHITE); rrect(c, cx - 9, cy - 7, 18, 14, 4); fill(c, (0.2, 0.2, 0.25))
    c.restore()


def stamp(c, x, y, lines, t_in, t, color=None, rot=-0.14, size=110):
    """Rubber-stamp slam (scale 1.8 -> 1 with overshoot over 180 ms), double border."""
    if t < t_in: return
    color = color or RED; p = prog(t, t_in, 0.18); sc = 1.8 - 0.8 * back_out(p, 2.2)
    imgs = [text_img(s, "Anton" if i == 0 else "Montserrat-ExtraBold", size if i == 0 else int(size * 0.42), color) for i, s in enumerate(lines)]
    w = max(im.width for im in imgs) + 70; h = sum(im.height for im in imgs) + 30 * len(imgs) + 40
    c.save(); c.translate(x, y); c.rotate(rot); c.scale(sc, sc)
    rrect(c, -w / 2, -h / 2, w, h, 18); stroke(c, color, 10, min(1, p * 3))
    rrect(c, -w / 2 + 16, -h / 2 + 16, w - 32, h - 32, 10); stroke(c, color, 4, min(1, p * 3))
    yy = -h / 2 + 34
    for im in imgs: paste(c, im, 0, yy, "ct", min(1, p * 3)); yy += im.height + 30
    c.restore()


def check_mark(c, x, y, s, rgb, a=1.0):
    c.set_line_cap(1); c.set_line_join(1)
    c.move_to(x - s * 0.45, y); c.line_to(x - s * 0.1, y + s * 0.35); c.line_to(x + s * 0.5, y - s * 0.4); stroke(c, rgb, s * 0.16, a)


def x_mark(c, x, y, s, rgb, a=1.0):
    c.set_line_cap(1)
    c.move_to(x - s / 2, y - s / 2); c.line_to(x + s / 2, y + s / 2); c.move_to(x + s / 2, y - s / 2); c.line_to(x - s / 2, y + s / 2)
    stroke(c, rgb, s * 0.16, a)
