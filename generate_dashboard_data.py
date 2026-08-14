#!/usr/bin/env python3
"""Build dashboard-only EDA data from the household workbook.

The generated JSON is intentionally separate from map data. It is used by the
Dashboard and by the DeepSeek chat endpoint for grounded answers.
"""
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parent
DEFAULT_SOURCE = Path('/Users/paul/Downloads/Copy of nhân khẩu LSN 5.2026.xlsx')
SOURCE = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_SOURCE
OUTPUT = ROOT / 'data/dashboard-real.json'
AS_OF = date(2026, 8, 12)


def normalized(value):
    text = ''.join(c for c in unicodedata.normalize('NFD', str(value).upper())
                   if unicodedata.category(c) != 'Mn')
    return ' '.join(text.split())


def extract_to(value):
    match = re.search(r'\bTO\s*(?:DP\s*)?(\d+)\b', normalized(value))
    return int(match.group(1)) if match else None


def age_at(value):
    if pd.isna(value):
        return None
    stamp = pd.Timestamp(value).date()
    return AS_OF.year - stamp.year - ((AS_OF.month, AS_OF.day) < (stamp.month, stamp.day))


def iso_date(value):
    if pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


def display_date(value):
    if pd.isna(value):
        return ''
    return pd.Timestamp(value).strftime('%d/%m/%Y')


def main():
    if not SOURCE.exists():
        raise SystemExit(f'Workbook not found: {SOURCE}')
    frame = pd.read_excel(SOURCE)
    frame['to'] = frame['Nơi thường trú'].map(extract_to)
    frame['age'] = frame['Ngày sinh'].map(age_at)
    frame['head_norm'] = frame['Họ và tên chủ hộ'].map(normalized)
    frame['name_norm'] = frame['Họ và tên'].map(normalized)
    frame['is_head'] = frame['head_norm'].eq(frame['name_norm'])
    # Một tên chủ hộ có thể xuất hiện ở nhiều hộ khác nhau. Các dòng của
    # cùng một hộ nằm thành một khối liên tiếp trong file import; dùng khối
    # liên tiếp để không gộp nhầm các hộ trùng tên thành một hộ 18+ người.
    frame['household_run'] = frame['Họ và tên chủ hộ'].astype(str).fillna('').ne(
        frame['Họ và tên chủ hộ'].astype(str).fillna('').shift()
    ).cumsum()

    households = []
    for number, (_, group) in enumerate(frame.groupby('household_run', sort=False), start=1):
        head = group['Họ và tên chủ hộ'].iloc[0]
        known_tos = group['to'].dropna().astype(int)
        household_to = int(known_tos.mode().iloc[0]) if len(known_tos) else None
        members = []
        for _, row in group.iterrows():
            members.append({
                'name': str(row['Họ và tên']),
                'dob': iso_date(row['Ngày sinh']),
                'dobDisplay': display_date(row['Ngày sinh']),
                'gender': str(row['Giới tính']),
                'isHead': bool(row['is_head']),
            })
        households.append({
            'id': f'HH-{number:04d}',
            'head': str(head),
            'address': str(group['Nơi thường trú'].mode().iloc[0]),
            'to': household_to,
            'members': len(group),
            'elderly': int((group['age'] >= 60).sum()),
            'children': int((group['age'] < 18).sum()),
            'male': int((group['Giới tính'] == 'Nam').sum()),
            'female': int((group['Giới tính'] == 'Nữ').sum()),
            'membersList': members,
        })

    by_to = []
    for to_number in list(range(1, 8)) + [None]:
        member_rows = frame[frame['to'].eq(to_number)] if to_number is not None else frame[frame['to'].isna()]
        household_rows = [h for h in households if h['to'] == to_number]
        if to_number is None:
            label = 'Chưa xác định'
        else:
            label = f'Tổ {to_number}'
        by_to.append({
            'id': to_number,
            'label': label,
            'members': int(len(member_rows)),
            'households': int(len(household_rows)),
            'elderly': int((member_rows['age'] >= 60).sum()),
            'children': int((member_rows['age'] < 18).sum()),
            'male': int((member_rows['Giới tính'] == 'Nam').sum()),
            'female': int((member_rows['Giới tính'] == 'Nữ').sum()),
        })

    age_ranges = [(-1, 5, '0–5'), (6, 17, '6–17'), (18, 29, '18–29'),
                  (30, 59, '30–59'), (60, 999, '60+')]
    age_bands = [{'label': label, 'members': int(((frame['age'] >= low) & (frame['age'] <= high)).sum())}
                 for low, high, label in age_ranges]

    head_counts = frame.groupby('household_run')['is_head'].sum()
    quality = {
        'missingRegistrationDate': int(frame['Ngày ĐKTT'].isna().sum()),
        'missingRegistrationRate': round(float(frame['Ngày ĐKTT'].isna().mean()), 4),
        'missingFatherName': int(frame['Họ tên cha'].isna().sum()),
        'duplicateStt': int(frame['STT'].duplicated().sum()),
        'membersWithoutTo': int(frame['to'].isna().sum()),
        'householdsWithoutTo': int(sum(h['to'] is None for h in households)),
        'householdsWithoutMatchingHead': int((head_counts == 0).sum()),
        'householdsWithMultipleHeadRows': int((head_counts > 1).sum()),
        'differentCurrentAddress': int((frame['Nơi thường trú'].astype(str).str.strip() != frame['Nơi ở hiện tại'].astype(str).str.strip()).groupby(frame['household_run']).any().sum()),
    }
    household_size_distribution = [
        {'size': int(size), 'households': int(count), 'members': int(size * count)}
        for size, count in sorted(pd.Series([h['members'] for h in households]).value_counts().items())
    ]

    result = {
        'source': {
            'file': SOURCE.name,
            'asOf': AS_OF.isoformat(),
            'generatedAt': date.today().isoformat(),
        },
        'totals': {
            'members': int(len(frame)),
            'households': int(len(households)),
            'elderly': int((frame['age'] >= 60).sum()),
            'children': int((frame['age'] < 18).sum()),
            'male': int((frame['Giới tính'] == 'Nam').sum()),
            'female': int((frame['Giới tính'] == 'Nữ').sum()),
            'averageHouseholdSize': round(float(len(frame) / len(households)), 2),
            'medianHouseholdSize': int(pd.Series([h['members'] for h in households]).median()),
        },
        'byTo': by_to,
        'ageBands': age_bands,
        'gender': {'male': int((frame['Giới tính'] == 'Nam').sum()), 'female': int((frame['Giới tính'] == 'Nữ').sum())},
        'householdSizeDistribution': household_size_distribution,
        'quality': quality,
        'topHouseholds': sorted(
            [{'id': h['id'], 'head': h['head'], 'members': h['members'], 'to': h['to']}
             for h in households], key=lambda h: (-h['members'], h['head']))[:10],
        'households': households,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {OUTPUT} · {len(frame)} members · {len(households)} households')


if __name__ == '__main__':
    main()
