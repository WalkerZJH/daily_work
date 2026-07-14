from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
from pathlib import Path


class PrototypeHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve prototype HTML files locally.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5195)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    handler = functools.partial(PrototypeHandler, directory=str(root))

    with socketserver.ThreadingTCPServer((args.host, args.port), handler) as httpd:
        httpd.daemon_threads = True
        print(f"Prototype server: http://{args.host}:{args.port}/index.html")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
