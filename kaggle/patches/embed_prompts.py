# Encodes every distinct prompt (and the negative prompt) with umT5 once, in bf16 (its native dtype),
# using the pipeline's own _get_t5_prompt_embeds so the result matches what the pipeline would make.
# Usage (from the repo folder): python embed_prompts.py <model_name> <config.yaml> <jobs.json> <negative prompt> <out.pt>
import os, sys, json, types, torch
from omegaconf import OmegaConf
from transformers import AutoTokenizer
from src.wan_text_encoder import WanT5EncoderModel
from src.pipeline_wan_fun_inpaint_audio_2512 import WanFunInpaintAudioPipeline

model_name, config_path, jobs_path, negative, out = sys.argv[1:6]
config = OmegaConf.load(config_path)
kw = config["text_encoder_kwargs"]
tokenizer = AutoTokenizer.from_pretrained(os.path.join(model_name, kw.get("tokenizer_subpath", "tokenizer")))
text_encoder = WanT5EncoderModel.from_pretrained(
    os.path.join(model_name, kw.get("text_encoder_subpath", "text_encoder")),
    additional_kwargs=OmegaConf.to_container(kw), low_cpu_mem_usage=True, torch_dtype=torch.bfloat16,
).eval().to("cuda")
fake_pipe = types.SimpleNamespace(tokenizer=tokenizer, text_encoder=text_encoder, _execution_device=torch.device("cuda"))
prompts = sorted({j["prompt"] for j in json.load(open(jobs_path))})
emb = {}
with torch.no_grad():
    for key, text in [(p, p) for p in prompts] + [("__neg__", negative)]:
        e = WanFunInpaintAudioPipeline._get_t5_prompt_embeds(fake_pipe, text, device=torch.device("cuda"), dtype=torch.float16)[0]
        assert torch.isfinite(e).all(), f"non-finite embedding for {key[:40]!r}"
        emb[key] = e.cpu()
        print(f"encoded {tuple(e.shape)}  {key[:60]}")
torch.save(emb, out)
print("saved", len(emb), "embeddings to", out)
