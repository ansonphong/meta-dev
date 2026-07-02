#!/usr/bin/env python3
"""
Local reverse proxy that strips the `anthropic-beta` header (and the
`?beta=true` query param) before forwarding to Z.AI's Anthropic-compatible
GLM endpoint.

WHY THIS EXISTS
---------------
Z.AI's https://api.z.ai/api/anthropic rejects ANY request carrying an
`anthropic-beta` header with:

    429 · [1302][Rate limit reached for requests]

Claude Code ALWAYS sends a non-empty `anthropic-beta` header on every API
call (e.g. claude-code-20250219, interleaved-thinking-2025-05-14,
effort-2025-11-24, ...). Several of those core betas are NOT suppressible via
env vars (CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS / DISABLE_PROMPT_CACHING only
remove some). The result: a headless `claude -p` worker pointed at Z.AI gets
[1302] on every attempt, Claude Code's SDK retries it 10x (~210s of backoff)
treating it as "overloaded", then surfaces the failure as a 529 — so every
GLM headless worker deterministically dies.

This proxy makes the request look "plain" to Z.AI by deleting the
`anthropic-beta` header and the `?beta=true` query string before forwarding.
With the header stripped, Z.AI serves glm-5.2 / glm-4.5 on the funded standard
tier (HTTP 200). DeepSeek and the real-Anthropic Sonnet backend are unaffected
— only the GLM backend routes through here (see claude-headless-exec).

USAGE
-----
    python3 glm-beta-strip-proxy.py [listen_port]   # default 8898

claude-headless-exec starts this on an ephemeral port for each GLM worker and
points the worker's ANTHROPIC_BASE_URL at it.

Verified working 2026-07-02: worker writes a file + returns exit 0 in ~87s
(was: deterministic 529 after ~210s before this proxy).
"""
import http.server
import http.client
import ssl
import sys

UPSTREAM_HOST = "api.z.ai"
UPSTREAM_PATH_PREFIX = "/api/anthropic"
# Request headers we must NOT forward to the upstream (and hop-by-hop headers).
DROP_REQ_HEADERS = {"anthropic-beta", "host", "content-length", "connection", "transfer-encoding"}
# Response headers we must NOT echo back to the client (hop-by-hop / re-framed).
DROP_RESP_HEADERS = {"transfer-encoding", "connection", "content-length"}


class StripProxy(http.server.BaseHTTPRequestHandler):
    """Forward requests to Z.AI with `anthropic-beta` and `?beta=true` removed."""

    def _forward(self):
        # Read the full request body.
        ln = int(self.headers.get("content-length", 0) or 0)
        body = self.rfile.read(ln) if ln else b""

        # Drop the query string (Claude Code appends `?beta=true`).
        path = self.path.split("?", 1)[0]
        if not path.startswith(UPSTREAM_PATH_PREFIX):
            path = UPSTREAM_PATH_PREFIX + path

        # Copy headers, stripping the beta header + hop-by-hop noise.
        hdrs = {k: v for k, v in self.headers.items() if k.lower() not in DROP_REQ_HEADERS}

        try:
            conn = http.client.HTTPSConnection(UPSTREAM_HOST, timeout=600,
                                               context=ssl.create_default_context())
            conn.request(self.command, path, body=body, headers=hdrs)
            resp = conn.getresponse()
        except Exception as e:  # upstream unreachable / TLS error
            try:
                self.send_response(502)
                self.send_header("content-type", "text/plain")
                self.end_headers()
                self.wfile.write(f"glm-beta-strip-proxy upstream error: {e}".encode())
            except Exception:
                pass
            return

        # Echo the upstream status + headers (minus hop-by-hop), then stream the body.
        self.send_response(resp.status, resp.reason)
        for k, v in resp.getheaders():
            if k.lower() in DROP_RESP_HEADERS:
                continue
            self.send_header(k, v)
        self.send_header("Connection", "close")  # we re-framed; signal close-delimited body
        self.end_headers()
        try:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # client went away
        conn.close()

    do_POST = _forward
    do_GET = _forward
    do_PUT = _forward
    do_DELETE = _forward
    do_PATCH = _forward

    def log_message(self, *a):
        pass  # quiet by default; claude-headless-exec owns the user-facing output


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8898
    http.server.ThreadingHTTPServer(("127.0.0.1", port), StripProxy).serve_forever()
