#!/usr/bin/env python3
"""Máy chủ tĩnh + nhận dữ liệu lưu về máy từ app (POST /api/save).

Chạy:  python3 server.py   ->  http://127.0.0.1:8899/
Dữ liệu app bấm "💾 Lưu về máy" sẽ ghi vào backups/latest-drawn.json
"""
import json, os
from http.server import HTTPServer, SimpleHTTPRequestHandler

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
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(('{"ok":true,"n":' + str(n) + '}').encode())
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(('{"ok":false,"error":"' + str(e) + '"}').encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # im lặng log


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print('Server: http://127.0.0.1:8899/  (POST /api/save de luu du lieu)')
    HTTPServer(('127.0.0.1', 8899), Handler).serve_forever()
