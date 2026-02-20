#!/usr/bin/env python3
"""Simple local debug receiver for sandbox runtimes.

Examples:
  ./debug/receiver.py --port 3333
  curl -X POST http://127.0.0.1:3333/log -d 'hello'
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    server_version = "cc1c-debug-receiver/1.0"

    def _reply(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._reply(200, {"ok": True, "service": "debug-receiver"})
        else:
            self._reply(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b""
        text = raw.decode("utf-8", errors="replace")
        ts = datetime.now(timezone.utc).isoformat()
        print(f"[{ts}] {self.client_address[0]} {self.path} {text}", flush=True)
        self._reply(200, {"ok": True})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Local debug receiver")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3333)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"debug-receiver listening on http://{args.bind}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

