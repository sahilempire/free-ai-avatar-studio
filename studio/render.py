"""Final composite + export + cover.
Layers: character track (blurred under pieces with blur_under) -> B-roll -> character PiP circle (face-tracked, during
B-roll) -> overlays -> captions -> watermark (off during B-roll). Audio: work/audio/mix_master.wav (the VO is the clock).
Export: H.264 High, CRF 18 capped at 11 Mbit/s (Instagram limit friendly), yuv420p, faststart, AAC 48 kHz 320k.
"""
import json, subprocess
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
from .config import font_path, hex_rgb


def pip_video(project, tl):
    cfg = project.get("pip", default={}); P = cfg.get("size", 300); OW, OH = project.width, project.height
    track = json.load(open(project.w("face_track.json"))); wins = [(b["start"], b["end"]) for b in tl["broll"]]
    yy, xx = np.mgrid[0:P, 0:P]; r = np.hypot(xx - P / 2 + 0.5, yy - P / 2 + 0.5)
    disk = np.clip(P / 2 - 7 - r, 0, 1); ring = np.clip(P / 2 - r, 0, 1) * (1 - disk)
    cap = cv2.VideoCapture(project.w("track.mp4"))
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{P}x{P}",
                            "-r", str(project.fps), "-i", "-", "-c:v", "qtrle", project.w("pip.mov")], stdin=subprocess.PIPE)
    for i in range(len(track)):
        ok, fr = cap.read()
        if not ok: break
        t = i / project.fps; out = np.zeros((P, P, 4), np.uint8)
        if any(a - 0.01 <= t <= b + 0.01 for a, b in wins):
            x, y, fw = track[i]; side = max(fw * 2.2, 220)
            x0, y0 = int(np.clip(x - side / 2, 0, OW - side)), int(np.clip(y - side * 0.46, 0, OH - side))
            crop = cv2.resize(fr[y0: y0 + int(side), x0: x0 + int(side)], (P, P), interpolation=cv2.INTER_AREA)
            rgb = crop[..., ::-1].astype(np.float32) * disk[..., None] + 255 * ring[..., None]
            out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8); out[..., 3] = (np.clip(disk + ring, 0, 1) * 255).astype(np.uint8)
        enc.stdin.write(out.tobytes())
    enc.stdin.close(); enc.wait(); cap.release()
    return cfg.get("x", 44), cfg.get("y", project.height - 380 - P - 4)      # bottom-left, above Instagram's UI


def run(project, name=None):
    tl = project.load("timeline.json"); DUR = tl["duration"]; fps = project.fps
    name = name or project.get("name", default="reel")
    px, py = pip_video(project, tl)
    wm_text = project.brand.get("watermark")
    if wm_text:
        wm = Image.new("RGBA", (400, 70), (0, 0, 0, 0))
        ImageDraw.Draw(wm).text((398, 35), wm_text, font=ImageFont.truetype(font_path("Montserrat-ExtraBold"), 40), fill=(255, 255, 255, 153),
                                anchor="rm", stroke_width=2, stroke_fill=(0, 0, 0, 90))
        wm.save(project.w("watermark.png"))
    cap_y = project.get("captions", "y_center", default=int(project.height * 0.62)) - project.get("captions", "band_height", default=440) // 2
    plan = [(project.w("broll", f"{b['id']}.mov"), b["start"], b["end"], 0, 0) for b in tl["broll"]]
    plan.append((project.w("pip.mov"), 0.0, DUR, px, py))
    plan += [(project.w("broll", f"{o['id']}.mov"), o["start"], o["end"], 0, 0) for o in tl["overlays"]]
    plan.append((project.w("captions.mov"), 0.0, DUR, 0, cap_y))
    inputs = ["-i", project.w("track.mp4")]
    for path, start, end, x, y in plan:
        inputs += (["-itsoffset", f"{start - 0.005:.4f}"] if start > 0 else []) + ["-i", path]     # first frame ready on its frame
    if wm_text: inputs += ["-loop", "1", "-i", project.w("watermark.png")]
    inputs += ["-i", project.w("audio", "mix_master.wav")]
    n = 1 + len(plan); WM = n if wm_text else None; AUD = n + (1 if wm_text else 0)
    blur = [b for b in tl["broll"] if b.get("blur_under")]
    en = "+".join(f"between(t,{b['start']:.4f},{b['end']:.4f})" for b in blur) or "0"
    g = [f"[0:v]boxblur=luma_radius=22:luma_power=2:enable='{en}'[b0]"]; prev = "b0"
    for k, (path, start, end, x, y) in enumerate(plan, start=1):     # hard cuts; 5 ms tolerance on the frame grid
        g.append(f"[{prev}][{k}:v]overlay={x}:{y}:eof_action=repeat:enable='between(t,{start - 0.005:.4f},{end - 0.005:.4f})'[v{k}]"); prev = f"v{k}"
    if WM:
        off = "+".join(f"between(t,{b['start']:.3f},{b['end']:.3f})" for b in tl["broll"]) or "0"
        g.append(f"[{prev}][{WM}:v]overlay=W-w-36:226:shortest=0:enable='not({off})'[vw]"); prev = "vw"
    g.append(f"[{prev}]trim=duration={DUR:.3f},setpts=PTS-STARTPTS,fps={fps},format=yuv420p[vout]")
    out = f"{project.out}/{name}.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(g),
                    "-map", "[vout]", "-map", f"{AUD}:a", "-t", f"{DUR:.3f}", "-c:v", "libx264", "-profile:v", "high", "-preset", "slow",
                    "-crf", "18", "-maxrate", "11M", "-bufsize", "22M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
                    "-movflags", "+faststart", out], check=True)
    cover(project)
    pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "json", out]))
    print(f"render: {out} ({float(pr['format']['duration']):.2f}s, {int(pr['format']['size']) / 1e6:.1f} MB)")


def cover(project):
    c = project.get("cover", default=None)
    if not c: return
    OW, OH = project.width, project.height
    cap = cv2.VideoCapture(project.w("track.mp4")); cap.set(cv2.CAP_PROP_POS_FRAMES, int(c.get("time", 1.4) * project.fps))
    ok, fr = cap.read(); cap.release()
    cov = Image.fromarray(fr[..., ::-1]).convert("RGBA"); shade = Image.new("RGBA", cov.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(shade)
    for yv in range(1100, OH): sd.line([(0, yv), (OW, yv)], fill=(10, 10, 12, int(235 * min(1, (yv - 1100) / 380))))
    cov.alpha_composite(shade); d = ImageDraw.Draw(cov); anton = ImageFont.truetype(font_path("Anton"), 150)
    colors = {"white": (255, 255, 255), "accent": hex_rgb(project.brand["accent"]), "highlight": hex_rgb(project.brand["highlight"])}
    for i, (line, col) in enumerate(c.get("lines", [])):
        d.text((OW / 2, 1230 + 170 * i), line, font=anton, fill=colors.get(col, (255, 255, 255)), anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))
    if c.get("pill"):
        mont = ImageFont.truetype(font_path("Montserrat-ExtraBold"), 44); pw = mont.getlength(c["pill"]) / 2 + 34
        y = 1230 + 170 * len(c.get("lines", [])) - 70
        d.rounded_rectangle((OW / 2 - pw, y, OW / 2 + pw, y + 70), 35, fill=colors["highlight"])
        d.text((OW / 2, y + 35), c["pill"], font=mont, fill=(14, 14, 16), anchor="mm")
    cov.convert("RGB").save(f"{project.out}/cover.png"); print(f"cover: {project.out}/cover.png")
