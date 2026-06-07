from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SAFE_SESSION_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


@dataclass
class Session:
    session_id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    traces: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        return cls(
            session_id=str(data["session_id"]),
            messages=list(data.get("messages", [])),
            tasks=dict(data.get("tasks", {})),
            traces=list(data.get("traces", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "tasks": self.tasks,
            "traces": self.traces,
        }


class SessionStore:
    def __init__(self, data_dir: str = ".agent_data") -> None:
        self.root = Path(data_dir)
        self.sessions_dir = self.root / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def load(self, session_id: str) -> Session:
        safe_id = self._safe_session_id(session_id)
        path = self._path_for(safe_id)
        if not path.exists():
            return Session(session_id=safe_id)
        with path.open("r", encoding="utf-8") as file:
            return Session.from_dict(json.load(file))

    def save(self, session: Session) -> None:
        path = self._path_for(session.session_id)
        with path.open("w", encoding="utf-8") as file:
            json.dump(session.to_dict(), file, ensure_ascii=False, indent=2)

    def _path_for(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def _safe_session_id(self, session_id: str) -> str:
        cleaned = SAFE_SESSION_RE.sub("_", session_id.strip())
        return cleaned or "default"
