#!/usr/bin/env bash
# One-time setup on macOS (Apple Silicon or Intel) or Linux: Python env, fonts, face detector, RIFE.
# System packages first:  macOS: brew install ffmpeg python@3.11 cairo pkg-config
#                         Linux: sudo apt install ffmpeg python3-venv libcairo2-dev pkg-config libvulkan1
set -euo pipefail
cd "$(dirname "$0")"
V=vendor; mkdir -p "$V"/{fonts,models,bin}
PY=${PYTHON:-python3.11}; command -v "$PY" >/dev/null || PY=python3
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -e ".[dev]" fonttools

echo "== fonts (Google Fonts, OFL)"
G=https://github.com/google/fonts/raw/main/ofl
curl -fsSL -o "$V/fonts/Anton-Regular.ttf" "$G/anton/Anton-Regular.ttf"
curl -fsSL -o "$V/fonts/Montserrat-VF.ttf" "$G/montserrat/Montserrat%5Bwght%5D.ttf"
curl -fsSL -o "$V/fonts/Inter-VF.ttf" "$G/inter/Inter%5Bopsz,wght%5D.ttf"
.venv/bin/python - "$V/fonts" <<'PY'
import sys
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
d = sys.argv[1]
for vf, cuts in {"Montserrat-VF.ttf": [("Montserrat-ExtraBold", 800), ("Montserrat-Bold", 700)],
                 "Inter-VF.ttf": [("Inter-Regular", 400), ("Inter-SemiBold", 600), ("Inter-Bold", 700)]}.items():
    for name, wght in cuts:
        axes = {"wght": wght} | ({"opsz": 14} if vf.startswith("Inter") else {})
        instantiateVariableFont(TTFont(f"{d}/{vf}"), axes, updateFontNames=True).save(f"{d}/{name}.ttf")
print("static font weights ready")
PY

echo "== face detector (OpenCV Zoo YuNet)"
curl -fsSL -o "$V/models/face_detection_yunet_2023mar.onnx" \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx

echo "== RIFE frame interpolation (ncnn/Vulkan; Apple GPU via MoltenVK on macOS)"
case "$(uname -s)" in Darwin) R=rife-ncnn-vulkan-20221029-macos;; *) R=rife-ncnn-vulkan-20221029-ubuntu;; esac
curl -fsSL -o /tmp/rife.zip "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/$R.zip"
rm -rf "$V/bin/rife" "$V/bin/$R"; unzip -q -o /tmp/rife.zip -d "$V/bin" && mv "$V/bin/$R" "$V/bin/rife" && rm /tmp/rife.zip
chmod +x "$V/bin/rife/rife-ncnn-vulkan"
[ "$(uname -s)" = Darwin ] && xattr -dr com.apple.quarantine "$V/bin" 2>/dev/null || true
echo "done. Activate with: source .venv/bin/activate   then: studio --help"
