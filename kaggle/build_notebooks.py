"""Builds the two Kaggle notebooks from the patches in kaggle/patches/ (run after editing a patch):
  lipsync_fast.ipynb       EchoMimicV3-Flash, one lip-synced clip per kit chunk, both T4s in parallel
  lipsync_realistic.ipynb  moving "takes" per scene (Wan2.1-Fun image-to-video, face pinned to the scene image at the
                           first and last frame) + one continuous LatentSync 1.5 dub per scene
Both read a kit dataset made by `studio kit` (upload work/kit.zip as a private Kaggle dataset).
"""
import base64, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
EM_COMMIT = "7e89489ca51c0d008fc1963ec6c03fc5bd0b9397"     # antgroup/echomimic_v3
LS_COMMIT = "a229c3948406bc2cf6eaf4873e662e70c6a04746"     # bytedance/LatentSync
VF_COMMIT = "e8c314fbfa494d0429bbef605c9f6112b79a7ead"     # aigc-apps/VideoX-Fun
NEG = ("blurry, low quality, deformed face, distorted face, changing face, asymmetric eyes, distorted hands, extra fingers, "
       "fused fingers, melting phone, smeared objects, flicker, warping background, text, subtitles, watermark, logo")
DEFAULT_PROMPT = ("A person talks directly to the camera with natural lip movement, natural blinking, expressive eyebrows "
                  "and subtle head movement. Realistic skin, natural light, hands steady.")


def b64(name): return base64.b64encode(open(f"{HERE}/patches/{name}", "rb").read()).decode()


def notebook(cells):
    nb = {"cells": [], "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
          "nbformat": 4, "nbformat_minor": 5}
    for i, (kind, src) in enumerate(cells):
        c = {"cell_type": kind, "id": f"c{i}", "metadata": {}, "source": src.strip("\n").splitlines(True)}
        if kind == "code": c.update(outputs=[], execution_count=None)
        nb["cells"].append(c)
    return nb


COMMON = '''
import os, glob, json, math, shutil, subprocess, threading, time, base64, re, torch
assert torch.cuda.is_available(), "Settings -> Accelerator -> GPU T4 x2"
print(torch.__version__, torch.cuda.device_count(), "x", torch.cuda.get_device_name(0))
hits = glob.glob("/kaggle/input/**/manifest.json", recursive=True)
assert hits, "Add your kit as input: upload work/kit.zip (from `studio kit`) as a Kaggle dataset, then Add Input"
KIT = os.path.dirname(hits[0]); print("kit:", KIT)
def find(rel):  # Kaggle can flatten a dataset's folders, so fall back to looking files up by name
    hits = glob.glob(f"{KIT}/{rel}") or glob.glob(f"/kaggle/input/**/{os.path.basename(rel)}", recursive=True)
    assert hits, f"not in the dataset: {rel}"; return hits[0]
LOGS = "/kaggle/working/logs"; os.makedirs(LOGS, exist_ok=True); T0 = time.time()
def sh(cmd, log, cwd=None, env=None):
    t = time.time()
    with open(f"{LOGS}/{log}.log", "w") as f:
        r = subprocess.run(cmd, shell=True, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT)
    print(f"[{(time.time()-T0)/60:6.1f}m] {log}: exit {r.returncode} in {(time.time()-t)/60:.1f} min", flush=True)
    assert r.returncode == 0, f"{log} failed:\\n" + "".join(open(f"{LOGS}/{log}.log").readlines()[-25:])
MEMPEAK, STOP = [0.0], threading.Event()
def mem_watch():  # system RAM log (two renderers at once can get OOM-killed)
    with open(f"{LOGS}/mem.log", "w") as f:
        while not STOP.is_set():
            m = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo")}
            used = (m["MemTotal"] - m["MemAvailable"]) / 2**20; MEMPEAK[0] = max(MEMPEAK[0], used)
            f.write(f"{(time.time()-T0)/60:6.1f}m used {used:5.1f} GiB\\n"); f.flush(); STOP.wait(10)
threading.Thread(target=mem_watch, daemon=True).start()
'''

FAST = notebook([
    ("markdown", """
# Free AI avatar studio: fast lip sync (EchoMimicV3-Flash on Kaggle's free T4 x2)
Part of [free-ai-avatar-studio](https://github.com/sahilempire/free-ai-avatar-studio). Turns a kit made by `studio kit`
(scene images + voice-over chunks + manifest) into one lip-synced clip per chunk, then zips them.

1. Upload `work/kit.zip` as a **private** Kaggle dataset, then **Add Input** here.
2. **Settings:** Accelerator **GPU T4 x2**, Internet **On** (needs a phone-verified Kaggle account).
3. **Run All** (or *Save Version → Save & Run All* to run in the background). About 1.5 h for 60 s of speech.
4. Download `clips.zip` from the Output panel, unzip into your project's `work/clips/`, then `studio post`.

Re-render a few clips: set `ONLY` (and `SEEDS` for a different take) and run again.
"""),
    ("code", f'''
# ---- Settings ----
SAMPLE_SIZE = 640     # ~464x848 output (upscaled locally). 768 is sharper but ~1.8x the GPU time.
STEPS = 8             # Flash is tuned for 8 steps
SEED = 43
SEEDS = {{}}            # per-clip seed for re-renders, e.g. {{"c03": 44}}
ONLY = None           # e.g. ["c00", "c01"] to test or re-render some clips
NEG = {NEG!r}
DEFAULT_PROMPT = {DEFAULT_PROMPT!r}
{COMMON}
DTYPE = "bfloat16" if torch.cuda.get_device_capability(0)[0] >= 8 else "float16"   # T4: native fp16
OUT, MODELS, REPO = "/kaggle/working/clips", "/tmp/em3_models", "/tmp/echomimic_v3"
os.makedirs(OUT, exist_ok=True); os.makedirs(MODELS, exist_ok=True)
'''),
    ("code", f'''
# ---- Code + dependencies (Kaggle's torch is kept) ----
if not os.path.exists(REPO):
    sh(f"git clone -q https://github.com/antgroup/echomimic_v3.git {{REPO}} && cd {{REPO}} && git checkout -q {EM_COMMIT}", "clone")
sh('pip install -q "diffusers==0.33.1" "transformers==4.51.3" "accelerate==1.6.0" einops safetensors timm tomesd torchdiffeq '
   'torchsde decord omegaconf sentencepiece ftfy func_timeout "moviepy==2.2.1" librosa pyloudnorm "imageio[ffmpeg]" av soundfile hf_transfer', "deps")
'''),
    ("code", '''
# ---- Weights (~24 GB, kept in /tmp) ----
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
from huggingface_hub import snapshot_download, hf_hub_download
BASE = f"{MODELS}/Wan2.1-Fun-V1.1-1.3B-InP"     # folder name matters for TeaCache
snapshot_download("alibaba-pai/Wan2.1-Fun-V1.1-1.3B-InP", local_dir=BASE, allow_patterns=["*.json", "*.pth", "*.safetensors", "google/*", "xlm-roberta-large/*"])
W2V = f"{MODELS}/chinese-wav2vec2-base"
snapshot_download("TencentGameMate/chinese-wav2vec2-base", local_dir=W2V, allow_patterns=["config.json", "preprocessor_config.json", "pytorch_model.bin"])
hf_hub_download("BadToBest/EchoMimicV3", "echomimicv3-flash-pro/diffusion_pytorch_model.safetensors", local_dir=f"{MODELS}/flash")
FLASH = f"{MODELS}/flash/echomimicv3-flash-pro/diffusion_pytorch_model.safetensors"
print("weights ready:", os.path.exists(FLASH))
'''),
    ("code", f'''
# ---- Patch upstream into a batch renderer; pad each chunk so the clip covers all of its speech; split across GPUs ----
for name, blob in (("patch_echomimic.py", "{b64('patch_echomimic.py')}"), ("embed_prompts.py", "{b64('embed_prompts.py')}")):
    open(f"{{REPO}}/{{name}}", "w").write(base64.b64decode(blob).decode())
sh(f"cd {{REPO}} && git checkout -q -- . && python patch_echomimic.py {{REPO}}", "patch")
import numpy as np, soundfile as sf
RUN_KIT = "/tmp/kit_run"; os.makedirs(f"{{RUN_KIT}}/audio", exist_ok=True); os.makedirs(f"{{RUN_KIT}}/images", exist_ok=True)
jobs = json.load(open(f"{{KIT}}/manifest.json"))
if ONLY: jobs = [j for j in jobs if j["id"] in ONLY]
for j in jobs:
    if not os.path.exists(f"{{RUN_KIT}}/{{j['image']}}"): os.symlink(find(j["image"]), f"{{RUN_KIT}}/{{j['image']}}")
    y, sr = sf.read(find(j["audio"]))
    need = math.ceil(len(y) / sr * 25); n = (need + 2) // 4 * 4 + 1        # upstream rounds frames DOWN twice
    pad = max(0, round((n + 0.5) / 25 * sr) - len(y))
    sf.write(f"{{RUN_KIT}}/{{j['audio']}}", np.concatenate([y, np.zeros((pad,) + y.shape[1:], y.dtype)]), sr)
    j["frames"] = max(j["frames"], n); j["prompt"] = j.get("prompt") or DEFAULT_PROMPT
    if j["id"] in SEEDS: j["seed"] = SEEDS[j["id"]]
json.dump(jobs, open("/tmp/jobs.json", "w"))
N_GPU = torch.cuda.device_count(); bins = [[] for _ in range(N_GPU)]
for j in sorted(jobs, key=lambda j: -j["frames"]): min(bins, key=lambda b: sum(x["frames"] for x in b)).append(j)
bins = [b for b in bins if b]; N_GPU = len(bins)
for g, b in enumerate(bins):
    json.dump(b, open(f"/tmp/jobs_gpu{{g}}.json", "w")); print(f"gpu{{g}}:", [x["id"] for x in b], sum(x["frames"] for x in b), "frames")
'''),
    ("code", '''
# ---- Render: encode prompts once (no 11 GB T5 per renderer), one renderer per GPU, restart if killed ----
EMB = "/tmp/emb.pt"
if not os.path.exists(EMB):
    r = subprocess.run(["python", "embed_prompts.py", BASE, "config/config.yaml", "/tmp/jobs.json", NEG, EMB], cwd=REPO); assert r.returncode == 0
common = (f'--kit_dir {RUN_KIT} --embeds {EMB} --config_path config/config.yaml --model_name "{BASE}" --transformer_path "{FLASH}" '
          f'--wav2vec_model_dir "{W2V}" --save_path "{OUT}" --num_inference_steps {STEPS} --sampler_name Flow_Unipc --guidance_scale 6.0 '
          f'--audio_guidance_scale 3.0 --audio_scale 1.0 --neg_scale 1.0 --neg_steps 0 --seed {SEED} --enable_teacache --teacache_threshold 0.1 '
          f'--num_skip_start_steps 5 --weight_dtype {DTYPE} --sample_size {SAMPLE_SIZE} {SAMPLE_SIZE} --fps 25 --shift 5.0')
rc = {}
def run(gpu):
    cmd = f"cd {REPO} && CUDA_VISIBLE_DEVICES={gpu} python -u batch.py --manifest /tmp/jobs_gpu{gpu}.json {common}"
    with open(f"{LOGS}/gpu{gpu}.log", "a") as log:
        for attempt in range(3):
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in p.stdout:
                stamp = f"[gpu{gpu} {(time.time()-T0)/60:5.1f}m] "; log.write(stamp + line); log.flush()
                if any(k in line for k in ("Saved output", "Traceback", "Error", "Killed")): print(stamp + line, end="", flush=True)
            rc[gpu] = p.wait()
            if rc[gpu] == 0: break
            print(f"[gpu{gpu}] exited {rc[gpu]}, restarting (finished clips are skipped)", flush=True)
ts = [threading.Thread(target=run, args=(g,)) for g in range(N_GPU)]
for t in ts: t.start()
for t in ts: t.join()
STOP.set(); print("exit codes", rc, f"| peak RAM {MEMPEAK[0]:.1f} GiB | {(time.time()-T0)/60:.1f} min")
'''),
    ("code", '''
# ---- Pack ----
shutil.make_archive("/kaggle/working/clips", "zip", OUT)
missing = [j["id"] for j in jobs if not os.path.exists(f"{OUT}/{j['id']}_output.mp4")]
print(len(jobs) - len(missing), "of", len(jobs), "clips | download /kaggle/working/clips.zip")
assert not missing, f"clips missing: {missing} (see /kaggle/working/logs); run again to finish them"
'''),
])

REAL = notebook([
    ("markdown", """
# Free AI avatar studio: realistic mode (moving takes + LatentSync 1.5, Kaggle T4 x2)
Part of [free-ai-avatar-studio](https://github.com/sahilempire/free-ai-avatar-studio). For each scene of your kit it renders
moving **takes** with Wan2.1-Fun image-to-video (background motion, blinks, expressions) with the face **pinned to the
scene image at the first and last frame** (identity holds and takes chain without a seam), then dubs the scene's
voice-over onto them with LatentSync 1.5 (only the mouth is redrawn).

Same setup as the fast notebook: kit dataset as input, **GPU T4 x2**, Internet **On**. About 20 min per take plus
~1.2 min per second of speech for the dub. Download `takes.zip`, unzip into `work/takes/`, then `studio post` with
`studio track --source scenes`.
"""),
    ("code", f'''
# ---- Settings ----
TAKES_PER_SCENE = 2       # takes alternate A, B, A ... to cover each scene
SEEDS = [43, 71]
NEG = {NEG!r}
DEFAULT_PROMPT = {DEFAULT_PROMPT!r}
{COMMON}
SCENES = json.load(open(f"{{KIT}}/scenes.json"))
W = "/kaggle/working/library"
for d in (f"{{W}}/takes", "/kaggle/working/takes"): os.makedirs(d, exist_ok=True)
print([(s["id"], s["dur"]) for s in SCENES])
'''),
    ("code", f'''
# ---- Setup: LatentSync 1.5 (pinned packages kept apart) + VideoX-Fun + weights ----
LS, LSPKG, VF, WAN = "/tmp/LatentSync", "/tmp/ls_pkgs", "/tmp/VideoX-Fun", "/tmp/models/Wan2.1-Fun-V1.1-1.3B-InP"
if not os.path.exists(LS):
    sh(f"git clone -q https://github.com/bytedance/LatentSync.git {{LS}} && cd {{LS}} && git checkout -q {LS_COMMIT}", "ls_clone")
sh(f"pip install -q --no-deps --target {{LSPKG}} diffusers==0.32.2 transformers==4.48.0 'tokenizers>=0.21,<0.22' huggingface_hub==0.30.2 DeepCache==0.1.1", "ls_pins")
sh("pip install -q insightface==0.7.3 onnxruntime-gpu kornia decord ffmpeg-python omegaconf einops librosa soundfile", "ls_deps")
sh(f"python -c \\"from huggingface_hub import hf_hub_download as d; [d('ByteDance/LatentSync-1.5', f, local_dir='{{LS}}/checkpoints') for f in ('latentsync_unet.pt','whisper/tiny.pt')]\\"", "ls_weights")
if not os.path.exists(VF):
    sh(f"git clone -q https://github.com/aigc-apps/VideoX-Fun.git {{VF}} && cd {{VF}} && git checkout -q {VF_COMMIT}", "vf_clone")
sh("pip install -q -U diffusers transformers accelerate ftfy timm tomesd torchdiffeq torchsde sentencepiece", "vf_deps")
sh(f"python -c \\"from huggingface_hub import snapshot_download as s; s('alibaba-pai/Wan2.1-Fun-V1.1-1.3B-InP', local_dir='{{WAN}}')\\"", "wan_weights")
BASE_SRC = open(f"{{VF}}/examples/wan2.1_fun/predict_i2v.py", encoding="utf-8").read()
CN_NEG = re.search(r'^negative_prompt\\s*=\\s*"(.*)"', BASE_SRC, re.M).group(1)
FREE_T5 = """
_encode = pipeline.encode_prompt
def _encode_then_free_t5(*a, **k):  # model_cpu_offload would keep T5 (11 GB) on the GPU through the VAE encode
    out = _encode(*a, **k); pipeline.text_encoder.to("cpu"); torch.cuda.empty_cache(); return out
pipeline.encode_prompt = _encode_then_free_t5
"""
'''),
    ("code", '''
# ---- Takes, one after another on GPU 0 (two image-to-video runs at once nearly fill Kaggle's RAM) ----
def make_take(scene, k):
    out = f"{W}/takes/{scene['id']}_{k}.mp4"
    if os.path.exists(out): return out
    img = find(scene["image"]); prompt = scene.get("prompt") or DEFAULT_PROMPT
    SET = {"GPU_memory_mode": '"model_cpu_offload"', "model_name": repr(WAN), "sampler_name": '"Flow_Unipc"', "sample_size": "[864, 480]",
           "video_length": "81", "weight_dtype": "torch.float16", "validation_image_start": repr(img), "validation_image_end": repr(img),
           "prompt": repr(prompt), "negative_prompt": repr(NEG + ", " + CN_NEG), "num_inference_steps": "25",
           "seed": str(SEEDS[k % len(SEEDS)]), "save_path": repr(f"/tmp/wan_{scene['id']}_{k}")}
    src = BASE_SRC
    for key, v in SET.items():
        src, n = re.subn(rf"^{key}(\\s*)=.*$", lambda m: f"{key}{m.group(1)}= {v}", src, count=1, flags=re.M); assert n == 1, key
    anchor = "coefficients = get_teacache_coefficients(model_name)"; assert src.count(anchor) == 1
    open(f"{VF}/examples/wan2.1_fun/predict_take.py", "w", encoding="utf-8").write(src.replace(anchor, FREE_T5 + anchor))
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="0", PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
    sh("python examples/wan2.1_fun/predict_take.py", f"take_{scene['id']}_{k}", cwd=VF, env=env)
    raw = sorted(glob.glob(f"/tmp/wan_{scene['id']}_{k}/*.mp4"))[-1]
    sh(f"ffmpeg -y -loglevel error -i {raw} -vf \\"minterpolate=fps=25:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1\\" -c:v libx264 -crf 16 -pix_fmt yuv420p {out}",
       f"interp_{scene['id']}_{k}")
    return out
for s in SCENES:
    for k in range(TAKES_PER_SCENE): make_take(s, k)
'''),
    ("code", '''
# ---- Dub each scene: chain its takes to the scene length, LatentSync over the exact voice-over slice ----
for g in (0, 1):  # LatentSync writes ./temp, so each GPU worker gets its own copy (checkpoints shared via a symlink)
    if not os.path.exists(f"{LS}_{g}"):
        shutil.copytree(LS, f"{LS}_{g}", ignore=shutil.ignore_patterns("checkpoints")); os.symlink(f"{LS}/checkpoints", f"{LS}_{g}/checkpoints")
def dub(i, gpu):
    sc = SCENES[i]; out = f"/kaggle/working/takes/{sc['id']}.mp4"
    if os.path.exists(out): return
    wd = f"/tmp/scene_{sc['id']}"; os.makedirs(wd, exist_ok=True)
    with open(f"{wd}/chunks.txt", "w") as f:
        for c in sc["chunks"]: f.write(f"file '{find('audio/' + c + '.wav')}'\\n")
    sh(f"ffmpeg -y -loglevel error -f concat -safe 0 -i {wd}/chunks.txt {wd}/vo.wav", f"vo_{sc['id']}")
    takes = [f"{W}/takes/{sc['id']}_{k}.mp4" for k in range(TAKES_PER_SCENE)]
    with open(f"{wd}/takes.txt", "w") as f:
        for j in range(int(sc["dur"] // 4.9) + 1): f.write(f"file '{takes[j % len(takes)]}'\\n")
    sh(f"ffmpeg -y -loglevel error -f concat -safe 0 -i {wd}/takes.txt -t {sc['dur'] + 0.3:.3f} -c:v libx264 -crf 14 -pix_fmt yuv420p {wd}/drive.mp4", f"drive_{sc['id']}")
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), PYTHONPATH=f"{LSPKG}:{LS}_{gpu}")
    sh(f"python -m scripts.inference --unet_config_path configs/unet/stage2.yaml --inference_ckpt_path checkpoints/latentsync_unet.pt "
       f"--inference_steps 25 --guidance_scale 1.5 --enable_deepcache --video_path {wd}/drive.mp4 --audio_path {wd}/vo.wav --video_out_path {out}",
       f"dub_{sc['id']}", cwd=f"{LS}_{gpu}", env=env)
def worker(gpu, ids):
    for i in ids:
        try: dub(i, gpu)
        except AssertionError as e: print(f"{SCENES[i]['id']} failed on gpu{gpu}: {str(e)[:300]}")
order = sorted(range(len(SCENES)), key=lambda i: -SCENES[i]["dur"])
ts = [threading.Thread(target=worker, args=(g, order[g::2])) for g in (0, 1)]
for t in ts: t.start()
for t in ts: t.join()
STOP.set(); shutil.make_archive("/kaggle/working/takes", "zip", "/kaggle/working/takes")
missing = [s["id"] for s in SCENES if not os.path.exists(f"/kaggle/working/takes/{s['id']}.mp4")]
print(f"peak RAM {MEMPEAK[0]:.1f} GiB | {(time.time()-T0)/60:.1f} min | download /kaggle/working/takes.zip")
assert not missing, f"scenes missing: {missing} (see logs); run again to finish them"
'''),
])

for name, nb in (("lipsync_fast.ipynb", FAST), ("lipsync_realistic.ipynb", REAL)):
    json.dump(nb, open(f"{HERE}/{name}", "w"), indent=1, ensure_ascii=False); print("wrote", name)
