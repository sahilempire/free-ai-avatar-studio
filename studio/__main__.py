"""studio CLI.  Usage: studio <step> [-p project.json]

  align      exact script -> word timings (work/words.json)
  timeline   anchors -> scenes, B-roll windows, punch-ins, sound cues (work/timeline.json)
  kit        voice-over -> lip-sync chunks + images + manifest (work/kit.zip, upload to Kaggle)
             ... run a Kaggle notebook, put its clips in work/clips/ (fast) or work/takes/ (realistic) ...
  track      character camera track (--source chunks|scenes)
  captions   karaoke caption band
  audio      music + SFX + ambience + ducking + master
  broll      graphics (--only id ... | --still id t)
  render     final video + cover (--name)
  prep       align + timeline + kit           post   captions + audio + broll + track + render
"""
import argparse, sys
from .config import Project


def main(argv=None):
    ap = argparse.ArgumentParser(prog="studio", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["align", "timeline", "kit", "track", "captions", "audio", "broll", "render", "cover", "prep", "post"])
    ap.add_argument("-p", "--project", default="project.json")
    ap.add_argument("--source", default="chunks", choices=["chunks", "scenes"], help="track: fast-notebook chunks or realistic scene takes")
    ap.add_argument("--only", nargs="*", help="broll: render only these piece ids")
    ap.add_argument("--still", nargs=2, metavar=("ID", "T"), help="broll: write one PNG frame")
    ap.add_argument("--name", help="render: output file name (without .mp4)")
    a = ap.parse_args(argv)
    p = Project(a.project)
    from . import align, timeline, kit, track, captions, audio, broll, render
    steps = {"align": lambda: align.run(p), "timeline": lambda: timeline.run(p), "kit": lambda: kit.run(p),
             "track": lambda: track.run(p, a.source), "captions": lambda: captions.run(p), "audio": lambda: audio.run(p),
             "broll": lambda: broll.run(p, a.only, a.still), "render": lambda: render.run(p, a.name), "cover": lambda: render.cover(p)}
    plan = {"prep": ["align", "timeline", "kit"], "post": ["captions", "audio", "broll", "track", "render"]}.get(a.step, [a.step])
    for s in plan:
        print(f"== {s}"); steps[s]()


if __name__ == "__main__":
    sys.exit(main())
