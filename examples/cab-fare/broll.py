"""Graphics for the cab-fare example: an invented ride app ("RideNow"), news card, results board, live fare,
dark-pattern popup, logic card, tip card, plus two overlays. Each function draws one frame: fn(c, t, piece) with
piece = {"start", "end", "events": {name: seconds}} resolved from project.json anchors.

Layout rule for 1080x1920 reels: keep important content between y=230 and y=1080. The top 220 px and bottom
380 px sit under Instagram's UI, captions sit around y=1190, and the character's circle sits bottom-left.
"""
import math
import cairo
from studio.draw import *


def ridenow_logo(c, x, y, size=56):
    """Invented brand: rounded square with an R and a highlight dot."""
    rrect(c, x, y, size, size, size * 0.28); fill(c, RED)
    text(c, "R", x + size / 2, y + size / 2 + 2, "Anton", int(size * 0.7), WHITE, "cm")
    c.arc(x + size * 0.78, y + size * 0.25, size * 0.09, 0, 2 * math.pi); fill(c, GOLD)


def app_screen(c, sx, sy, sw, sh, t, fare, fare_label, route, kind, show_fare=True, traffic=0):
    status_bar(c, sx, sy + 4, sw)
    ridenow_logo(c, sx + 28, sy + 74, 46); text(c, "RideNow", sx + 88, sy + 82, "Montserrat-ExtraBold", 30)
    map_view(c, sx, sy + 140, sw, sh * 0.52, t, route, traffic=traffic)
    cy = sy + 140 + sh * 0.52
    rrect(c, sx, cy - 24, sw, sh - (cy - sy) + 24, 30); fill(c, (0.08, 0.08, 0.10))
    text(c, "Mini  ·  4.2 km  ·  14 min", sx + 30, cy + 10, "Inter-SemiBold", 26, (0.75, 0.75, 0.8))
    if show_fare:
        text(c, fare, sx + 30, cy + 52, "Montserrat-ExtraBold", 88, WHITE)
        text(c, fare_label, sx + 30, cy + 160, "Inter-Regular", 24, (0.6, 0.6, 0.65))
    rrect(c, sx + 26, sy + sh - 96, sw - 52, 70, 35); fill(c, RED)
    text(c, "Book ride", sx + sw / 2, sy + sh - 61, "Montserrat-ExtraBold", 30, WHITE, "cm")
    phone_notch(c, sx, sy, sw, kind)

ROUTE = [(0.18, 0.82), (0.30, 0.62), (0.52, 0.58), (0.62, 0.36), (0.80, 0.22)]

def count_rupees(t, t0, value, dur=0.6):
    p = ease_out(prog(t, t0, dur)); return f"₹{int(round(value * p))}" if t >= t0 else "₹ --"

# ---------------- B1: same ride, two phones (viral claim) ----------------
def B1(c, t, b):
    e = b["events"]; t0 = b["start"]
    vignette_bg(c); grid(c)
    title(c, "SAME RIDE. SAME TIME.", 240, t, t0, 88)
    pill(c, "VIRAL CLAIM", W / 2, 352, GOLD, outline=True, alpha=ease_out(prog(t, t0 + 0.2, 0.3)))
    for i, (kind, label, fare, te) in enumerate((("iphone", "iPhone", 312, e["iphone_fare"]), ("android", "Android", 268, e["android_fare"]))):
        p = ease_out(prog(t, t0 + 0.1 + i * 0.12, 0.45))
        x = 160 + i * 460; y = 470 + 300 * (1 - p)
        with scaled(c, x, y, 0.68):
            sx, sy, sw, sh, _ = phone(c, 0, 0, 440, 900, kind)
            app_screen(c, sx, sy, sw, sh, t - t0, count_rupees(t, te, fare), "Same pickup → same drop", ROUTE, kind)
        k = ease_out(prog(t, te, 0.3)) if t >= te else 0.35
        pill(c, label, x + 150, y - 54, RED if kind == "iphone" else (0.20, 0.55, 0.30), WHITE, 30, alpha=k)
    if t >= e["question_stamp"]:
        p = back_out(prog(t, e["question_stamp"], 0.2), 2.4)
        c.save(); c.translate(W / 2, 800); c.rotate(-0.15); c.scale(0.4 + 0.6 * p, 0.4 + 0.6 * p)
        c.arc(0, 0, 120, 0, 2 * math.pi); fill(c, RED, 0.92); c.arc(0, 0, 104, 0, 2 * math.pi); stroke(c, WHITE, 6)
        text(c, "?", 0, 6, "Anton", 180, WHITE, "cm"); c.restore()

# ---------------- B2: news card over a blurred cab shot (transparent background) ----------------
def B2(c, t, b):
    e = b["events"]; t0 = b["start"]
    c.set_source_rgba(0, 0, 0, 0.35); c.paint()                   # darken the blurred footage under it
    p = ease_out(prog(t, e["card_in"], 0.45)); x = 60 - 1100 * (1 - p)
    rrect(c, x, 330, 960, 560, 34); fill(c, (0.97, 0.97, 0.98), 0.97)
    rrect(c, x, 330, 960, 96, 34); fill(c, RED); c.rectangle(x, 380, 960, 46); fill(c, RED)
    text(c, "BYTE.TALK BRIEF", x + 40, 352, "Montserrat-ExtraBold", 36, WHITE)
    text(c, "23 JAN 2025", x + 920, 356, "Montserrat-ExtraBold", 30, (1, 0.85, 0.85), "rt")
    text(c, "CCPA notice to", x + 40, 470, "Anton", 92, INK)
    hp = ease_out(prog(t, e["notice_word"], 0.25))                # highlight on "notice"
    lead = font("Anton", 92).getlength("CCPA "); nw = font("Anton", 92).getlength("notice")
    rrect(c, x + 40 + lead, 572, nw * hp, 14, 7); fill(c, GOLD, hp)
    text(c, "Ola & Uber", x + 40, 592, "Anton", 92, RED)
    text(c, "Central Consumer Protection Authority", x + 40, 730, "Inter-SemiBold", 32, (0.3, 0.3, 0.35))
    text(c, "Question: is the fare set by your phone type?", x + 40, 782, "Inter-Regular", 30, (0.35, 0.35, 0.4))
    # ticker
    ty = 960; c.rectangle(0, ty, W, 72); fill(c, INK, 0.92); c.rectangle(0, ty, 210, 72); fill(c, RED)
    text(c, "LIVE", 105, ty + 36, "Montserrat-ExtraBold", 34, WHITE, "cm")
    msg = "VIRAL CLAIM: same ride costlier on iPhone?   •   CCPA seeks answers from Ola & Uber   •   Both deny phone-based pricing   •   "
    im = text_img(msg * 2, "Inter-SemiBold", 32); off = ((t - t0) * 160) % (im.width / 2)
    c.save(); c.rectangle(210, ty, W - 210, 72); c.clip(); paste(c, im, 230 - off, ty + 36, "lm"); c.restore()

# ---------------- B3: test results board, the winner flips ----------------
def B3(c, t, b):
    e = b["events"]; t0 = b["start"]
    vignette_bg(c); grid(c)
    title(c, "TEST RESULTS", 230, t, t0, 92, GOLD, sub="Same route · same time · iPhone vs Android")
    rows = [("Test 1", "iphone", e["row1"]), ("Test 2", "android", e["row2"]),
            ("Test 3", "iphone", e["iphone_costlier"]), ("Test 4", "android", e["row3"])]
    y0 = 500
    text(c, "COSTLIER PHONE", 1000, y0 - 40, "Montserrat-ExtraBold", 26, (0.6, 0.6, 0.65), "rt")
    for i, (lab, win, tr) in enumerate(rows):
        if t < tr: continue
        p = ease_out(prog(t, tr, 0.3)); y = y0 + i * 128 + 30 * (1 - p)
        rrect(c, 80, y, 920, 112, 24); fill(c, (1, 1, 1), 0.06 * p + 0.02)
        text(c, lab, 120, y + 56, "Montserrat-ExtraBold", 40, WHITE, "lm", alpha=p)
        for j, (name, kind) in enumerate((("iPhone", "iphone"), ("Android", "android"))):
            bx = 420 + j * 290; is_win = kind == win
            rrect(c, bx, y + 16, 250, 80, 40)
            if is_win: fill(c, RED, p)
            else: stroke(c, (0.5, 0.5, 0.55), 3, p)
            text(c, name, bx + 125, y + 56, "Montserrat-ExtraBold", 34,
                 WHITE if is_win else (0.6, 0.6, 0.65), "cm", alpha=p)
    # magnifier sweep: lens follows the newest row
    shown = [i for i, r in enumerate(rows) if t >= r[2]]
    if shown:
        i = shown[-1]; tr = rows[i][2]; k = ease_in_out(prog(t, tr, 0.6))
        lx = 420 + (290 if rows[i][1] == "android" else 0) + 125; ly = y0 + i * 128 + 56
        sx, sy = lx - 160 + 160 * k, ly - 40 + 40 * k
        c.arc(sx, sy, 92, 0, 2 * math.pi); fill(c, (1, 1, 1), 0.10)
        c.arc(sx, sy, 92, 0, 2 * math.pi); stroke(c, GOLD, 10)
        c.move_to(sx + 66, sy + 66); c.line_to(sx + 140, sy + 140); c.set_line_cap(1); stroke(c, GOLD, 22)
    if t >= e["android_costlier"]:
        p = ease_out(prog(t, e["android_costlier"], 0.3))
        pill(c, "RESULT: MIXED, NO FIXED PATTERN", W / 2, 1012, GOLD, INK, 32, alpha=p)
    text(c, "Source: Indian Express test, Jan 2025", W / 2, 418, "Inter-SemiBold", 26, (0.62, 0.62, 0.68), "ct")

# ---------------- B4: one phone, the fare keeps changing ----------------
def B4(c, t, b):
    e = b["events"]; t0 = b["start"]
    vignette_bg(c); grid(c)
    title(c, "FARE IS DYNAMIC", 240, t, t0, 96, WHITE)
    words = [("TIME", e["fare_265"]), ("TRAFFIC", e["fare_251"]), ("DEMAND", e["fare_289"])]
    x = 140
    for wd, tw in words:
        on = t >= tw; w_, _ = pill(c, wd, x, 370, GOLD if on else (0.25, 0.25, 0.28), INK if on else (0.7, 0.7, 0.72), 32, "lt")
        x += w_ + 24
    steps = [(e["fare_240"], 240), (e["fare_265"], 265), (e["fare_251"], 251), (e["fare_289"], 289)]
    prev, cur, tc = 240, 240, steps[0][0]
    for ts, v in steps:
        if t >= ts: prev, cur, tc = cur, v, ts
    k = ease_out(prog(t, tc, 0.35)); fare = int(round(prev + (cur - prev) * k))
    with scaled(c, 90, 460, 0.64):
        sx, sy, sw, sh, _ = phone(c, 0, 0, 500, 940, "android")
        app_screen(c, sx, sy, sw, sh, t - t0, f"₹{fare}", "Updates every few seconds", ROUTE, "android", traffic=14)
        if cur != prev and k < 1:
            up = cur > prev; ax, ay = sx + sw - 70, sy + 140 + sh * 0.52 + 90
            c.move_to(ax - 26, ay + (18 if up else -18)); c.line_to(ax + 26, ay + (18 if up else -18)); c.line_to(ax, ay + (-26 if up else 26))
            c.close_path(); fill(c, RED if up else (0.3, 0.8, 0.45), 1 - k)
    # clock + demand meter
    cx, cy = 780, 600
    c.arc(cx, cy, 150, 0, 2 * math.pi); fill(c, (1, 1, 1), 0.06); c.arc(cx, cy, 150, 0, 2 * math.pi); stroke(c, WHITE, 6)
    for h in range(12):
        a = h / 12 * 2 * math.pi; c.move_to(cx + 128 * math.sin(a), cy - 128 * math.cos(a)); c.line_to(cx + 140 * math.sin(a), cy - 140 * math.cos(a))
    stroke(c, WHITE, 4)
    a = (t - t0) * 2.4; c.move_to(cx, cy); c.line_to(cx + 110 * math.sin(a), cy - 110 * math.cos(a)); stroke(c, GOLD, 8)
    a2 = (t - t0) * 0.2; c.move_to(cx, cy); c.line_to(cx + 70 * math.sin(a2), cy - 70 * math.cos(a2)); stroke(c, WHITE, 10)
    text(c, "TIME", cx, cy + 170, "Montserrat-ExtraBold", 28, (0.7, 0.7, 0.75), "ct")
    lvl = 0.25 + 0.15 * (t >= e["fare_265"]) - 0.05 * (t >= e["fare_251"]) + 0.5 * ease_out(prog(t, e["fare_289"], 0.4))
    lvl += 0.03 * math.sin((t - t0) * 9)
    mx, my, mh = 720, 790, 200
    rrect(c, mx, my, 120, mh, 26); fill(c, (1, 1, 1), 0.08)
    g = cairo.LinearGradient(0, my + mh, 0, my); g.add_color_stop_rgb(0, 0.3, 0.8, 0.45); g.add_color_stop_rgb(0.55, *GOLD); g.add_color_stop_rgb(1, *RED)
    rrect(c, mx + 12, my + mh - 12 - (mh - 24) * clamp(lvl), 96, (mh - 24) * clamp(lvl), 18); c.set_source(g); c.fill()
    text(c, "DEMAND", mx + 60, my + mh + 12, "Montserrat-ExtraBold", 28, (0.7, 0.7, 0.75), "ct")
    if t >= e["two_seconds"]:
        p = back_out(prog(t, e["two_seconds"], 0.25))
        pill(c, "2 SEC = NEW PRICE", 590, 1052, RED, WHITE, 32, alpha=clamp(p))

# ---------------- B5: dark pattern after booking ----------------
def B5(c, t, b):
    e = b["events"]; t0 = b["start"]
    vignette_bg(c); grid(c)
    pill(c, "DARK PATTERN", W / 2, 240, RED, WHITE, 36)
    text(c, "Pressure to pay more after booking", W / 2, 320, "Inter-SemiBold", 34, (0.8, 0.8, 0.85), "ct")
    c.save(); c.translate(348, 380); c.scale(0.66, 0.66)
    sx, sy, sw, sh, r = phone(c, 0, 0, 580, 1000, "iphone")
    status_bar(c, sx, sy + 4, sw)
    map_view(c, sx, sy + 60, sw, sh * 0.62, t - t0, ROUTE)
    c.rectangle(sx, sy + 60, sw, sh * 0.62); fill(c, (0, 0, 0), 0.25)
    # searching spinner
    cx, cy = sx + sw / 2, sy + 60 + sh * 0.31
    for i in range(12):
        a = i / 12 * 2 * math.pi + (t - t0) * 6; al = (i / 12)
        c.move_to(cx + 34 * math.cos(a), cy + 34 * math.sin(a)); c.line_to(cx + 56 * math.cos(a), cy + 56 * math.sin(a))
        c.set_line_cap(1); stroke(c, WHITE, 8, al)
    text(c, "Searching…", cx, cy + 80, "Montserrat-ExtraBold", 36, WHITE, "ct")
    phone_notch(c, sx, sy, sw, "iphone")
    # bottom sheet popup
    p = ease_out(prog(t, e["popup_in"], 0.4)); py = sy + sh - 560 * p
    if p > 0:
        c.save(); rrect(c, sx, sy, sw, sh, r); c.clip()
        rrect(c, sx, py, sw, 600, 36); fill(c, (0.97, 0.97, 0.98))
        rrect(c, sx + sw / 2 - 40, py + 16, 80, 8, 4); fill(c, (0.75, 0.75, 0.78))
        tw, _ = text(c, "Driver nahi mil raha", sx + 36, py + 62, "Montserrat-ExtraBold", 36, INK)
        paste(c, text_img("😟", "emoji", 160), sx + 46 + tw, py + 56, "lt", scale=0.30)
        text(c, "Add karo, jaldi milega", sx + 40, py + 124, "Inter-SemiBold", 30, (0.4, 0.4, 0.45))
        for i, amt in enumerate(("+₹10", "+₹20", "+₹30")):
            bx = sx + 34 + i * (sw - 68) / 3; bw = (sw - 68) / 3 - 18
            pulse = 1 + 0.06 * math.sin((t - t0) * 7 + i)
            pressed = amt == "+₹20" and t >= e["plus20_click"]
            c.save(); c.translate(bx + bw / 2, py + 260); c.scale(pulse * (0.93 if pressed and t < e["plus20_click"] + 0.15 else 1), pulse)
            rrect(c, -bw / 2, -50, bw, 100, 24); fill(c, RED if pressed else GOLD)
            text(c, amt, 0, 0, "Montserrat-ExtraBold", 42, WHITE if pressed else INK, "cm"); c.restore()
            if pressed:
                rp = prog(t, e["plus20_click"], 0.5); c.arc(bx + bw / 2, py + 260, 40 + 140 * rp, 0, 2 * math.pi); stroke(c, RED, 6, 1 - rp)
        text(c, "Skip and keep waiting", sx + sw / 2, py + 360, "Inter-Regular", 24, (0.6, 0.6, 0.65), "ct")
        c.restore()
    c.restore()
    pill(c, "₹10 LAKH FINE · CCPA · SEP 2026", W / 2, 1040, RED, WHITE, 28, alpha=1.0)

# ---------------- B6: the tip ----------------
def B6(c, t, b):
    e = b["events"]; t0 = b["start"]
    vignette_bg(c); grid(c)
    title(c, "PRO TIP", 240, t, t0, 110, GOLD)
    for i, (name, col) in enumerate((("RideNow", RED), ("App 2", (0.18, 0.45, 0.85)))):
        p = back_out(prog(t, e["two_apps"] + i * 0.12, 0.35))
        x = 230 + i * 420; y = 420
        c.save(); c.translate(x + 110, y + 110); c.scale(max(p, 0.01), max(p, 0.01))
        rrect(c, -110, -110, 220, 220, 52); fill(c, col)
        if i == 0: text(c, "R", 0, 4, "Anton", 150, WHITE, "cm")
        else:
            c.arc(0, 0, 58, 0, 2 * math.pi); stroke(c, WHITE, 16); c.arc(0, 0, 14, 0, 2 * math.pi); fill(c, WHITE)
        c.restore()
        text(c, name, x + 110, y + 250, "Montserrat-ExtraBold", 34, WHITE, "ct", alpha=clamp(p))
    if t >= e["two_apps"] + 0.3:
        a = ease_out(prog(t, e["two_apps"] + 0.3, 0.3)); c.set_line_cap(1)
        bump = 1 + 0.25 * math.sin(math.pi * prog(t, e["compare"], 0.35))   # pulse on "compare"
        c.save(); c.translate(W / 2, 530); c.scale(bump, bump); c.translate(-W / 2, -530)
        for dy, d in ((-22, 1), (22, -1)):                        # drawn swap arrows (no font glyph needed)
            x0, x1 = W / 2 - 50 * d, W / 2 + 50 * d; c.move_to(x0, 530 + dy); c.line_to(x1, 530 + dy); stroke(c, GOLD, 10, a)
            c.move_to(x1, 530 + dy); c.line_to(x1 - 22 * d, 530 + dy - 16); c.move_to(x1, 530 + dy); c.line_to(x1 - 22 * d, 530 + dy + 16)
            stroke(c, GOLD, 10, a)
        c.restore()
    # 1-minute timer ring
    cx, cy = 330, 870
    k = clamp((t - e["timer_start"]) / 1.6) if t >= e["timer_start"] else 0     # fills while she says "ek minute ruk ke"
    c.arc(cx, cy, 110, 0, 2 * math.pi); stroke(c, (1, 1, 1), 16, 0.12)
    if k > 0: c.arc(cx, cy, 110, -math.pi / 2, -math.pi / 2 + 2 * math.pi * k); stroke(c, GOLD, 16)
    text(c, "1:00" if k < 1 else "0:00", cx, cy, "Montserrat-ExtraBold", 54, WHITE, "cm")
    text(c, "1 min ruko", cx, cy + 140, "Inter-SemiBold", 30, (0.75, 0.75, 0.8), "ct")
    # refresh
    rx, ry = 750, 870; spin = ease_out(prog(t, e["refresh"], 0.6)) * 2 * math.pi
    c.save(); c.translate(rx, ry); c.rotate(spin)
    c.arc(0, 0, 90, 0.4, 2 * math.pi - 0.2); stroke(c, WHITE, 16)
    c.move_to(90 - 30, -24); c.line_to(90 + 30, -24); c.line_to(90 + 2, 26); c.close_path(); fill(c, WHITE)
    c.restore()
    text(c, "Refresh karo", rx, ry + 140, "Inter-SemiBold", 30, (0.75, 0.75, 0.8), "ct")

# ---------------- B7: the algorithm reads your hurry, not your phone ----------------
def B7(c, t, b):
    e = b["events"]; t0 = b["start"]
    vignette_bg(c); grid(c)
    title(c, "LOGIC SIMPLE HAI", 240, t, e["logic"] - 0.1, 96, GOLD)
    # algorithm chip with a scanning pulse
    ca = back_out(prog(t, e["algorithm"], 0.3))
    if t >= e["algorithm"]:
        c.save(); c.translate(W / 2, 470); c.scale(max(ca, 0.01), max(ca, 0.01))
        rrect(c, -230, -58, 460, 116, 30); fill(c, (0.13, 0.13, 0.16)); rrect(c, -230, -58, 460, 116, 30); stroke(c, GOLD, 4)
        for k in range(4):                                  # chip pins
            for sx in (-1, 1):
                c.rectangle(sx * 230 - (14 if sx > 0 else -2) + (0 if sx > 0 else -12), -36 + k * 22, 12, 8); fill(c, GOLD)
        text(c, "ALGORITHM", 0, 0, "Anton", 64, WHITE, "cm"); c.restore()
        pr = ((t - e["algorithm"]) * 1.6) % 1.0
        rrect(c, W / 2 - 230 - 40 * pr, 412 - 40 * pr, 460 + 80 * pr, 116 + 80 * pr, 30 + 20 * pr); stroke(c, GOLD, 3, 0.6 * (1 - pr))
    cards = [("AAPKI JALDI", 70, e["jaldi"], True), ("PHONE", 570, e["phone"], False)]
    for label, x, te, good in cards:
        p = ease_out(prog(t, e["logic"] + (0.30 if good else 0.45), 0.35)); y = 640 + 60 * (1 - p)
        rrect(c, x, y, 440, 420, 34); fill(c, (1, 1, 1), 0.07 * p); rrect(c, x, y, 440, 420, 34); stroke(c, (1, 1, 1), 2, 0.25 * p)
        text(c, label, x + 220, y + 38, "Montserrat-ExtraBold", 40, WHITE, "ct", alpha=p)
        cx, cy = x + 220, y + 230
        if good:                                            # hurry meter: stopwatch + filling red bar
            c.arc(cx, cy - 20, 72, 0, 2 * math.pi); stroke(c, WHITE, 8, p)
            rrect(c, cx - 16, cy - 112, 32, 16, 5); fill(c, WHITE, p)
            sweep = (t - t0) * (9 if t >= te else 2.5)
            c.move_to(cx, cy - 20); c.line_to(cx + 56 * math.sin(sweep), cy - 20 - 56 * math.cos(sweep)); c.set_line_cap(1); stroke(c, RED, 8, p)
            fillk = ease_out(prog(t, te, 0.5))
            rrect(c, x + 50, y + 340, 340, 26, 13); fill(c, (1, 1, 1), 0.12 * p)
            rrect(c, x + 50, y + 340, 340 * max(fillk, 0.0001), 26, 13); fill(c, RED, p)
        else:                                               # two phone outlines
            for k, dx in enumerate((-70, 70)):
                rrect(c, cx + dx - 52, cy - 110, 104, 200, 22); stroke(c, WHITE, 7, p)
                if k == 0: rrect(c, cx + dx - 20, cy - 98, 40, 12, 6); fill(c, WHITE, p)
                else: c.arc(cx + dx, cy - 92, 6, 0, 2 * math.pi); fill(c, WHITE, p)
        if t >= te + (0.3 if good else 0.1):                # verdicts
            k = back_out(prog(t, te + (0.3 if good else 0.1), 0.25), 2.2)
            col = (0.25, 0.80, 0.42) if good else RED
            c.save(); c.translate(x + 432, y + 8); c.scale(max(k, 0.01), max(k, 0.01))
            c.arc(0, 0, 54, 0, 2 * math.pi); fill(c, col)
            (check_mark if good else x_mark)(c, 0, 0, 58, WHITE, 1); c.restore()
            pill(c, "READS THIS" if good else "NOT THIS", x + 220, y + 440, col, WHITE, 30, alpha=clamp(k))
    if t >= e["jaldi"]:                                     # scan beam: chip -> hurry card
        k = ease_out(prog(t, e["jaldi"], 0.3))
        c.set_dash([18, 14], -((t - t0) * 160) % 32)
        c.move_to(W / 2 - 80, 530); c.line_to(W / 2 - 80 - (W / 2 - 80 - 290) * k, 530 + (640 - 530) * k); stroke(c, GOLD, 6, 0.9)
        c.set_dash([])


# ---------------- overlays on the character ----------------
def L1(c, t, o):
    t0 = o["start"]
    p = ease_out(prog(t, t0, 0.35)); q = 1 - ease_out(prog(t, o["end"] - 0.25, 0.25))
    a = min(p, q); x = 60 - 700 * (1 - p)
    rrect(c, x, 250, 760, 150, 22); fill(c, INK, 0.88 * a)
    c.rectangle(x, 250, 16, 150); fill(c, RED, a)
    text(c, "DONO NE DENY KIYA", x + 44, 272, "Anton", 64, WHITE, alpha=a)
    text(c, "Ola & Uber: phone dekhkar pricing nahi", x + 46, 352, "Inter-SemiBold", 30, GOLD, alpha=a)

def S1(c, t, o):
    a = 1 - ease_out(prog(t, o["end"] - 0.2, 0.2))
    c.push_group(); stamp(c, W / 2, 640, ["₹10 LAKH FINE", "CCPA · SEP 2026"], o["start"], t, RED, -0.12, 120)
    c.pop_group_to_source(); c.paint_with_alpha(a)


DRAW = {"B1_split_phones": B1, "B2_news_card": B2, "B3_results_board": B3, "B4_dynamic_fare": B4,
        "B5_dark_pattern": B5, "B6_tip_card": B6, "B7_logic": B7, "L1_deny_lower_third": L1, "S1_fine_stamp": S1}
