#!/usr/bin/env python3
"""Update household notes/addresses from the latest hand-drawn TO boundaries."""
import json
from pathlib import Path


ROOT = Path(__file__).parent
TARGET = ROOT / "backups/latest-drawn.json"


def inside(point, ring):
    x, y = point
    hit = False
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[i - 1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            hit = not hit
    return hit


data = json.loads(TARGET.read_text(encoding="utf-8"))
features = data.get("features", [])
to_features = [f for f in features if f.get("properties", {}).get("type") == "to"]
updated = 0
unassigned = 0

for feature in features:
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})
    if geom.get("type") != "Polygon" or props.get("type") in {"to", "thon"}:
        continue
    ring = geom.get("coordinates", [[]])[0]
    if not ring:
        continue
    cx = sum(p[0] for p in ring) / len(ring)
    cy = sum(p[1] for p in ring) / len(ring)
    match = next((f for f in to_features if inside((cx, cy), f["geometry"]["coordinates"][0])), None)
    if not match:
        unassigned += 1
        continue
    name = match["properties"].get("name", "Tổ chưa xác định")
    old_note = props.get("note", "")
    suffix = old_note.split("Thôn Lệ Sơn Nam", 1)[-1] if "Thôn Lệ Sơn Nam" in old_note else ", Xã Hoà Tiến, Thành Phố Đà Nẵng"
    address = f"{name}, Thôn Lệ Sơn Nam{suffix}"
    props["to"] = name
    props["note"] = address
    for member in props.get("members_list", []):
        member["address"] = address
    updated += 1

TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"Updated {updated} household notes; {unassigned} houses outside TO boundaries")
