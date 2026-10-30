"""Lip-sync kit for Kaggle: the voice-over cut into chunks (<= 4.2 s, cut at the biggest pauses, never across a
scene), one image per scene, and manifest.json. Output: work/kit/ + work/kit.zip (upload kit.zip as a Kaggle dataset).

manifest.json rows: {id, image, audio, start, end, frames, scene, prompt}. scenes.json: one row per scene.
"""
import json, math, os, shutil, zipfile

MAX_CHUNK = 4.2


def cut_points(words, start, end, max_len=MAX_CHUNK):
    """Split [start, end) at word gaps so every piece is <= max_len; prefer the widest gaps."""
    inner = [w for w in words if start <= w["start"] and w["end"] <= end]
    gaps = [((a["end"] + b["start"]) / 2, b["start"] - a["end"]) for a, b in zip(inner, inner[1:])]
    pieces = [(start, end)]
    while True:
        long = [(a, b) for a, b in pieces if b - a > max_len]
        if not long: return pieces
        a, b = long[0]
        cands = [(g, t) for t, g in gaps if a + 0.6 < t < b - 0.6]            # keep pieces >= 0.6 s
        if not cands:                                                          # no pause: cut mid-way
            t = (a + b) / 2
        else:
            # widest gap, mildly favouring the middle so pieces stay balanced
            t = max(cands, key=lambda c: c[0] - 0.02 * abs(c[1] - (a + b) / 2))[1]
        i = pieces.index((a, b)); pieces[i:i + 1] = [(a, round(t, 3)), (round(t, 3), b)]


def run(project):
    import soundfile as sf
    tl, words = project.load("timeline.json"), project.load("words.json")
    kit = project.w("kit", "x"); kit = os.path.dirname(kit)
    shutil.rmtree(kit, ignore_errors=True); os.makedirs(f"{kit}/audio"); os.makedirs(f"{kit}/images")
    vo, sr = sf.read(project.voiceover)
    manifest, scenes, n = [], [], 0
    for s in tl["scenes"]:
        end = min(s["end"], tl["vo_end"])
        if end <= s["start"]: continue
        img = os.path.basename(project.path(s["image"])); shutil.copy(project.path(s["image"]), f"{kit}/images/{img}")
        ids = []
        for a, b in cut_points(words, s["start"], end):
            cid = f"c{n:02d}"; n += 1; ids.append(cid)
            sf.write(f"{kit}/audio/{cid}.wav", vo[int(round(a * sr)): int(round(b * sr))], sr)
            frames = math.ceil((b - a) * 25); frames += (4 - (frames - 1) % 4) % 4          # 4k+1 grid
            manifest.append({"id": cid, "image": f"images/{img}", "audio": f"audio/{cid}.wav", "start": a, "end": b,
                             "frames": frames, "scene": s["id"], "prompt": s["prompt"]})
        scenes.append({"id": s["id"], "image": f"images/{img}", "start": s["start"], "end": end, "dur": round(end - s["start"], 3),
                       "chunks": ids, "prompt": s["prompt"]})
    json.dump(manifest, open(f"{kit}/manifest.json", "w"), ensure_ascii=False, indent=1)
    json.dump(scenes, open(f"{kit}/scenes.json", "w"), ensure_ascii=False, indent=1)
    z = project.w("kit.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        for root, _, files in os.walk(kit):
            for name in files: f.write(os.path.join(root, name), os.path.relpath(os.path.join(root, name), kit))
    longest = max(m["end"] - m["start"] for m in manifest)
    print(f"kit: {len(manifest)} chunks in {len(scenes)} scenes (longest {longest:.2f}s) -> {z}")
    return manifest
