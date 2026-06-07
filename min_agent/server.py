from __future__ import annotations

import json
import os
import sys
import uuid
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from .llm import LLMClient
from .runtime import AgentRuntime
from .session import SessionStore
from .tools import build_tool_registry

STATIC_DIR = Path(__file__).parent / "static"


class AgentAPIHandler(SimpleHTTPRequestHandler):
    """Serves static files and REST API for the Agent runtime."""

    runtime: AgentRuntime = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    # ── routing ──────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # API routes
        if path == "/api/sessions":
            return self._json(self._list_sessions())
        if path.startswith("/api/session/"):
            sid = path.split("/api/session/", 1)[1]
            return self._json(self._get_session(sid))

        # Static files – serve index.html for /
        if parsed.path == "/" or not self._static_exists(parsed.path):
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        data = self._read_body()

        if path == "/api/chat":
            session_id = data.get("session_id", "default")
            message = data.get("message", "").strip()
            if not message:
                return self._json({"error": "message is required"}, 400)

            answer = self.runtime.run(session_id, message)
            session = self.runtime.session_store.load(session_id)
            return self._json({
                "answer": answer,
                "session_id": session_id,
                "traces": session.traces,
                "tasks": session.tasks,
                "message_count": len(session.messages),
            })

        if path == "/api/session/new":
            sid = uuid.uuid4().hex[:8]
            return self._json({"session_id": sid})

        if path == "/api/session/delete":
            sid = data.get("session_id", "")
            if sid:
                p = self.runtime.session_store.sessions_dir / f"{sid}.json"
                if p.exists():
                    p.unlink()
            return self._json({"ok": True})

        return self._json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self._cors()
        self.send_response(200)
        self.end_headers()

    # ── helpers ──────────────────────────────────────────────

    def _static_exists(self, path: str) -> bool:
        clean = path.lstrip("/")
        if not clean:
            return False
        return (STATIC_DIR / clean).exists()

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _list_sessions(self):
        sd = self.runtime.session_store.sessions_dir
        sessions = sorted(
            [f.stem for f in sd.glob("*.json")],
            key=lambda s: (sd / f"{s}.json").stat().st_mtime,
            reverse=True,
        )
        return {"sessions": sessions}

    def _get_session(self, sid: str):
        s = self.runtime.session_store.load(sid)
        return {
            "session_id": s.session_id,
            "message_count": len(s.messages),
            "messages": s.messages,
            "tasks": s.tasks,
            "traces": s.traces,
        }

    def log_message(self, fmt, *args):
        if len(args) >= 1 and ("/api/" in str(args[0])):
            print(f"  [api] {args[0]}")
        else:
            super().log_message(fmt, *args)


def serve(port=8765, data_dir=".agent_data", max_steps=6):
    store = SessionStore(data_dir)
    llm = LLMClient.from_env()
    tools = build_tool_registry()
    rt = AgentRuntime(llm=llm, session_store=store, tools=tools, max_steps=max_steps)

    AgentAPIHandler.runtime = rt
    server = HTTPServer(("127.0.0.1", port), AgentAPIHandler)
    print(f"Agent test server  →  http://127.0.0.1:{port}")
    print(f"Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Minimal Agent API Server")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--data-dir", default=".agent_data")
    p.add_argument("--max-steps", type=int, default=6)
    args = p.parse_args()
    serve(args.port, args.data_dir, args.max_steps)
