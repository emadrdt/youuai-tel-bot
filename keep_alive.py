import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("OK".encode("utf-8"))

    def log_message(self, format, *args):
        pass  # لاگ‌های اضافی وب‌سرور را خاموش کن


def start_web_server() -> None:
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _Handler)
    server.serve_forever()


def run_in_background() -> None:
    thread = Thread(target=start_web_server, daemon=True)
    thread.start()