"""SeekLit 本地开发服务器：静态文件 + /functions/v1/app 代理到本地 Deno(:8000)。
零依赖（仅标准库）。用法：python dev/serve_local.py [端口，默认5173]
"""
import http.server
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM = "http://127.0.0.1:8000"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kw):
        super().__init__(*args, directory=os.path.join(ROOT, "web"), **kw)

    def do_GET(self):
        if self.path.startswith("/functions/v1/app"):
            return self.proxy("GET")
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/functions/v1/app"):
            return self.proxy("POST")
        self.send_error(405)

    def do_PUT(self):
        if self.path.startswith("/functions/v1/app"):
            return self.proxy("PUT")
        self.send_error(405)

    def do_DELETE(self):
        if self.path.startswith("/functions/v1/app"):
            return self.proxy("DELETE")
        self.send_error(405)

    def proxy(self, method):
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=method)
        for h in ("content-type", "x-api-token"):
            if self.headers.get(h):
                req.add_header(h, self.headers[h])
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                self.send_response(resp.status)
                ct = resp.headers.get("content-type", "application/json")
                self.send_header("content-type", ct)
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("content-type", e.headers.get("content-type", "application/json"))
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            payload = ('{"code":"BACKEND_OFFLINE","message":"本地 Function 服务不可达: %s"}' % e).encode()
            self.send_response(503)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
    print(f"SeekLit dev server on http://127.0.0.1:{port} (static + /functions proxy -> {UPSTREAM})")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
