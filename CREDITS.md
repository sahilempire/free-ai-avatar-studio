# Credits and licenses

This repo's own code is MIT. It downloads and runs the models and tools below; each keeps its own license, and
**you are responsible for following them**, especially for commercial use. Licenses as listed by each project in
October 2026; check the linked pages for changes.

| Component | Used for | License |
|---|---|---|
| [EchoMimicV3](https://github.com/antgroup/echomimic_v3) code + [Flash weights](https://huggingface.co/BadToBest/EchoMimicV3) | fast lip sync (Kaggle) | Apache-2.0 |
| [Wan2.1-Fun-V1.1-1.3B-InP](https://huggingface.co/alibaba-pai/Wan2.1-Fun-V1.1-1.3B-InP) | base video model, moving takes | Apache-2.0 |
| [VideoX-Fun](https://github.com/aigc-apps/VideoX-Fun) | image-to-video runner | Apache-2.0 |
| [LatentSync](https://github.com/bytedance/LatentSync) code / [1.5 weights](https://huggingface.co/ByteDance/LatentSync-1.5) | realistic lip sync (Kaggle) | Apache-2.0 / **OpenRAIL++** (use-based restrictions) |
| [chinese-wav2vec2-base](https://huggingface.co/TencentGameMate/chinese-wav2vec2-base) | audio features for EchoMimic | MIT |
| [ctc-forced-aligner](https://github.com/MahmoudAshraf97/ctc-forced-aligner) code / [MMS alignment model](https://huggingface.co/MahmoudAshraf/mms-300m-1130-forced-aligner) | caption word timings | BSD-2-Clause / **CC-BY-NC-4.0 (non-commercial)** |
| [RIFE ncnn Vulkan](https://github.com/nihui/rife-ncnn-vulkan) | 25 to 30 fps interpolation | MIT |
| [YuNet face detector](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) (OpenCV Zoo) | face tracking for punch-ins and the PiP | Apache-2.0 (zoo) |
| [Anton](https://fonts.google.com/specimen/Anton), [Montserrat](https://fonts.google.com/specimen/Montserrat), [Inter](https://fonts.google.com/specimen/Inter) | graphics and captions | SIL OFL 1.1 |

**Commercial use:** the MMS alignment model is non-commercial. If your reels earn money, replace the `align` step
with a commercially licensed aligner (or time captions another way) before publishing them.

Music and sound effects are synthesised in code by `studio audio` (no samples, nothing to license). If you use your
own track (`music.file`), make sure you hold the rights.
