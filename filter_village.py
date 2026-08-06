#!/usr/bin/env python3
"""Filter buildings/roads near Lệ Sơn Nam village center marker."""
import json, math

CENTER = (15.9610, 108.1828)  # Kiệt 1 ĐH409 - Thôn Lệ Sơn Nam
RADIUS_M = 1500

def dist_m(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

def poly_centroid(f):
    coords = f["geometry"]["coordinates"][0]
    n = len(coords)
    lat = sum(c[1] for c in coords)/n
    lon = sum(c[0] for c in coords)/n
    return lat, lon

with open("data/buildings.geojson") as f:
    bld = json.load(f)
with open("data/roads.geojson") as f:
    rds = json.load(f)

sel_b = [feat for feat in bld["features"]
         if dist_m(*CENTER, *poly_centroid(feat)) <= RADIUS_M]

sel_r = []
for feat in rds["features"]:
    cs = feat["geometry"]["coordinates"]
    near = any(dist_m(*CENTER, c[1], c[0]) <= RADIUS_M for c in cs)
    if near:
        sel_r.append(feat)

out_b = {"type": "FeatureCollection", "features": sel_b}
out_r = {"type": "FeatureCollection", "features": sel_r}
with open("data/village_buildings.geojson", "w") as f:
    json.dump(out_b, f)
with open("data/village_roads.geojson", "w") as f:
    json.dump(out_r, f)

names = sorted({feat["properties"].get("name") for feat in sel_r if feat["properties"].get("name")})
print(f"village buildings: {len(sel_b)}")
print(f"village roads: {len(sel_r)}")
print("road names:", ", ".join(names) or "(none)")
