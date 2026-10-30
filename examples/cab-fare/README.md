# Example: "iPhone pe cab mehenga?" (64 s Hinglish explainer)

A complete project for a reel with 4 scenes, 7 B-roll graphics, 2 overlays, 4 punch-ins, 12 sound cues and a music
drop. The character images and the voice-over are not included. Add your own to run it:

```
assets/voiceover.wav
assets/scene_street.png  assets/scene_cab.png  assets/scene_studio.png  assets/scene_roadside.png
```

Then `studio prep`, run a Kaggle notebook, and `studio post`. Your voice-over has to match the script in
`project.json`, so for your own content change `script.lines`, the anchors and `broll.py` together.

`broll.py` shows the patterns worth copying:
- elements that appear on spoken words (`events`)
- a phone mockup with an invented app ("RideNow"; never use real brands' UI)
- a transparent piece over the blurred character (`alpha` + `blur_under`)
- a rubber-stamp overlay
