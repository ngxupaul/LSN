#!/usr/bin/env python3
"""AI building extraction for Thôn Lệ Sơn Nam using SAM (segment-anything).

Pipeline:
1. Download satellite tiles (Google, zoom 19) for the village area.
2. Stitch tiles into 1024px blocks with 25% overlap.
3. Grid-point prompting with SAM (SamPredictor) -> binary acceptance mask.
4. Connected components -> polygons -> lat/lon -> GeoJSON (building=house).
5. Dedupe across overlapping blocks, filter by area/shape.
Output: data/ai_buildings.geojson
"""
import json, math, os, sys, time, urllib.request

AREA = (15.9550, 108.1825, 15.9615, 108.1964)  # minlat, minlon, maxlat, maxlon
ZOOM = 19
TILE = 256
BLOCK = 1024
OUT = "data/ai_buildings.geojson"
TILE_DIR = "ai/tiles"

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

def tile_xyz(lat, lon, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y

def tile_bounds(x, y, z):
    n = 2 ** z
    lon0 = x / n * 360.0 - 180.0
    lon1 = (x + 1) / n * 360.0 - 180.0
    lat0 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    lat1 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return lat1, lon0, lat0, lon1  # north lat, west lon, south lat, east lon

def deg_per_px(lat, z):
    n = 2 ** z
    return 360.0 / n / TILE, 360.0 / n / TILE * math.cos(math.radians(lat))

def download_tile(x, y, z):
    path = os.path.join(TILE_DIR, f"{z}_{x}_{y}.jpg")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    for host in ("mt1", "mt2", "mt3", "mt0"):
        url = f"https://{host}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
            if len(data) > 1000:
                with open(path, "wb") as f:
                    f.write(data)
                return path
        except Exception:
            continue
        time.sleep(0.1)
    return None

def main():
    os.makedirs(TILE_DIR, exist_ok=True)
    minlat, minlon, maxlat, maxlon = AREA
    x0, y1 = tile_xyz(maxlat, minlon, ZOOM)
    x1, y0 = tile_xyz(minlat, maxlon, ZOOM)

    print(f"tile range x:[{x0}..{x1}] y:[{y1}..{y0}]  ({ (x1-x0+1)*(y0-y1+1) } tiles)")
    tiles = {}
    for x in range(x0, x1 + 1):
        for y in range(y1, y0 + 1):
            p = download_tile(x, y, ZOOM)
            if p:
                tiles[(x, y)] = p
    print(f"downloaded {len(tiles)} tiles")

    # ---- SAM setup: grid-point prompting + connected components ----
    import numpy as np
    import torch
    from PIL import Image
    from skimage import measure
    from segment_anything import sam_model_registry, SamPredictor

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print("torch device:", device)
    sam = sam_model_registry["vit_b"](checkpoint="ai/sam_vit_b_01ec64.pth")
    sam.to(device)
    predictor = SamPredictor(sam)

    GRID = 32            # khoảng cách điểm prompt (px) -> 32x32 điểm/block
    IOU_MIN = 0.55       # ngưỡng iou mask
    PX_MIN, PX_MAX = 40, 6000   # lọc diện tích mask (px); 1px~0.34m2 tại z19

    dlon, dlat = deg_per_px((minlat + maxlat) / 2, ZOOM)

    blocks = []
    for bx in range(x0, x1 + 1 - 3, 3):
        for by in range(y1, y0 + 1 - 3, 3):
            blocks.append((bx, by))
    print(f"{len(blocks)} blocks")

    ys, xs = np.mgrid[GRID//2:BLOCK:GRID, GRID//2:BLOCK:GRID]
    pts = np.stack([xs.ravel(), ys.ravel()], 1).astype(np.float64)
    lbl = np.ones(len(pts), dtype=np.int64)
    all_polys = []  # {"coords": [(lon,lat),...], "area_m2": float}

    for bi, (bx, by) in enumerate(blocks):
        img = np.zeros((BLOCK, BLOCK, 3), dtype=np.uint8)
        ok = True
        for i in range(4):
            for j in range(4):
                p = tiles.get((bx + i, by + j))
                if not p:
                    ok = False
                    break
                t = np.asarray(Image.open(p).convert("RGB"))
                img[j*TILE:(j+1)*TILE, i*TILE:(i+1)*TILE] = t
            if not ok:
                break
        if not ok:
            continue
        print(f"block {bi+1}/{len(blocks)} (tile {bx},{by})...", flush=True)
        t0 = time.time()
        predictor.set_image(img)
        acc = np.zeros((BLOCK, BLOCK), dtype=bool)
        B = 64
        for s in range(0, len(pts), B):
            chunk = pts[s:s+B]
            coords_t = torch.as_tensor(predictor.transform.apply_coords(chunk, predictor.original_size),
                                       dtype=torch.float32, device=device)
            labels_t = torch.ones(len(chunk), 1, dtype=torch.int32, device=device)
            masks, scores, _ = predictor.predict_torch(
                point_coords=coords_t[:, None, :], point_labels=labels_t,
                multimask_output=True, return_logits=True)   # (B,3,H,W) mps
            ar = torch.arange(masks.shape[0], device=device)
            best = scores.argmax(dim=1)                       # (B,)
            lg = masks[ar, best]                              # (B,H,W) logits
            hi = lg > 1.0
            lo = lg > -1.0
            n_hi = hi.sum(dim=(1, 2))
            n_lo = lo.sum(dim=(1, 2))
            stab = n_hi / n_lo.clamp(min=1)
            score_ok = scores[ar, best] >= IOU_MIN
            keep = score_ok & (stab >= 0.70) & (n_lo >= PX_MIN) & (n_lo <= PX_MAX)
            if keep.any():
                acc |= hi[keep].any(dim=0).cpu().numpy()
        print(f"  {int(acc.sum())} px sau lọc iou, {time.time()-t0:.0f}s", flush=True)
        nlat, wlon, slat, elon = tile_bounds(bx, by, ZOOM)
        lab = measure.label(acc, connectivity=2)
        for rid in range(1, lab.max() + 1):
            comp = lab == rid
            n = int(comp.sum())
            if n < PX_MIN or n > PX_MAX:
                continue
            cnts = measure.find_contours(comp, level=0.5)
            if not cnts:
                continue
            c = max(cnts, key=len)
            if len(c) < 4:
                continue
            ys_c = c[:, 0]; xs_c = c[:, 1]
            w = xs_c.max() - xs_c.min(); h = ys_c.max() - ys_c.min()
            if w > 0 and h > 0 and max(w, h) / min(w, h) > 4:
                continue  # đối tượng dài (đường/bờ ruộng)
            poly = [(wlon + (px - 1) * dlon, nlat - (py - 1) * dlat) for py, px in c]
            if poly[0] != poly[-1]:
                poly.append(poly[0])
            area_deg2 = abs(sum(poly[i][0]*poly[i+1][1] - poly[i+1][0]*poly[i][1] for i in range(len(poly)-1)) / 2)
            m_per_deg = 111320.0 * math.cos(math.radians(nlat))
            area_m2 = area_deg2 * 111320.0 * m_per_deg
            if area_m2 < 15 or area_m2 > 2000:
                continue
            if len(poly) > 60:
                poly = [poly[i] for i in range(0, len(poly), 2)]
            all_polys.append({"coords": poly, "area_m2": area_m2})
        del acc, lab
        torch.cuda.empty_cache() if device == "cuda" else None

    print(f"total candidate polys: {len(all_polys)}")

    # ---- Dedupe overlapping blocks ----
    from shapely.geometry import Polygon

    kept = []
    for p in sorted(all_polys, key=lambda p: -p["area_m2"]):
        g = Polygon(p["coords"])
        if not g.is_valid:
            g = g.buffer(0)
        if g.is_empty or g.area < 1e-10:
            continue
        dup = False
        for k in kept:
            if k.intersects(g):
                inter = k.intersection(g).area
                if inter / min(k.area, g.area) > 0.5:
                    dup = True
                    break
        if not dup:
            kept.append(g)
    print(f"after dedupe: {len(kept)}")

    # ---- Simplify + output ----
    feats = []
    for g in kept:
        g = g.simplify(0.00002, preserve_topology=True)  # ~2m tolerance
        coords = list(g.exterior.coords)
        feats.append({
            "type": "Feature",
            "properties": {"building": "house", "name": "", "source": "ai:SAM (cần kiểm tra)"},
            "geometry": {"type": "Polygon", "coordinates": [coords]},
        })
    with open(OUT, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)
    print(f"WROTE {OUT}: {len(feats)} buildings")

if __name__ == "__main__":
    main()
