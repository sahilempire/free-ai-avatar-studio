# Lessons from running this on free T4s

Every one of these broke a real run. The fix for each is already in the notebooks and the `studio` code.

| Symptom | Cause | Fix |
|---|---|---|
| `Cannot copy out of meta tensor` (EchoMimic) | Newer diffusers loads the base Wan checkpoint with `low_cpu_mem_usage`, which has no audio layers. Those layers stay on the meta device, and a plain `load_state_dict` is a no-op for them. | Load the Flash weights with `assign=True` (after casting to the run dtype) and assert nothing is left on meta. |
| Renderer `Killed` mid-run with two GPUs | System RAM (31 GB) runs out when both renderers save a clip at the same moment. | Encode prompts once and never load the 11 GB T5 in the renderers. Free the leftover 3.7 GB state dict. Restart a killed renderer (it skips finished clips). A RAM log is written to `logs/mem.log`. |
| Clips end before the speech does | Upstream rounds frames down twice (`int(dur*25)`, then to 4n+1), losing up to 0.15 s per chunk. | Pad each chunk with silence up to the next 4n+1 frame count; `studio track` trims back to the exact timeline. |
| Slow runs on T4 | `torch.cuda.is_bf16_supported()` returns True on T4 through emulation. | Use bf16 only when compute capability is 8 or higher; T4 gets native fp16. |
| `ValueError: Cannot forward both prompt and prompt_embeds` | Passing cached embeddings directly fails the pipeline's input checks. | Keep passing the text prompt and override `encode_prompt` to return the cached embeddings. |
| `audio/c00.wav` not found on Kaggle | Uploaded datasets can be flattened (no `audio/` folder). | Look every file up by name. |
| CUDA OOM in the image-to-video VAE encode | `model_cpu_offload` keeps T5 on the GPU until the next model in its sequence runs. | Move T5 back to the CPU right after `encode_prompt`, and set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`. |
| The face slowly becomes someone else (image-to-video) | A 1.3B model drifts after about 3 s. | Pin the same image as the first and the last frame (`validation_image_end`). Takes then also chain without a seam. |
| A 1-frame flash of the wrong shot | Graphic windows that don't sit on the 30 fps grid leave a gap frame between pieces. | Snap every window to whole frames, give overlay edges 5 ms of tolerance, and hard-cut instead of fading. |
| Hands melt or props smear | The model moves the hands with the audio; changing the prompt alone doesn't stop it. | Re-render that chunk with a different seed (`SEEDS`). Frame scenes so hands hold still objects. |
| Huge output files | Film grain is incompressible at CRF 18. | Cap the bitrate (`-maxrate 11M`). Instagram re-encodes anyway. |
