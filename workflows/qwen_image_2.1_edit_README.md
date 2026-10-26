# Qwen Image 2.1 Edit

Adapted from the workflow by AusBoss supplied as `qwenImage21Edit_v11_3269977.json`.
Source: https://github.com/ausboss/ComfyUI-AusBoss

The API graph preserves the original models, image preprocessing, 1 megapixel target, 30 steps, CFG 1, Euler/simple and denoise 1.
Removed workflow note, timer and comparison UI. Text and seed constants are inlined. The LoRA helper contained only disabled entries and is bypassed. SaveImage replaces the custom saver and receives the decoded edit directly. No AusBoss nodes remain in this base graph.

The alpha-mask compositing nodes are retained: they fill transparent areas before encoding. They are not redundant.

This file is available in Rendering > Edit > Qwen Image 2.1. Steps, sampler, scheduler and seed are editable; resolution remains 1 megapixel, CFG 1 and denoise 1. Saved metadata uses standard ComfyUI SaveImage behavior.

Rendering's LoRA panel supports up to three optional Qwen LoRAs, each with strength 0–1.5. Put compatible files in `ComfyUI/models/loras/Qwen2.1` (config override: `LORA_QWEN21_DIR`). Names and strengths are saved separately from other models. `-` or strength zero bypasses a slot. The app inserts standard `LoraLoaderModelOnly` nodes into the sampler's model path; the text encoder is unchanged. The base JSON intentionally remains free of optional LoRA nodes. Compatibility depends on the selected file: this folder is a selection filter, not an architecture detector. No LoRA is enabled automatically and sampler settings are not changed automatically by selecting one.

Portrait editing was tested without LoRA. LoRA graph wiring and UI/session behavior are checked separately; results from individual LoRA files still need visual evaluation.

Required files (retain these exact loader paths):
- diffusion_models/Qwen_image_2.1/qwen_image_2.1_int8_convrot.safetensors
- text_encoders/qwen3vl_8b_int8_convrot.safetensors
- vae/qwen_image_2.1_vae_bf16.safetensors

The source author's note requests ComfyUI 0.37.0 or newer. This compatibility claim has not been independently tested here.
