"""Project config: one project.json drives every step. Paths in it are relative to the file."""
import json, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.environ.get("STUDIO_VENDOR", os.path.join(REPO, "vendor"))    # fonts, models, binaries (setup.sh)


def hex_rgb(h, scale=255):
    h = h.lstrip("#")
    rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return rgb if scale == 255 else tuple(v / 255 for v in rgb)


class Project:
    def __init__(self, path):
        self.file = os.path.abspath(path)
        self.dir = os.path.dirname(self.file)
        self.cfg = json.load(open(self.file, encoding="utf-8"))
        c = self.cfg
        self.fps = c.get("fps", 30)
        self.width, self.height = c.get("size", [1080, 1920])
        self.tail = c.get("tail", 0.7)
        self.voiceover = self.path(c["voiceover"])
        self.work = self.path(c.get("work_dir", "work"))
        self.out = self.path(c.get("out_dir", "out"))
        b = c.get("brand", {})
        self.brand = {"accent": b.get("accent", "#C8102E"), "highlight": b.get("highlight", "#D4AF37"),
                      "ink": b.get("ink", "#0E0E10"), "watermark": b.get("watermark"), "follow": b.get("follow")}
        for d in (self.work, self.out): os.makedirs(d, exist_ok=True)

    def path(self, rel):
        return rel if os.path.isabs(rel) else os.path.normpath(os.path.join(self.dir, rel))

    def w(self, *parts):
        """A path inside the work dir (created on demand)."""
        p = os.path.join(self.work, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def get(self, *keys, default=None):
        node = self.cfg
        for k in keys:
            if not isinstance(node, dict) or k not in node: return default
            node = node[k]
        return node

    def load(self, name):
        return json.load(open(self.w(name), encoding="utf-8"))

    def save(self, name, data):
        json.dump(data, open(self.w(name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def vendor(*parts):
    return os.path.join(VENDOR, *parts)


def font_path(name):
    aliases = {"Anton": "Anton-Regular"}
    return vendor("fonts", aliases.get(name, name) + ".ttf")
