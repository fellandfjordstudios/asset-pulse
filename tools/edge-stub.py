#!/usr/bin/env python3
"""A LOCAL STUB of agent A's intake, for testing the catalog's request form
without Turnstile, moderation or a store.

    tools/edge-stub.py [port]        # default 8787, the intake's local port in
                                     # the library's ops/edge/README.md

POST /v1/requests  201 {"id"}, as the real intake answers; it logs whether a
                   photo and a licence (CC-BY-4.0 or CC0-1.0) came with it and
                   stores nothing. A request with neither is refused 400 with a
                   reason, as the real intake would refuse it.
Every answer carries CORS headers, so the catalog served from another port can
post to it. Agent A's own Workers run under `wrangler dev` (its README); this
stub exists so the pulse's test needs no npm install and no secret.
"""
import json
import re
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


class Stub(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, "")

    def do_POST(self):
        if urlparse(self.path).path != "/v1/requests":
            return self._send(404, json.dumps({"error": "no such route"}))
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        photo = b'name="photo"; filename=' in body
        m = re.search(rb'name="licence"\r\n\r\n([^\r]*)', body)
        licence = m.group(1).decode() if m else ""
        if not photo or licence not in ("CC-BY-4.0", "CC0-1.0"):
            reason = "no photo" if not photo else "the licence must be CC-BY-4.0 or CC0-1.0"
            print("stub intake: refused (%s)" % reason, flush=True)
            return self._send(400, json.dumps({"refused": True, "link": "form", "reason": reason}))
        rid = uuid.uuid4().hex[:12]
        print("stub intake: %d bytes, photo, licence %s -> %s" % (len(body), licence, rid), flush=True)
        self._send(201, json.dumps({"id": rid, "stub": True}))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    print("intake stub on http://127.0.0.1:%d/v1/requests" % port, flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Stub).serve_forever()
