#!/usr/bin/env python3
"""Serve a cards folder so a browser can open the card (videos need HTTP range requests, which python -m http.server lacks).
usage: python serve.py <cards-folder> [port]   then open http://localhost:<port>/card.html#<name>"""
import http.server, os, re, sys
from functools import partial


class Range(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        m = re.match(r"bytes=(\d+)-(\d*)", self.headers.get("Range", ""))
        path = self.translate_path(self.path)
        if not m or not os.path.isfile(path): return super().send_head()
        size = os.path.getsize(path); a = int(m[1]); b = int(m[2]) if m[2] else size - 1
        if a >= size: self.send_error(416); return None
        b = min(b, size - 1); f = open(path, "rb"); f.seek(a)
        self.send_response(206); self.send_header("Content-Type", self.guess_type(path)); self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {a}-{b}/{size}"); self.send_header("Content-Length", str(b - a + 1)); self.end_headers()
        self._left = b - a + 1; return f

    def copyfile(self, src, dst):
        left = getattr(self, "_left", None)
        if left is None: return super().copyfile(src, dst)
        while left > 0:
            chunk = src.read(min(1 << 16, left))
            if not chunk: break
            dst.write(chunk); left -= len(chunk)

    def log_message(self, *a): pass


if __name__ == "__main__":
    root, port = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8790
    Range.extensions_map.update({".mp4": "video/mp4", ".webp": "image/webp", ".json": "application/json", ".js": "text/javascript"})
    print(f"serving {os.path.abspath(root)} on http://localhost:{port}/  (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), partial(Range, directory=root)).serve_forever()
