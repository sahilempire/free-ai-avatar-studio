"""Turns EchoMimicV3's infer_flash.py (commit 7e89489) into batch.py, a batch renderer for a studio kit:
- renders every job in a manifest with the models loaded once (skips clips that already exist)
- loads the Flash transformer with assign=True: the base Wan checkpoint has no audio layers, so they start on
  the meta device and a plain load_state_dict leaves them empty ("Cannot copy out of meta tensor")
- frees the 3.7 GB state_dict upstream keeps alive for the whole run
- never loads the 11 GB T5: prompts come pre-encoded (embed_prompts.py) through encode_prompt
- model CPU offload so it fits a 16 GB T4; per-job seed
Usage: python patch_echomimic.py <repo>
"""
import re, sys

repo = sys.argv[1]
src = open(f"{repo}/infer_flash.py", encoding="utf-8").read()


def swap(old, new, count=1):
    global src
    n = src.count(old)
    assert n == count, f"expected {count}x {old[:60]!r}, found {n} (upstream changed? pin the commit)"
    src = src.replace(old, new)


# arguments: per-job values come from the manifest
for arg in ("image_path", "audio_path", "prompt"):
    swap(f'parser.add_argument("--{arg}", type=str, required=True', f'parser.add_argument("--{arg}", type=str, default=""')
swap("    return parser.parse_args()", "    parser.add_argument(\"--manifest\", type=str, required=True)\n"
     "    parser.add_argument(\"--kit_dir\", type=str, required=True)\n"
     "    parser.add_argument(\"--embeds\", type=str, required=True)\n"
     "    return parser.parse_args()")
# Flash weights into the meta-initialised audio layers, then drop the duplicate
swap("        m, u = transformer.load_state_dict(state_dict, strict=False)",
     "        state_dict = {k: v.to(weight_dtype) for k, v in state_dict.items()}\n"
     "        m, u = transformer.load_state_dict(state_dict, strict=False, assign=True)\n"
     "        assert not [n for n, p in transformer.named_parameters() if p.is_meta], \"weights missing from the checkpoint\"\n"
     "        import gc; del state_dict; gc.collect()")
# no T5: embeddings are loaded instead
t5 = re.search(r"    # Get Text encoder\n    text_encoder = WanT5EncoderModel\.from_pretrained\(.*?\n    text_encoder = text_encoder\.eval\(\)", src, re.S)
assert t5, "T5 block not found"
src = src.replace(t5.group(0), "    text_encoder = None  # prompts are pre-encoded\n    EMB = torch.load(args.embeds)")
# offload instead of moving everything to the GPU (upstream calls pipeline.to twice)
assert src.count("    pipeline.to(device=device)") == 2, "expected two pipeline.to() calls"
src = src.replace("    pipeline.to(device=device)", "    pipeline.enable_model_cpu_offload()", 1)
src = src.replace("\n    pipeline.to(device=device)", "", 1)
swap("    coefficients = get_teacache_coefficients(model_name) if enable_teacache else None",
     "    def _encode_prompt(prompt, negative_prompt=None, do_classifier_free_guidance=True, *a, device=None, dtype=None, **k):\n"
     "        to = dict(device=device or \"cuda\", dtype=dtype or weight_dtype)\n"
     "        return [EMB[prompt].to(**to)], ([EMB[\"__neg__\"].to(**to)] if do_classifier_free_guidance else None)\n"
     "    pipeline.encode_prompt = _encode_prompt\n\n"
     "    coefficients = get_teacache_coefficients(model_name) if enable_teacache else None")

# wrap the per-clip generation (the last top-level `with torch.no_grad():` in main) in a loop over the manifest
lines = src.split("\n")
start = max(i for i, l in enumerate(lines) if l == "    with torch.no_grad():")
stop = next(i for i, l in enumerate(lines) if l.startswith("if __name__"))
block = [("    " + l if l.strip() else l) for l in lines[start:stop]]
while block and not block[-1].strip(): block.pop()
loop = ["    import json",
        "    for job in json.load(open(args.manifest)):",
        "        image_path = os.path.join(args.kit_dir, job[\"image\"])",
        "        audio_path = os.path.join(args.kit_dir, job[\"audio\"])",
        "        prompt, video_length = job[\"prompt\"], job[\"frames\"]",
        "        generator = torch.Generator(device=\"cuda\").manual_seed(job.get(\"seed\", seed))"] + block + ["", ""]
src = "\n".join(lines[:start] + loop + lines[stop:])
swap("image_name = os.path.basename(image_path).split('.')[0]", "image_name = job['id']")
skip = re.search(r"(print\(f\"⏭️  Skip: \{output_video_path\} already exists\.\"\)\n\s+)return", src)
assert skip, "skip-existing block not found"
src = src.replace(skip.group(0), skip.group(1) + "continue")
open(f"{repo}/batch.py", "w", encoding="utf-8").write(src)

# the pipeline reads the T5 dtype on every call
p = f"{repo}/src/pipeline_wan_fun_inpaint_audio_2512.py"
ps = open(p, encoding="utf-8").read()
if "weight_dtype = self.text_encoder.dtype" in ps:
    open(p, "w", encoding="utf-8").write(ps.replace("weight_dtype = self.text_encoder.dtype", "weight_dtype = self.transformer.dtype"))
print("batch.py ready")
