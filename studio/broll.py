"""Renders B-roll and overlays to RGBA videos (qtrle). Pieces live in YOUR module (project.json: broll.module), which
defines DRAW = {"piece_id": draw_function}; each function is called as fn(c, t, piece) with a cairo context, the
absolute time t, and the resolved piece {start, end, events}. Built-in overlays: _ai_disclosure, _follow.
Output: work/broll/<id>.mov.  Preview one frame:  python -m studio broll --still <id> <t>
"""
import importlib.util, os, subprocess, sys
from . import draw
from .draw import *


def builtin(project):
    def ai(c, t, p):
        a = 1 - ease_out(prog(t, p["end"] - 0.3, 0.3))
        im = text_img(project.get("ai_disclosure", "text", default="AI-generated host"), "Inter-SemiBold", 30, WHITE)
        rrect(c, 40, 1470, im.width + 36, im.height + 22, 20); fill(c, (0, 0, 0), 0.55 * a); paste(c, im, 58, 1481, alpha=0.95 * a)
    def follow(c, t, p):
        k = back_out(prog(t, p["start"], 0.3))
        with scaled(c, draw.W / 2, 760, k):
            im = text_img(project.brand["follow"], "Montserrat-ExtraBold", 56, WHITE)
            rrect(c, -im.width / 2 - 40, -im.height / 2 - 24, im.width + 80, im.height + 48, 40); fill(c, draw.RED); paste(c, im, 0, 0, "cm")
    return {"_ai_disclosure": ai, "_follow": follow}


def load_pieces(project):
    draw.configure(project.brand, (project.width, project.height))
    fns = builtin(project)
    mod_path = project.get("broll", "module")
    if mod_path:
        spec = importlib.util.spec_from_file_location("project_broll", project.path(mod_path))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); fns.update(mod.DRAW)
    return fns


def frame(fn, piece, t):
    s, c = draw.new(alpha=piece["alpha"]); fn(c, t, piece); s.flush(); return draw.to_rgba(s)


def run(project, only=None, still=None):
    tl = project.load("timeline.json"); fns = load_pieces(project); fps = project.fps
    pieces = {p["id"]: p for p in tl["broll"] + tl["overlays"]}
    missing = [pid for pid in pieces if pid not in fns]
    if missing: raise SystemExit(f"no draw function for {missing} in {project.get('broll', 'module')}")
    if still:
        from PIL import Image
        pid, t = still[0], float(still[1]); out = project.w("broll", f"{pid}_{t:.2f}.png")
        Image.fromarray(frame(fns[pid], pieces[pid], t)).save(out); print(out); return
    for pid, p in pieces.items():
        if only and pid not in only: continue
        n = int(round((p["end"] - p["start"]) * fps)); out = project.w("broll", f"{pid}.mov")
        enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
                                "-s", f"{draw.W}x{draw.H}", "-r", str(fps), "-i", "-", "-c:v", "qtrle", out], stdin=subprocess.PIPE)
        for i in range(n): enc.stdin.write(frame(fns[pid], p, p["start"] + i / fps).tobytes())
        enc.stdin.close(); enc.wait(); print(f"  {pid}: {n} frames -> {out}")
