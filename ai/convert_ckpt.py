#!/usr/bin/env python3
"""Convert HF transformers SAM checkpoint -> original SAM state_dict (exact)."""
import torch, re
from segment_anything import sam_model_registry

hf = torch.load("ai/sam_vit_b_01ec64.pth", map_location="cpu")
sam = sam_model_registry["vit_b"](checkpoint=None)
model_keys = set(sam.state_dict().keys())

out = {}
skipped = []

def map_key(k):
    # ---- prompt encoder ----
    if k in ("prompt_encoder.no_mask_embed.weight", "prompt_encoder.not_a_point_embed.weight"):
        return k
    if k == "shared_image_embedding.positional_embedding":
        return "prompt_encoder.pe_layer.positional_encoding_gaussian_matrix"
    if k == "prompt_encoder.shared_embedding.positional_embedding":
        return None  # duplicate of shared_image_embedding
    m = re.match(r"^prompt_encoder\.point_embed\.(\d+)\.weight$", k)
    if m: return f"prompt_encoder.point_embeddings.{m.group(1)}.weight"
    m = re.match(r"^prompt_encoder\.mask_embed\.(conv1|conv2|conv3)\.(weight|bias)$", k)
    if m:
        idx = {"conv1": "0", "conv2": "3", "conv3": "6"}[m.group(1)]
        return f"prompt_encoder.mask_downscaling.{idx}.{m.group(2)}"
    m = re.match(r"^prompt_encoder\.mask_embed\.layer_norm1\.(weight|bias)$", k)
    if m: return f"prompt_encoder.mask_downscaling.1.{m.group(1)}"
    m = re.match(r"^prompt_encoder\.mask_embed\.layer_norm2\.(weight|bias)$", k)
    if m: return f"prompt_encoder.mask_downscaling.4.{m.group(1)}"
    # ---- mask decoder tokens ----
    if k in ("mask_decoder.iou_token.weight", "mask_decoder.mask_tokens.weight"):
        return k
    # ---- output upscaling ----
    m = re.match(r"^mask_decoder\.(upscale_conv1|upscale_layer_norm|upscale_conv2)\.(weight|bias)$", k)
    if m:
        idx = {"upscale_conv1": "0", "upscale_layer_norm": "1", "upscale_conv2": "3"}[m.group(1)]
        return f"mask_decoder.output_upscaling.{idx}.{m.group(2)}"
    # ---- iou head / hypernets: layers.0 passthrough, proj_in->layers.1, proj_out->layers.2 ----
    m = re.match(r"^mask_decoder\.(iou_prediction_head|output_hypernetworks_mlps\.\d+)\.layers\.0\.(weight|bias)$", k)
    if m: return k
    m = re.match(r"^mask_decoder\.(iou_prediction_head|output_hypernetworks_mlps\.\d+)\.proj_in\.(weight|bias)$", k)
    if m: return f"mask_decoder.{m.group(1)}.layers.1.{m.group(2)}"
    m = re.match(r"^mask_decoder\.(iou_prediction_head|output_hypernetworks_mlps\.\d+)\.proj_out\.(weight|bias)$", k)
    if m: return f"mask_decoder.{m.group(1)}.layers.2.{m.group(2)}"
    # ---- two-way transformer ----
    m = re.match(r"^mask_decoder\.transformer\.layers\.\d+\.mlp\.(lin1|lin2)\.(weight|bias)$", k)
    if m: return k
    m = re.match(r"^mask_decoder\.transformer\.layers\.(\d+)\.layer_norm([1-4])\.(weight|bias)$", k)
    if m: return f"mask_decoder.transformer.layers.{m.group(1)}.norm{m.group(2)}.{m.group(3)}"
    # decoder attn: passthrough (model uses q_proj/k_proj/v_proj/out_proj like HF)
    m = re.match(r"^mask_decoder\.transformer\.(layers\.\d+\.(?:self_attn|cross_attn_token_to_image|cross_attn_image_to_token)|final_attn_token_to_image)\.(q_proj|k_proj|v_proj|out_proj)\.(weight|bias)$", k)
    if m: return k
    m = re.match(r"^mask_decoder\.transformer\.layer_norm_final_attn\.(weight|bias)$", k)
    if m: return f"mask_decoder.transformer.norm_final_attn.{m.group(1)}"
    # ---- vision encoder ----
    m = re.match(r"^vision_encoder\.pos_embed$", k)
    if m: return "image_encoder.pos_embed"
    m = re.match(r"^vision_encoder\.patch_embed\.projection\.(weight|bias)$", k)
    if m: return "image_encoder.patch_embed.proj." + m.group(1)
    m = re.match(r"^vision_encoder\.layers\.(\d+)\.layer_norm1\.(weight|bias)$", k)
    if m: return f"image_encoder.blocks.{m.group(1)}.norm1.{m.group(2)}"
    m = re.match(r"^vision_encoder\.layers\.(\d+)\.layer_norm2\.(weight|bias)$", k)
    if m: return f"image_encoder.blocks.{m.group(1)}.norm2.{m.group(2)}"
    m = re.match(r"^vision_encoder\.layers\.(\d+)\.attn\.(rel_pos_h|rel_pos_w)$", k)
    if m: return f"image_encoder.blocks.{m.group(1)}.attn.{m.group(2)}"
    m = re.match(r"^vision_encoder\.layers\.(\d+)\.attn\.(qkv|proj)\.(weight|bias)$", k)
    if m: return f"image_encoder.blocks.{m.group(1)}.attn.{m.group(2)}.{m.group(3)}"
    m = re.match(r"^vision_encoder\.layers\.(\d+)\.mlp\.(lin1|lin2)\.(weight|bias)$", k)
    if m: return f"image_encoder.blocks.{m.group(1)}.mlp.{m.group(2)}.{m.group(3)}"
    neck = {"conv1": "0", "layer_norm1": "1", "conv2": "2", "layer_norm2": "3"}
    m = re.match(r"^vision_encoder\.neck\.(conv1|conv2|layer_norm1|layer_norm2)\.(weight|bias)?$", k)
    if m:
        return f"image_encoder.neck.{neck[m.group(1)]}." + (m.group(2) or "")
    return None

for k, v in hf.items():
    nk = map_key(k)
    if nk is None:
        skipped.append(k)
    else:
        out[nk] = v

print("skipped:", len(skipped))
for s in skipped[:15]:
    print("  !!", s)

got = set(out.keys())
missing = model_keys - got
extra = got - model_keys
print("model keys:", len(model_keys), "| converted:", len(got), "| missing:", len(missing), "| extra:", len(extra))
for k in sorted(missing)[:10]:
    print("  MISS:", k)
for k in sorted(extra)[:10]:
    print("  EXTRA:", k)

if not missing and not extra:
    torch.save(out, "ai/sam_vit_b_01ec64.pth")
    sam2 = sam_model_registry["vit_b"](checkpoint="ai/sam_vit_b_01ec64.pth")
    print("SAVED + LOADED OK, params:", round(sum(p.numel() for p in sam2.parameters())/1e6), "M")
else:
    print("NEED FIX")
