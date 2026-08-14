#!/usr/bin/env python3
"""Máy chủ tĩnh + lưu bản đồ + chatbot DeepSeek grounded trên EDA.

Chạy:  python3 server.py   ->  http://127.0.0.1:8899/
Dữ liệu app bấm "💾 Lưu về máy" sẽ ghi vào backups/latest-drawn.json.
Chatbot dùng DEEPSEEK_API_KEY (không ghi khóa vào mã nguồn).
"""
import json, os, re
import unicodedata
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


ROOT = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DATA = os.path.join(ROOT, 'data', 'dashboard-real.json')
DEEPSEEK_URL = 'https://api.deepseek.com/chat/completions'


def json_response(handler, status, payload):
    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def load_dashboard_data():
    try:
        with open(DASHBOARD_DATA, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def find_household(question, data, history=None):
    households = data.get('households', [])
    def match(text):
        q = normalize_text(text)
        # Ưu tiên mã hộ vì tên chủ hộ có thể xuất hiện ở nhiều dòng/hộ.
        for household in households:
            household_id = normalize_text(str(household.get('id', '')))
            if household_id and household_id in q:
                return household
        for household in households:
            head = normalize_text(str(household.get('head', '')))
            if head and head in q:
                return household
        return None

    # Câu hỏi hiện tại luôn thắng lịch sử; tránh lấy nhầm mã hộ từ câu trả lời trước.
    current = match(question)
    if current:
        return current
    for item in reversed(history or []):
        if isinstance(item, dict) and item.get('content'):
            previous = match(str(item.get('content')))
            if previous:
                return previous
    return None


def member_detail_answer(household):
    members = household.get('membersList') or []
    if not members:
        return f"Chưa có nguồn dữ liệu chi tiết từng thành viên của hộ {household.get('id', '')} ({household.get('head', '')})."
    lines = [
        f"Chi tiết hộ {household.get('id')} · {household.get('head')} · Tổ {household.get('to') or 'chưa rõ'} · {fmt_int(household.get('members'))} thành viên:",
        f"Địa chỉ/ghi chú: {household.get('address') or 'Chưa cập nhật'}",
    ]
    for index, member in enumerate(members, start=1):
        marker = ' · Chủ hộ' if member.get('isHead') else ''
        details = ' · '.join(filter(None, [member.get('dobDisplay'), member.get('gender')]))
        lines.append(f"{index}. {member.get('name', 'Chưa rõ')}{marker}" + (f" · {details}" if details else ''))
    return '\n'.join(lines)


def fmt_int(value):
    return f'{int(value or 0):,}'.replace(',', '.')


def normalize_text(value):
    text = unicodedata.normalize('NFD', str(value or ''))
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn').casefold()
    return text.replace('đ', 'd')


def local_answer(question, data, history=None):
    """Useful offline fallback when no DeepSeek key is configured."""
    history_text = ' '.join(
        str(item.get('content', '')) for item in (history or [])
        if isinstance(item, dict) and item.get('role') in ('user', 'assistant')
    )
    q = normalize_text(question)
    household = find_household(question, data, history)
    detail_intent = any(word in q for word in ('thanh vien', 'chi tiet', 'chi tietes', 'danh sach thanh vien', 'member', 'thong tin'))
    if household and detail_intent:
        return member_detail_answer(household)
    if any(word in q for word in ('ho dong', 'ho nao dong', 'dong nhan khau', 'dong nguoi nhat')):
        top = (data.get('topHouseholds') or [{}])[0]
        return f"Hộ đông nhân khẩu nhất thôn là {top.get('id')} · chủ hộ {top.get('head')} · Tổ {top.get('to') or 'chưa rõ'} · {fmt_int(top.get('members'))} thành viên."
    totals = data.get('totals', {})
    fmt = fmt_int
    if 'to' in q and any(ch.isdigit() for ch in q):
        match = re.search(r'to\s*(\d+)', q)
        if match:
            wanted = int(match.group(1))
            row = next((x for x in data.get('byTo', []) if x.get('id') == wanted), None)
            if row:
                return f"{row['label']} có {fmt(row['households'])} hộ và {fmt(row['members'])} nhân khẩu, gồm {fmt(row['elderly'])} NCT và {fmt(row['children'])} trẻ em."
    if any(word in q for word in ('tong', 'bao nhieu ho', 'nhan khau', 'tom tat', 'dan so', 'hien tai')):
        return f"Dashboard hiện có {fmt(totals.get('households'))} hộ và {fmt(totals.get('members'))} nhân khẩu; {fmt(totals.get('elderly'))} người cao tuổi, {fmt(totals.get('children'))} trẻ em."
    if any(word in q for word in ('chat luong', 'thieu', 'chua xac dinh', 'eda')):
        quality = data.get('quality', {})
        return f"EDA ghi nhận {fmt(quality.get('membersWithoutTo'))} nhân khẩu chưa có số tổ rõ ràng, {fmt(quality.get('missingRegistrationDate'))} dòng thiếu ngày ĐKTT và {fmt(quality.get('householdsWithoutMatchingHead'))} hộ chưa khớp được dòng chủ hộ."
    return 'Mình đang ở chế độ offline. Hãy hỏi về tổng hộ, nhân khẩu, một Tổ cụ thể, hoặc mã hộ để xem chi tiết thành viên.'


def grounded_context(question, data, history=None):
    compact = {
        'totals': data.get('totals', {}),
        'byTo': data.get('byTo', []),
        'ageBands': data.get('ageBands', []),
        'quality': data.get('quality', {}),
        'topHouseholds': data.get('topHouseholds', []),
    }
    q = normalize_text(question + ' ' + ' '.join(
        str(item.get('content', '')) for item in (history or [])
        if isinstance(item, dict) and item.get('role') in ('user', 'assistant')
    ))
    matches = []
    for household in data.get('households', []):
        if normalize_text(household.get('head', '')) in q or normalize_text(household.get('id', '')) in q:
            matches.append(household)
    if matches:
        compact['matchedHouseholds'] = matches[:5]
    return json.dumps(compact, ensure_ascii=False)


def call_deepseek(question, history, data):
    api_key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    household = find_household(question, data, history)
    normalized_question = normalize_text(question)
    detail_intent = any(word in normalized_question for word in ('thanh vien', 'chi tiet', 'chi tietes', 'danh sach thanh vien', 'member', 'thong tin'))
    # Chi tiết hộ phải lấy thẳng từ dữ liệu import để không bị mô hình diễn giải sai.
    if household and detail_intent and household.get('membersList'):
        return {'ok': True, 'mode': 'local', 'answer': member_detail_answer(household)}
    if not api_key:
        return {'ok': True, 'mode': 'local', 'answer': local_answer(question, data, history)}
    messages = [{
        'role': 'system',
        'content': (
            'Bạn là trợ lý dữ liệu cho Thôn Lệ Sơn Nam. Trả lời bằng tiếng Việt, ngắn gọn và có số liệu. '
            'Chỉ dùng context dữ liệu được cung cấp; nếu không có dữ liệu thì nói rõ “chưa có nguồn”. '
            'Khi context có matchedHouseholds.membersList và người dùng hỏi chi tiết thành viên, hãy liệt kê tên, ngày sinh, giới tính và đánh dấu chủ hộ; không trả lời rằng chưa có nguồn. '
            'Không tự suy đoán, không gán các hộ chưa xác định tổ vào một tổ cụ thể.\n\nCONTEXT:\n' + grounded_context(question, data, history)
        ),
    }]
    for item in (history or [])[-6:]:
        if isinstance(item, dict) and item.get('role') in ('user', 'assistant') and item.get('content'):
            messages.append({'role': item['role'], 'content': str(item['content'])[:4000]})
    messages.append({'role': 'user', 'content': question[:4000]})
    payload = json.dumps({
        'model': os.environ.get('DEEPSEEK_MODEL', 'deepseek-v4-flash'),
        'messages': messages,
        'thinking': {'type': 'disabled'},
        'temperature': 0.2,
        'max_tokens': 900,
    }).encode('utf-8')
    request = Request(DEEPSEEK_URL, data=payload, method='POST', headers={
        'Authorization': 'Bearer ' + api_key,
        'Content-Type': 'application/json',
    })
    try:
        with urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode('utf-8'))
        answer = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        if not answer:
            raise ValueError('DeepSeek returned an empty answer')
        return {'ok': True, 'mode': 'deepseek', 'model': result.get('model'), 'answer': answer}
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')[:500]
        return {'ok': False, 'error': f'DeepSeek HTTP {exc.code}: {detail}'}
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return {'ok': False, 'error': 'Không kết nối được DeepSeek: ' + str(exc)}

class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/save':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length).decode('utf-8')
                data = json.loads(body)
                os.makedirs('backups', exist_ok=True)
                with open('backups/latest-drawn.json', 'w') as f:
                    json.dump(data, f, ensure_ascii=False, indent=1)
                n = len(data.get('features', []))
                json_response(self, 200, {'ok': True, 'n': n})
            except Exception as e:
                json_response(self, 400, {'ok': False, 'error': str(e)})
        elif self.path == '/api/chat':
            try:
                length = min(int(self.headers.get('Content-Length', 0)), 200000)
                body = json.loads(self.rfile.read(length).decode('utf-8'))
                question = str(body.get('message', '')).strip()
                if not question:
                    return json_response(self, 400, {'ok': False, 'error': 'Thiếu câu hỏi'})
                result = call_deepseek(question, body.get('history', []), load_dashboard_data())
                json_response(self, 200 if result.get('ok') else 502, result)
            except Exception as e:
                json_response(self, 400, {'ok': False, 'error': str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # im lặng log


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print('Server: http://127.0.0.1:8899/  (POST /api/save de luu du lieu)')
    ThreadingHTTPServer(('127.0.0.1', 8899), Handler).serve_forever()
