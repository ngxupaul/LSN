#!/usr/bin/env python3
"""Prepare zone data (Lệ Sơn Bắc + Lệ Sơn Nam) from Overpass JSON."""
import json

SRC = "/tmp/focus2.json"
d = json.load(open(SRC))
els = d["elements"]

def to_feature(el):
    if el.get("geometry"):
        coords = [[round(p["lon"], 7), round(p["lat"], 7)] for p in el["geometry"]]
        if el["type"] == "way" and el.get("tags", {}).get("building"):
            geom = {"type": "Polygon", "coordinates": [coords]}
        elif el["type"] == "way":
            geom = {"type": "LineString", "coordinates": coords}
        else:
            geom = {"type": "Point", "coordinates": coords[0] if coords else [el["lon"], el["lat"]]}
    else:
        geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
    props = dict(el.get("tags", {}))
    props["@id"] = f'{el["type"]}/{el["id"]}'
    return {"type": "Feature", "properties": props, "geometry": geom}

blds = [e for e in els if "building" in e.get("tags", {})]
roads = [e for e in els if "highway" in e.get("tags", {}) and e["tags"]["highway"] != "bus_stop"]
pois = [e for e in els if e.get("tags", {}).get("amenity") or e.get("tags", {}).get("highway") == "bus_stop"]

for name, lst in (("data/zone_buildings.geojson", blds),
                  ("data/zone_roads.geojson", roads),
                  ("data/zone_pois.geojson", pois)):
    fc = {"type": "FeatureCollection", "features": [to_feature(e) for e in lst]}
    with open(name, "w") as f:
        json.dump(fc, f)
    print(name, "->", len(lst))

# Convex hull of building centroids + Kiệt 1 anchor -> estimated hamlet extent
import math
def centroid(f):
    c = f["geometry"]["coordinates"][0]
    return (sum(p[1] for p in c)/len(c), sum(p[0] for p in c)/len(c))
pts = [centroid(to_feature(e)) for e in blds]
pts.append((15.9610, 108.1828))  # Kiệt 1 anchor

def cross(o, a, b):
    return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
pts_sorted = sorted(set(pts))
lower = []
for p in pts_sorted:
    while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
        lower.pop()
    lower.append(p)
upper = []
for p in reversed(pts_sorted):
    while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
        upper.pop()
    upper.append(p)
hull = lower[:-1] + upper[:-1]
# GeoJSON order: [lon, lat]
hull_coords = [[round(lon, 7), round(lat, 7)] for lat, lon in hull]
hull_feat = {"type": "Feature",
             "properties": {"name": "Phạm vi ước tính khu dân cư Lệ Sơn (Bắc+Nam)", "note": "Convex hull các nhà OSM + mốc Kiệt 1"},
             "geometry": {"type": "Polygon", "coordinates": [hull_coords + [hull_coords[0]]]}}
with open("data/zone_extent.geojson", "w") as f:
    json.dump({"type": "FeatureCollection", "features": [hull_feat]}, f)
print("zone_extent.geojson -> hull points:", len(hull_coords))
