"""The character's camera track for the whole reel (W x H, 30 fps, VO length + tail).
Source "chunks": work/clips/<chunk>_output.mp4 from the fast notebook, cut frame-exactly to the manifest.
Source "scenes": work/takes/<scene_id>.mp4 from the realistic notebook (one lip-synced take per scene).
Per frame: fit to 9:16, scene grade, handheld drift (+ vibration), punch-ins centred on the tracked face, vignette,
fine grain, end freeze. Writes work/track.mp4 + work/face_track.json (face position per frame, used by the PiP).
"""
import json, math, os, shutil, subprocess
import cv2, numpy as np
from .config import vendor

GRADES = {  # (lift, gamma, gain) per channel in BGR, saturation
    "neutral":        ((0.004, 0.004, 0.004), (1.00, 1.00, 1.00), (1.00, 1.00, 1.00), 1.00),
    "night_neon":     ((0.010, 0.012, 0.030), (1.00, 1.00, 0.97), (1.00, 1.00, 1.04), 1.06),
    "daylight":       ((0.010, 0.010, 0.012), (0.98, 0.99, 1.00), (1.00, 1.01, 1.03), 1.02),
    "studio_red_rim": ((0.004, 0.004, 0.006), (1.00, 1.00, 1.00), (0.99, 0.99, 1.05), 0.98),
    "golden_hour":    ((0.004, 0.010, 0.022), (1.04, 1.01, 0.98), (0.94, 1.00, 1.07), 1.08),
}
FPS_IN = 25


def run(project, source="chunks"):
    tl = project.load("timeline.json"); fps = project.fps; OW, OH = project.width, project.height
    VO_END, DUR = tl["vo_end"], tl["duration"]; N_OUT = int(round(DUR * fps)); N_SPEECH = int(round(VO_END * fps))
    run_ = lambda cmd: subprocess.run(cmd, check=True)
    src = project.w("track_src25.mp4"); inputs, chains = [], []
    even = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    if source == "chunks":
        man = json.load(open(project.w("kit", "manifest.json")))
        for i, j in enumerate(man):
            n = round(j["end"] * FPS_IN) - round(j["start"] * FPS_IN)
            inputs += ["-i", project.w("clips", f"{j['id']}_output.mp4")]; chains.append(f"[{i}:v]{even},trim=end_frame={n},setpts=PTS-STARTPTS[v{i}]")
    else:
        for i, s in enumerate(tl["scenes"]):
            n = round(min(s["end"], VO_END) * FPS_IN) - round(s["start"] * FPS_IN)
            if n <= 0: continue
            inputs += ["-i", project.w("takes", f"{s['id']}.mp4")]
            chains.append(f"[{len(chains)}:v]fps={FPS_IN},{even},trim=end_frame={n},setpts=PTS-STARTPTS[v{len(chains)}]")
    graph = ";".join(chains) + ";" + "".join(f"[v{i}]" for i in range(len(chains))) + f"concat=n={len(chains)}:v=1:a=0[v]"
    run_(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[v]",
          "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", src])
    f25, f30 = project.w("f25", "x"), project.w("f30", "x"); f25, f30 = os.path.dirname(f25), os.path.dirname(f30)
    for d in (f25, f30): shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    run_(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", src, f"{f25}/%06d.png"])
    rife = vendor("bin", "rife")
    run_([f"{rife}/rife-ncnn-vulkan", "-i", f25, "-o", f30, "-m", f"{rife}/rife-v4.6", "-n", str(N_SPEECH), "-f", "%06d.png"])
    frames = sorted(os.listdir(f30)); assert len(frames) == N_SPEECH, f"RIFE gave {len(frames)} frames, wanted {N_SPEECH}"

    def lut(g):
        lift, gamma, gain, _ = g; x = np.arange(256) / 255.0
        return np.stack([np.clip((lift[c] + (1 - lift[c]) * x ** (1 / gamma[c])) * gain[c], 0, 1) * 255 for c in range(3)], 1).astype(np.uint8)
    grades = {k: (v, lut(v)) for k, v in GRADES.items()}
    yy, xx = np.mgrid[0:OH, 0:OW]
    vig = (1 - 0.28 * np.clip(((xx - OW / 2) / (OW * 0.62)) ** 2 + ((yy - OH * 0.42) / (OH * 0.62)) ** 2, 0, 1) ** 1.4)[..., None].astype(np.float32)
    rng = np.random.default_rng(11)
    scene_at = lambda t: next((s for s in tl["scenes"] if s["start"] <= t < s["end"]), tl["scenes"][-1])
    def noise(t, seed, freqs=(0.11, 0.23, 0.37)):
        ph = np.random.default_rng(seed).uniform(0, 2 * math.pi, len(freqs))
        return sum(math.sin(2 * math.pi * f * t + p) / (k + 1) for k, (f, p) in enumerate(zip(freqs, ph)))
    punch = lambda t: any(p["start"] <= t < p["end"] for p in tl["punch_ins"])
    det = cv2.FaceDetectorYN.create(vendor("models", "face_detection_yunet_2023mar.onnx"), "", (360, 640), 0.6)
    freeze_at = tl["freeze"]["start"] if tl.get("freeze") else 1e9
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OW}x{OH}",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p", project.w("track.mp4")],
                           stdin=subprocess.PIPE)
    face, held, track = None, None, []
    for i in range(N_OUT):
        t = i / fps
        if t >= freeze_at and held is not None: img = held
        else:
            img = cv2.imread(f"{f30}/{frames[min(i, N_SPEECH - 1)]}"); h, w = img.shape[:2]; s = max(OW / w, OH / h)
            img = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_LANCZOS4)
            y0, x0 = (img.shape[0] - OH) // 2, (img.shape[1] - OW) // 2; img = img[y0: y0 + OH, x0: x0 + OW]
            img = cv2.addWeighted(img, 1.25, cv2.GaussianBlur(img, (0, 0), 1.2), -0.25, 0)
            if t >= freeze_at - 1 / fps: held = img
        sc = scene_at(t); g, L = grades.get(sc["grade"], grades["neutral"])
        _, f = det.detect(cv2.resize(img, (360, 640)))
        if f is not None and len(f):
            x, y, fw, fh = f[0][:4] * (OW / 360); c_ = np.array([x + fw / 2, y + fh / 2, fw])
            face = c_ if face is None or np.linalg.norm(c_[:2] - face[:2]) > 200 else face * 0.8 + c_ * 0.2
        fc = face if face is not None else np.array([OW * 0.52, OH * 0.33, OW * 0.26])
        vib = sc.get("vibration")
        z = 1.03 + 0.012 * noise(t, 1, (0.05, 0.09))
        dx = 7 * noise(t, 2) + (1.6 * math.sin(2 * math.pi * 11.3 * t) if vib else 0)
        dy = 6 * noise(t, 3) + (2.0 * math.sin(2 * math.pi * 9.1 * t + 1) if vib else 0)
        cx, cy = OW / 2, OH / 2
        if punch(t) and t < freeze_at: z *= 1.15; cx, cy = fc[0], fc[1] + OH * 0.06
        M = cv2.getRotationMatrix2D((cx, cy), math.degrees(0.0025 * noise(t, 4, (0.07, 0.13))), z); M[0, 2] += dx; M[1, 2] += dy
        out = cv2.warpAffine(img, M, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        out = np.stack([cv2.LUT(out[..., k], L[:, k]) for k in range(3)], -1)
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)[..., None].astype(np.float32)
        o = (gray + (out.astype(np.float32) - gray) * g[3]) * vig + rng.normal(0, 7.0, (OH, OW, 1)).astype(np.float32)
        enc.stdin.write(np.clip(o, 0, 255).astype(np.uint8).tobytes())
        p = M @ np.array([fc[0], fc[1], 1.0]); track.append([round(float(p[0]), 1), round(float(p[1]), 1), round(float(fc[2] * z), 1)])
    enc.stdin.close(); enc.wait()
    json.dump(track, open(project.w("face_track.json"), "w")); shutil.rmtree(f25); shutil.rmtree(f30)
    print(f"track: {N_OUT} frames ({N_OUT / fps:.2f}s) from {source} -> {project.w('track.mp4')}")
