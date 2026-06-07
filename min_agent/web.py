from __future__ import annotations

import json
import mimetypes
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .cli import create_runtime
from .session import SessionStore

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / ".agent_data"


class AgentWebHandler(BaseHTTPRequestHandler):
    server_version = "MinimalAgentWeb/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/session":
            query = parse_qs(parsed.query)
            session_id = query.get("id", ["default"])[0]
            self._send_json(self._load_session(session_id))
            return

        if parsed.path in {"/", "/index.html"}:
            self._send_file(WEB_DIR / "index.html")
            return

        requested = (WEB_DIR / parsed.path.lstrip("/")).resolve()
        if WEB_DIR.resolve() in requested.parents and requested.exists() and requested.is_file():
            self._send_file(requested)
            return

        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/chat":
            self.send_error(404, "Not found")
            return

        try:
            payload = self._read_json()
            session_id = str(payload.get("session_id") or "default")
            message = str(payload.get("message") or "").strip()
            if not message:
                raise ValueError("message is required")

            runtime = create_runtime(str(DATA_DIR), int(payload.get("max_steps") or 6))
            answer = runtime.run(session_id=session_id, user_input=message)
            session = self._load_session(session_id)
            session["answer"] = answer
            self._send_json(session)
        except Exception as exc:
            traceback.print_exc()
            self._send_json({"ok": False, "error": str(exc), "error_type": type(exc).__name__}, status=500)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _load_session(self, session_id: str) -> dict[str, object]:
        store = SessionStore(str(DATA_DIR))
        session = store.load(session_id)
        return {"ok": True, "session": session.to_dict()}

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length).decode("utf-8")
        data = json.loads(raw or "{}")
        if not isinstance(data, dict):
            raise ValueError("request body must be a JSON object")
        return data

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        body = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    host = "127.0.0.1"
    port = 8765
    server = ThreadingHTTPServer((host, port), AgentWebHandler)
    print(f"Agent visualizer running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
