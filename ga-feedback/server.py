#!/usr/bin/env python3
"""GA Feedback Server — standalone feedback receiver for any local web page."""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

FEEDBACKS_FILE = os.path.join(os.path.dirname(__file__), 'feedbacks.json')
WWW_DIR = os.path.join(os.path.dirname(__file__), 'www')
LAST_READ_FILE = os.path.join(os.path.dirname(__file__), 'last_read.txt')
PORT = 9876


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == '/' or path == '/bookmarklet.html':
            self._serve_file(os.path.join(WWW_DIR, 'bookmarklet.html'), 'text/html')
        elif path == '/ga-feedback.js':
            self._serve_file(os.path.join(WWW_DIR, 'ga-feedback.js'), 'application/javascript')
        elif path == '/api/feedbacks':
            self._serve_json(self._load_feedbacks())
        elif path == '/api/health':
            self._serve_json({'status': 'ok', 'port': PORT})
        elif path.startswith('/api/submit'):
            qs = urlparse(self.path).query
            params = parse_qs(qs)
            callback = params.get('callback', [''])[0]
            data_json = params.get('data', [''])[0]
            try:
                data = json.loads(data_json)
                feedbacks = self._load_feedbacks()
                feedbacks.append(data)
                self._save_feedbacks(feedbacks)
                response = json.dumps({'ok': True, 'count': len(feedbacks)})
            except Exception as e:
                response = json.dumps({'ok': False, 'error': str(e)})
            if callback:
                body = (callback + '(' + response + ');').encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/javascript')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._serve_json({'error': 'missing callback'}, 400)
        elif path == '/api/pending':
            feedbacks = self._load_feedbacks()
            count = len(feedbacks)
            last_read = self._get_last_read()
            self._serve_json({'pending': count > last_read, 'count': count, 'unread': count - last_read})
        elif path.startswith('/api/ack') and parsed.query:
            qs = {p.split('=')[0]: p.split('=')[1] for p in parsed.query.split('&') if '=' in p}
            if 'count' in qs:
                self._set_last_read(int(qs['count']))
                self._serve_json({'ok': True})
            else:
                self.send_error(400)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/feedback':
            try:
                length = int(self.headers.get('Content-Length', 0))
                if length <= 0 or length > 10 * 1024 * 1024:
                    self._serve_json({'error': 'invalid content length'}, 400)
                    return
            except (ValueError, TypeError):
                self._serve_json({'error': 'invalid content length'}, 400)
                return
            body = self.rfile.read(length)
            try:
                body = body.decode('utf-8')
            except UnicodeDecodeError:
                self._serve_json({'error': 'invalid utf-8'}, 400)
                return
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._serve_json({'error': 'invalid json'}, 400)
                return
            feedbacks = self._load_feedbacks()
            feedbacks.append(data)
            self._save_feedbacks(feedbacks)
            self._serve_json({'ok': True, 'count': len(feedbacks)})
        elif self.path == '/api/reset':
            self._save_feedbacks([])
            self._set_last_read(0)
            self._serve_json({'ok': True, 'count': 0})
        else:
            self.send_error(404)

    def _load_feedbacks(self):
        if not os.path.exists(FEEDBACKS_FILE):
            return []
        with open(FEEDBACKS_FILE, 'r') as f:
            return json.load(f)

    def _save_feedbacks(self, data):
        tmp = FEEDBACKS_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, FEEDBACKS_FILE)  # atomic on Linux

    def _get_last_read(self):
        if not os.path.exists(LAST_READ_FILE):
            return 0
        with open(LAST_READ_FILE, 'r') as f:
            try:
                return int(f.read().strip())
            except (ValueError, TypeError):
                return 0

    def _set_last_read(self, count):
        with open(LAST_READ_FILE, 'w') as f:
            f.write(str(count))

    def _serve_file(self, path, mime):
        if not os.path.exists(path):
            self.send_error(404)
            return
        with open(path, 'rb') as f:
            content = f.read()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_json(self, data, status=200):
        content = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        if len(args) >= 3:
            print(f"[ga-feedback] {args[0]} {args[1]} {args[2]}")
        else:
            print(f"[ga-feedback] {' '.join(str(a) for a in args)}")


def main():
    server = HTTPServer(('127.0.0.1', PORT), Handler)
    print(f"\n  🌐 GA Feedback Server running at:")
    print(f"  ┌──────────────────────────────────────────────┐")
    print(f"  │  http://localhost:{PORT}/bookmarklet.html          │")
    print(f"  │  http://localhost:{PORT}/ga-feedback.js            │")
    print(f"  │  POST /api/feedback                          │")
    print(f"  │  POST /api/reset                             │")
    print(f"  │  GET  /api/pending                           │")
    print(f"  └──────────────────────────────────────────────┘\n")
    print(f"  📤 feedbacks written to: {FEEDBACKS_FILE}")
    print(f"  🚀 Ready. Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  👋 Server stopped.\n")
        server.server_close()


if __name__ == '__main__':
    main()
