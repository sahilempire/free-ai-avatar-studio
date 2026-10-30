"""Karaoke captions as a transparent band video (qtrle with alpha), placed by render.py.

2-4 words per caption, split at sentence ends then commas, balanced groups (5 -> 3+2, never 4+1). The spoken word is
drawn in the highlight colour with a 100 -> 108 -> 100% pop over 120 ms; key words in the accent colour; a soft dark
backdrop keeps text readable on any background.  Output: work/captions.mov + work/captions.json
"""
import re, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .config import font_path, hex_rgb

END = re.compile(r"[.?!…:]['’]?$"); COMMA = re.compile(r"[,;]['’]?$")


def group(words, max_words=4):
    sentences, cur = [], []
    for w in words:
        cur.append(w)
        if END.search(w["text"]): sentences.append(cur); cur = []
    if cur: sentences.append(cur)
    caps = []
    for sent in sentences:
        clauses, cl = [], []
        for w in sent:
            cl.append(w)
            if COMMA.search(w["text"]): clauses.append(cl); cl = []
        if cl: clauses.append(cl)
        groups = []
        for cl in clauses:
            if groups and len(groups[-1]) + len(cl) <= max_words: groups[-1] = groups[-1] + cl
            else: groups.append(cl)
        for g in groups:
            k = -(-len(g) // max_words); base, extra = divmod(len(g), k); i = 0
            for j in range(k):
                n = base + (1 if j < extra else 0); caps.append(g[i:i + n]); i += n
    return caps


def run(project):
    tl, words = project.load("timeline.json"), project.load("words.json")
    c = project.get("captions", default={})
    fps, dur = project.fps, tl["duration"]
    BW, BH = project.width, c.get("band_height", 440)
    SIZE, STROKE, MAXW = c.get("size", 82), c.get("stroke", 8), c.get("max_width", 980)
    WHITE = hex_rgb(c.get("color", "#FFFFFF")); HL = hex_rgb(project.brand["highlight"]); KEY = hex_rgb(project.brand["accent"])
    BACK = int(255 * c.get("backdrop_opacity", 0.7))
    fpath = font_path(c.get("font", "Montserrat-ExtraBold"))
    words = [dict(w) for w in words]
    words[-1]["end"] = min(words[-1]["end"], words[-1]["start"] + 0.45)

    caps = group(words, c.get("max_words", 4))
    timeline = []
    for k, cw in enumerate(caps):
        start, end = max(0.0, cw[0]["start"] - 0.05), cw[-1]["end"] + 0.30
        if k + 1 < len(caps): end = min(end, caps[k + 1][0]["start"] - 0.05)
        timeline.append({"start": round(start, 3), "end": round(end, 3), "words": cw})
    project.save("captions.json", [{"start": t["start"], "end": t["end"], "text": " ".join(w["text"] for w in t["words"])} for t in timeline])

    fonts = {}
    def font(scale=1.0):
        px = int(round(SIZE * scale))
        if px not in fonts: fonts[px] = ImageFont.truetype(fpath, px)
        return fonts[px]
    space = font().getlength(" ")
    def layout(ws):
        lines, line, lw = [], [], 0
        for w in ws:
            wd = font().getlength(w["text"]); add = wd if not line else lw + space + wd
            if line and add > MAXW: lines.append((line, lw)); line, lw = [], 0; add = wd
            line.append((w, wd)); lw = add
        lines.append((line, lw))
        lh = SIZE * 1.18; y0 = BH / 2 - lh * len(lines) / 2; pos = []
        for li, (line, lw) in enumerate(lines):
            x = (BW - lw) / 2
            for w, wd in line: pos.append((w, x, y0 + li * lh, wd)); x += wd + space
        return pos
    pop = lambda t: 1.0 if t < 0 or t > 0.12 else 1.0 + 0.08 * (t / 0.06 if t < 0.06 else (0.12 - t) / 0.06)

    def active_word(cap, t):
        a = None
        for w in cap["words"]:
            if w["start"] - 0.03 <= t: a = w
        return a

    def render(cap, t):
        img = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
        if not cap: return img
        pos = layout(cap["words"]); d = ImageDraw.Draw(img)
        x0 = min(p[1] for p in pos) - 30; x1 = max(p[1] + p[3] for p in pos) + 30
        y0 = min(p[2] for p in pos) - 10; y1 = max(p[2] for p in pos) + SIZE * 1.18 + 6
        back = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
        ImageDraw.Draw(back).rounded_rectangle((x0, y0, x1, y1), radius=28, fill=(10, 10, 12, BACK)); img.alpha_composite(back)
        act = active_word(cap, t)
        for w, x, y, wd in pos:
            on = w is act and t < w["end"] + 0.25
            color = KEY if w.get("key") else (HL if on else WHITE)
            s = pop(t - w["start"] + 0.03) if on else 1.0; f = font(s); sw = f.getlength(w["text"])
            d.text((x + wd / 2 - sw / 2, y + SIZE * 0.55 - SIZE * s * 0.55), w["text"], font=f, fill=color + (255,),
                   stroke_width=STROKE, stroke_fill=(0, 0, 0, 255))
        return img

    out = project.w("captions.mov")
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
                          "-s", f"{BW}x{BH}", "-r", str(fps), "-i", "-", "-c:v", "qtrle", out], stdin=subprocess.PIPE)
    last_key, frame = None, None
    for i in range(int(round(dur * fps))):
        t = i / fps
        cap = next((x for x in timeline if x["start"] <= t < x["end"]), None)
        act = active_word(cap, t) if cap else None
        key = (id(cap), id(act), act is not None and t - act["start"] + 0.03 <= 0.12 and i)
        if key != last_key: frame = np.asarray(render(cap, t)).tobytes(); last_key = key
        p.stdin.write(frame)
    p.stdin.close(); p.wait()
    assert all(a["end"] <= b["start"] for a, b in zip(timeline, timeline[1:])), "overlapping captions"
    print(f"captions: {len(timeline)} captions, {min(len(t['words']) for t in timeline)}-"
          f"{max(len(t['words']) for t in timeline)} words each -> {out}")
