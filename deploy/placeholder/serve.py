"""Placeholder web service: static files and GET /health, Python standard library only.

Environment (optional): ROOT (default /data/www), PORT (default 8000), HOST (default 0.0.0.0).
"""
import functools
import http.server
import json
import os
import time

ROOT = os.environ.get("ROOT", "/data/www")
PORT = int(os.environ.get("PORT", "8000"))
HOST = os.environ.get("HOST", "0.0.0.0")
STARTED = time.time()


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"status": "ok", "uptime_s": int(time.time() - STARTED)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()


if __name__ == "__main__":
    handler = functools.partial(Handler, directory=ROOT)
    http.server.ThreadingHTTPServer((HOST, PORT), handler).serve_forever()
