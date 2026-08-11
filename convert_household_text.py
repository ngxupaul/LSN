#!/usr/bin/env python3
"""Chuyển bảng hộ đánh số thành dữ liệu 5 cột để nhập từng hộ vào ứng dụng."""

import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def display_date(value):
    value = clean(value)
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return value


def slug(value):
    plain = unicodedata.normalize("NFD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-") or "ho"


def parse_numbered_households(text):
    households = []
    current = None
    for line_number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        parts = [clean(part) for part in raw.split("\t")]
        while parts and not parts[-1]:
            parts.pop()
        if len(parts) < 5:
            raise ValueError(f"Dòng {line_number}: cần 5 cột, nhận được {len(parts)}")

        household_number, name, dob, gender = parts[:4]
        address = clean(" ".join(parts[4:]))
        if household_number:
            if not household_number.isdigit():
                raise ValueError(f"Dòng {line_number}: mã hộ không hợp lệ: {household_number}")
            current = {
                # Chỉ dùng để tách nhóm và đặt tên file; tuyệt đối không xuất thành ID nhà.
                "_source_group": household_number,
                "headName": name,
                "address": address,
                "members": [],
            }
            households.append(current)
        elif current is None:
            raise ValueError(f"Dòng {line_number}: thành viên xuất hiện trước dòng chủ hộ")

        current["members"].append({
            "name": name,
            "dob": display_date(dob),
            "gender": gender,
            "headName": current["headName"],
            "address": address or current["address"],
            "head": name.casefold() == current["headName"].casefold(),
        })
    return households


def member_text(household):
    return "\n".join(
        " | ".join((m["name"], m["dob"], m["gender"], household["headName"], m["address"]))
        for m in household["members"]
    ) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("imports/households"))
    args = parser.parse_args()

    households = parse_numbered_households(args.source.read_text(encoding="utf-8-sig"))
    args.output.mkdir(parents=True, exist_ok=True)
    for household in households:
        number = int(household["_source_group"])
        filename = f"{number:03d}-{slug(household['headName'])}.txt"
        (args.output / filename).write_text(member_text(household), encoding="utf-8")

    bundle = {
        "format": "lesonnam-households-v1",
        # File import không chứa id/fid/household_number; ID nhà hiện tại luôn được giữ nguyên.
        "households": [
            {key: value for key, value in household.items() if key != "_source_group"}
            for household in households
        ],
    }
    bundle_path = args.output.parent / "households-headname.json"
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Converted {len(households)} households / {sum(len(h['members']) for h in households)} people")
    print(args.output)
    print(bundle_path)


if __name__ == "__main__":
    main()
