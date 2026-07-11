import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from . import core
from . import analysis

HTML_PATH = Path(__file__).resolve().parent / "dashboard.html"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # quiet; the terminal is for run.sh output

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj):
        self._send(200, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        try:
            if u.path == "/" or u.path == "/index.html":
                self._send(200, HTML_PATH.read_bytes(), "text/html; charset=utf-8")
            elif u.path == "/api/summary":
                self._json(core.api_summary())
            elif u.path == "/api/series":
                self._json(core.api_series(qs))
            elif u.path == "/api/opinion":
                self._json(core.api_opinion(qs))
            elif u.path == "/api/repost":
                self._json(core.api_repost(qs))
            elif u.path == "/api/network":
                self._json(analysis.api_network(qs))
            elif u.path == "/api/log":
                self._send(200, core.api_log(qs).encode(), "text/plain; charset=utf-8")
            elif u.path == "/favicon.ico":
                self._send(204, b"", "image/x-icon")
            else:
                self._send(404, b"not found", "text/plain")
        except BrokenPipeError:
            pass
        except Exception as e:
            self._send(500, f"{type(e).__name__}: {e}".encode(), "text/plain")


def run_server(logdir: Path, only, host: str, port: int):
    core.SERVE_LOGDIR = logdir
    core.SERVE_ONLY = only
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"Serving interactive dashboard at {url}")
    print("Over SSH / VSCode Remote-SSH: check the PORTS tab for an auto-forward "
          "toast, or Cmd/Ctrl+Shift+P -> 'Simple Browser: Show' -> paste the URL above.")
    print("Ctrl-C to stop (does not affect the simulations).")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
