"""Phase 9 EXTENSION — remote Streamable-HTTP transport + auth over the read-only MCP server.
Pre-registration: docs/PHASE9_PLAN.md AMENDMENT 2026-08-02 (G9.9–G9.14).

TRANSPORT + AUTH ONLY. This module adds NO science, NO schema, NO query logic. It reuses
`jobs.mcp_server.handle()` VERBATIM — no tool is re-implemented here — so HTTP tool payloads are
byte-identical to the stdio path by construction (G9.9). `guarded_query` and the manifest allowlist
are untouched (G9.11): every write vector is still refused inside `mcp_server` before DuckDB.

Threat model (see amendment): under remote transport `guarded_query` is the ONLY control between the
open internet and the warehouse, so auth is BLOCKING. Auth here is a static Bearer token, compared in
constant time, checked BEFORE any dispatch — so an unauthenticated request opens ZERO DuckDB
connections (G9.10, proven by `mcp_server.CONN_COUNT` + the AUTH_REJECT log line). The server is
FAIL-CLOSED at startup: no token ⇒ it refuses to start.

Scope limits (labelled PROVISIONAL / author-supplied in the amendment): minimal JSON-RPC-2.0
handshake subset (`initialize` / `tools/list` / `tools/call`); NO SSE server→client streaming; static
bearer token (OAuth 2.0 / mTLS is the documented production upgrade). No deployment is performed.

    DYNASTY_MCP_TOKEN=<secret> uv run python -m jobs.mcp_http --host 127.0.0.1 --port 8848
"""
from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobs import mcp_server as mcp

LOG = logging.getLogger("dynasty.mcp_http")

# MCP protocol version this transport advertises on `initialize`. The Streamable-HTTP wire shape
# (JSON-RPC 2.0 over POST) is the connector contract; this string is metadata, not a statistic.
PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "dynasty-engine-mcp", "version": "0.1.0"}
TOKEN_ENV = "DYNASTY_MCP_TOKEN"

# Canonical JSON serialization — used identically on BOTH transports so G9.9 parity is a byte compare.
_DUMP = dict(sort_keys=True, ensure_ascii=False)


def canonical(obj) -> str:
    """The single serialization used for parity: the stdio path and the HTTP path both render the
    tool payload through this, so 'byte-identical' (G9.9) is a literal string equality."""
    return json.dumps(obj, **_DUMP)


def _tool_list() -> list:
    """Advertise the same tools the stdio dispatch exposes (`mcp_server.TOOLS`). Loose input schema —
    the tools validate their own args; this is a discovery surface, not a new contract."""
    descriptions = {
        "trade_delta": "Dual-pool trade E[Δ] (corpus AND consensus) with MC precision bands.",
        "archetype_gap": "Archetype-vs-draft-capital AUC gap (indistinguishable); DeLong CI.",
        "college_null": "College-production Westfall–Young family-wise p (UNINFORMATIVE, not null).",
        "startup_strategy": "Startup-strategy markings (no VALIDATED edge; edges UNINFORMATIVE).",
        "season_state": "2026 season state (NOT_STARTED/IN_PROGRESS/COMPLETE) — metadata.",
        "answer": "Fail-closed natural-language router over the supported manifest.",
    }
    return [{"name": name,
             "description": descriptions.get(name, name),
             "inputSchema": {"type": "object", "properties": {}, "additionalProperties": True}}
            for name in mcp.TOOLS]


def _rpc_ok(rid, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _rpc_error(rid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def dispatch(req: dict):
    """JSON-RPC 2.0 dispatch. `tools/call` routes to `mcp_server.handle()` VERBATIM — the exact
    function the stdio server calls — so the emitted payload cannot drift from stdio. Returns None for
    notifications (the HTTP layer answers those with 202/no body)."""
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        return _rpc_ok(rid, {"protocolVersion": PROTOCOL_VERSION, "serverInfo": SERVER_INFO,
                             "capabilities": {"tools": {"listChanged": False}}})
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None  # notification — no JSON-RPC response
    if method == "tools/list":
        return _rpc_ok(rid, {"tools": _tool_list()})
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        LOG.info("DISPATCH method=tools/call tool=%s", name)
        try:
            payload = mcp.handle({"tool": name, "args": args})   # <-- reused verbatim (parity + guard)
        except Exception as e:  # noqa: BLE001 — never leak a stack to the internet; surface a hard_fail
            LOG.warning("TOOL_ERROR tool=%s err=%s", name, type(e).__name__)
            payload = {"hard_fail": f"{type(e).__name__}: {e}"}
        is_error = ("error" in payload) or ("hard_fail" in payload)
        # MCP-compliant result: text content + the canonical payload as structuredContent (the G9.9
        # parity surface). Both are rendered through `canonical`, identical to the stdio serialization.
        return _rpc_ok(rid, {"content": [{"type": "text", "text": canonical(payload)}],
                             "structuredContent": payload, "isError": is_error})
    return _rpc_error(rid, -32601, f"method not found: {method!r}")


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"          # keep-alive; every response carries Content-Length

    # Silence the default stderr access log; we emit our own structured audit lines (G9.10).
    def log_message(self, *_a):
        return

    def _send(self, code: int, obj, extra_headers: dict | None = None) -> None:
        body = b"" if obj is None else canonical(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _authorized(self) -> bool:
        """Constant-time Bearer check. Requires the exact `Bearer <token>` header; anything else
        (missing header, wrong scheme, wrong token) is unauthorized."""
        presented = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.token}"          # type: ignore[attr-defined]
        return presented.startswith("Bearer ") and hmac.compare_digest(presented, expected)

    def _auth_gate(self) -> bool:
        """AUTH GATE — runs BEFORE any routing/dispatch/DuckDB (G9.10). Returns True iff the request
        may proceed; otherwise it has already written a 401 and logged AUTH_REJECT."""
        if self._authorized():
            LOG.info("AUTH_OK method=%s path=%s", self.command, self.path)
            return True
        LOG.warning("AUTH_REJECT method=%s path=%s peer=%s", self.command, self.path,
                    self.client_address[0])
        self._send(401, {"error": "unauthorized", "detail": "Bearer token required"},
                   {"WWW-Authenticate": "Bearer"})
        return False

    def do_POST(self) -> None:
        if not self._auth_gate():
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            req = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send(400, _rpc_error(None, -32700, "parse error"))
            return
        resp = dispatch(req)
        if resp is None:                      # notification → 202 Accepted, empty body (MCP)
            self._send(202, None)
            return
        self._send(200, resp)

    def do_GET(self) -> None:
        # MCP Streamable HTTP opens the server→client SSE stream via GET. We do NOT implement SSE
        # (documented scope limit), but the endpoint is still auth-gated so an UNauth GET is 401
        # (G9.10: "every registered endpoint"), and an authed GET is 405 (no streaming).
        if not self._auth_gate():
            return
        self._send(405, {"error": "SSE streaming not supported; POST JSON-RPC to this endpoint"},
                   {"Allow": "POST"})


def make_server(host: str = "127.0.0.1", port: int = 0, token: str | None = None) -> ThreadingHTTPServer:
    """Build the threading HTTP server. FAIL-CLOSED: without a token it refuses to start rather than
    expose an unauthenticated warehouse to the internet (G9.10)."""
    token = token or os.environ.get(TOKEN_ENV)
    if not token:
        raise RuntimeError(
            f"{TOKEN_ENV} is required — the remote MCP transport refuses to start unauthenticated "
            "(fail-closed; guarded_query is the only control in front of the warehouse over the "
            "internet). Set a strong random token and provision it to the connector out-of-band.")
    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.token = token                       # type: ignore[attr-defined]
    return httpd


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only dynasty MCP over Streamable HTTP (Bearer auth)")
    ap.add_argument("--host", default="127.0.0.1", help="bind host (default localhost)")
    ap.add_argument("--port", type=int, default=8848, help="bind port")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    httpd = make_server(args.host, args.port)
    LOG.info("SERVE host=%s port=%s (bearer auth, read-only; SSE unsupported)",
             args.host, httpd.server_address[1])
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
