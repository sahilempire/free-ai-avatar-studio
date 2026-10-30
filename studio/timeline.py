"""The edit plan: scenes, B-roll windows, overlays, punch-ins, sound cues, music, freeze. Output: work/timeline.json

Every time in project.json is an ANCHOR, so a re-recorded voice-over re-times the whole edit:
    3.2                                   seconds
    {"word": "Indian"}                    start of the first "Indian" (punctuation/case ignored)
    {"word": "nahi", "nth": 5, "edge": "end", "offset": 0.08}
    {"scene": "cab"}                      start of a scene ("edge": "end" for its end)
    {"event": "B1_split_phones.iphone_fare", "offset": 0.6}   an event of a B-roll piece
    "vo_end"                              end of the voice-over
"""
import re
from .align import norm


class AnchorError(ValueError):
    pass


def make_resolver(words, vo_end, scenes=None, pieces=None):
    def resolve(a):
        if a is None: return None
        if isinstance(a, (int, float)): return float(a)
        if a == "vo_end": return vo_end
        off = a.get("offset", 0.0)
        if "word" in a:
            hits = [w for w in words if norm(w["text"]) == norm(a["word"])]
            nth = a.get("nth", 1)
            if len(hits) < nth:
                near = sorted({w["text"] for w in words if norm(a["word"])[:3] in norm(w["text"])})[:8]
                raise AnchorError(f"word {a['word']!r} #{nth} not in the script ({len(hits)} found). Similar: {near}")
            w = hits[nth - 1]
            return round((w["end"] if a.get("edge") == "end" else w["start"]) + off, 3)
        if "scene" in a:
            s = next((s for s in scenes or [] if s["id"] == a["scene"]), None)
            if not s: raise AnchorError(f"unknown scene {a['scene']!r}")
            return round((s["end"] if a.get("edge") == "end" else s["start"]) + off, 3)
        if "event" in a:
            pid, ev = a["event"].split(".", 1)
            return round(pieces[pid]["events"][ev] + off, 3)
        raise AnchorError(f"can't read anchor {a!r}")
    return resolve


def run(project):
    words = project.load("words.json")
    import soundfile as sf
    vo_end = round(sf.info(project.voiceover).duration, 3)
    fps, tail = project.fps, project.tail
    duration = round(int((vo_end + tail) * fps) / fps, 3)               # whole frames only
    snap = lambda x: round(round(x * fps) / fps, 4)

    resolve = make_resolver(words, vo_end)
    scenes = []
    for i, s in enumerate(project.get("scenes")):
        start = 0.0 if i == 0 else resolve(s["start"])
        scenes.append({"id": s["id"], "image": s["image"], "start": snap(start), "grade": s.get("grade", "neutral"),
                       "vibration": s.get("vibration", False), "ambience": s.get("ambience", "none"),
                       "prompt": s.get("prompt", "")})
    for a, b in zip(scenes, scenes[1:]): a["end"] = b["start"]
    scenes[-1]["end"] = duration
    resolve = make_resolver(words, vo_end, scenes)

    pieces = {}
    def piece(p, kind):
        item = {"id": p["id"], "kind": kind, "start": snap(resolve(p["from"])), "end": snap(resolve(p["to"])),
                "alpha": p.get("alpha", kind == "overlay"), "blur_under": p.get("blur_under", False),
                "events": {k: resolve(v) for k, v in p.get("events", {}).items()}}
        pieces[item["id"]] = item
        return item
    broll = [piece(p, "broll") for p in project.get("broll", "pieces", default=[])]
    overlays = [piece(p, "overlay") for p in project.get("broll", "overlays", default=[])]
    if project.get("ai_disclosure", "enabled", default=False):
        secs = project.get("ai_disclosure", "seconds", default=3.0)
        overlays.append({"id": "_ai_disclosure", "kind": "overlay", "start": 0.0, "end": snap(secs), "alpha": True,
                         "blur_under": False, "events": {}})
    if project.brand.get("follow"):
        overlays.append({"id": "_follow", "kind": "overlay", "start": snap(vo_end - 0.5), "end": duration, "alpha": True,
                         "blur_under": False, "events": {}})
    resolve = make_resolver(words, vo_end, scenes, pieces)
    punch_ins = [{"label": p.get("label", ""), "start": snap(resolve(p["from"])), "end": snap(resolve(p["to"]))}
                 for p in project.get("punch_ins", default=[])]
    sfx = [{"t": b["start"], "kind": "whoosh"} for b in broll] if project.get("sfx_auto_whoosh", default=True) else []
    sfx += [{"t": resolve(e["at"]), "kind": e["kind"]} for e in project.get("sfx", default=[])]
    m = project.get("music", default={})
    drop_at = resolve(m["drop_before"]) if m.get("drop_before") else None
    music = {"bpm": m.get("bpm", 92), "file": project.path(m["file"]) if m.get("file") else None,
             "drop": [round(drop_at - m.get("drop_seconds", 0.4), 3), drop_at] if drop_at else None,
             "harder_from": drop_at, "end": duration}
    fz = project.get("freeze", default=None)
    freeze = {"start": resolve(fz["from"]) + fz.get("hold_after", 0.0)} if fz else None

    tl = {"vo_end": vo_end, "duration": duration, "fps": fps, "scenes": scenes, "broll": broll, "overlays": overlays,
          "punch_ins": punch_ins, "sfx": sorted(sfx, key=lambda e: e["t"]), "music": music, "freeze": freeze}
    check(tl)
    project.save("timeline.json", tl)
    for b in broll + overlays: print(f"  {b['kind']:7} {b['id']:24} {b['start']:7.2f} - {b['end']:7.2f}")
    print(f"timeline: {len(scenes)} scenes, {len(broll)} B-roll, {len(overlays)} overlays, {len(punch_ins)} punch-ins, "
          f"{len(sfx)} sound cues, {duration:.2f}s -> {project.w('timeline.json')}")
    return tl


def check(tl):
    """B-roll pieces and punch-ins must not overlap; everything must sit inside the video."""
    spans = sorted([(b["start"], b["end"], b["id"]) for b in tl["broll"]] +
                   [(p["start"], p["end"], "punch " + p["label"]) for p in tl["punch_ins"]])
    for a, b in zip(spans, spans[1:]):
        if a[1] > b[0] + 1e-6: raise ValueError(f"overlap: {a[2]} ({a[0]}-{a[1]}) and {b[2]} ({b[0]}-{b[1]})")
    for s in spans:
        if not (0 <= s[0] < s[1] <= tl["duration"] + 1e-6): raise ValueError(f"bad window {s}")
