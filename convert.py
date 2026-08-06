#!/usr/bin/env python3
"""Convert Overpass API 'out geom' JSON to GeoJSON."""
import json, sys

def to_feature(el, props_extra=None):
    if el.get("geometry"):
        coords = [[round(p["lon"], 7), round(p["lat"], 7)] for p in el["geometry"]]
        # close ring for areas
        if el["type"] == "way" and len(coords) > 2 and coords[0] != coords[-1]:
            pass  # keep as-is; decide area vs line below
        geom = {"type": "Polygon" if (el["type"] == "way" and el.get("tags", {}).get("building")) else ("LineString" if el["type"] == "way" else "Point"), "coordinates": coords}
        if geom["type"] == "Polygon":
            geom["coordinates"] = [coords]
    else:
        geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
    props = dict(el.get("tags", {}))
    props["@id"] = f'{el["type"]}/{el["id"]}'
    if props_extra:
        props.update(props_extra)
    return {"type": "Feature", "properties": props, "geometry": geom}

def convert(infile, outfile, extra=None):
    with open(infile) as f:
        data = json.load(f)
    features = [to_feature(el, extra) for el in data["elements"]]
    gj = {"type": "FeatureCollection", "features": features}
    with open(outfile, "w") as f:
        json.dump(gj, f)
    print(f"{outfile}: {len(features)} features")

if __name__ == "__main__":
    convert("data/raw_buildings.json", "data/buildings.geojson")
    convert("data/raw_roads.json", "data/roads.geojson")
