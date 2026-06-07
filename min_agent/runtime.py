from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from .llm import LLMClient
from .session import Session, SessionStore
from .tools import Tool, ToolContext


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
TASK_INTENT_RE = re.compile(r"(创建|新建|记录|更新|继续|进度|任务|todo|待办)", re.IGNORECASE)


@dataclass
class AgentRuntime:
    llm: LLMClient
    session_store: SessionStore
    tools: dict[str, Tool]
    max_steps: int = 6

    def run(self, session_id: str, user_input: str) -> str:
        session = self.session_store.load(session_id)
        session.messages.append({"role": "user", "content": user_input})

        messages = self._build_messages(session)
        final_answer = ""
        todo_tool_used = False

        for step in range(1, self.max_steps + 1):
            started_at = time.time()
            trace: dict[str, Any] = {
                "step": step,
                "ts": int(started_at),
                "kind": "llm",
            }

            try:
                raw = self.llm.chat(messages)
                trace["raw"] = raw
            except Exception as exc:
                trace["error"] = str(exc)
                session.traces.append(trace)
                final_answer = f"LLM 调用失败：{exc}"
                break

            try:
                action = self._parse_action(raw)
                trace["action"] = action
            except Exception as exc:
                trace["parse_error"] = str(exc)
                if raw.strip():
                    action = {"type": "final", "answer": raw.strip()}
                    trace["action"] = action
                else:
                    trace["error"] = f"LLM 返回空内容，已请求模型按 JSON 协议重试：{exc}"
                    session.traces.append(trace)
                    messages.append({"role": "assistant", "content": raw})
                    messages.append(
                        {
                            "role": "user",
                            "content": 'Your previous response was empty or invalid. Return ONLY valid JSON with type "final" or "tool". If a tool observation is available, summarize it as a final answer.',
                        }
                    )
                    continue

            session.traces.append(trace)

            if self._requires_todo_tool(user_input, action, todo_tool_used):
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "user",
                        "content": 'This user request is about task state. You must call the todo tool instead of answering directly. Return ONLY JSON like {"type":"tool","tool":"todo","args":{"action":"create","title":"...","status":"...","note":"..."}} or use list/get/update as appropriate.',
                    }
                )
                continue

            if action.get("type") == "final":
                final_answer = str(action.get("answer", "")).strip()
                break

            if action.get("type") != "tool":
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "user",
                        "content": 'Invalid action. Return JSON with type "final" or "tool".',
                    }
                )
                continue

            tool_name = str(action.get("tool", ""))
            args = action.get("args") or {}
            if tool_name == "todo":
                todo_tool_used = True
            observation = self._execute_tool(session, step, tool_name, args)
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Tool observation:\n{json.dumps(observation, ensure_ascii=False)}"})
        else:
            final_answer = "已达到最大步数限制，任务未能在本轮内完成。请缩小问题或继续追问。"

        if final_answer:
            session.messages.append({"role": "assistant", "content": final_answer})
        self.session_store.save(session)
        return final_answer

    def _execute_tool(self, session: Session, step: int, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        trace: dict[str, Any] = {
            "step": step,
            "ts": int(time.time()),
            "kind": "tool",
            "tool": tool_name,
            "args": args,
        }

        try:
            if tool_name not in self.tools:
                raise RuntimeError(f"Unknown tool: {tool_name}")
            context = ToolContext(session=session)
            result = self.tools[tool_name].run(args, context)
            trace["ok"] = True
            trace["result"] = result
            observation = {"ok": True, "tool": tool_name, "result": result}
        except Exception as exc:
            trace["ok"] = False
            trace["error"] = str(exc)
            observation = {"ok": False, "tool": tool_name, "error": str(exc)}

        session.traces.append(trace)
        return observation

    def _requires_todo_tool(self, user_input: str, action: dict[str, Any], todo_tool_used: bool) -> bool:
        if todo_tool_used:
            return False
        if "todo" not in self.tools:
            return False
        if action.get("type") == "tool" and action.get("tool") == "todo":
            return False
        if action.get("type") not in {"final", "tool"}:
            return False
        return bool(TASK_INTENT_RE.search(user_input))

    def _build_messages(self, session: Session) -> list[dict[str, str]]:
        tool_specs = [
            {"name": tool.name, "description": tool.description, "args_schema": tool.args_schema}
            for tool in self.tools.values()
        ]
        session_state = {
            "session_id": session.session_id,
            "tasks": session.tasks,
            "recent_traces": session.traces[-5:],
        }
        system = f"""You are a minimal self-built Agent runtime.
You can either answer directly or request exactly one tool call per step.

Return ONLY valid JSON. Do not add Markdown or extra text.

Final answer format:
{{"type":"final","answer":"your answer"}}

Tool call format:
{{"type":"tool","tool":"tool_name","args":{{}}}}

Available tools:
{json.dumps(tool_specs, ensure_ascii=False, indent=2)}

Session state:
{json.dumps(session_state, ensure_ascii=False, indent=2)}

Rules:
- Use tools when calculation, search, document lookup, weather, or task state changes are needed.
- For task creation, updates, listing, retrieval, progress changes, or todo requests, always call the todo tool instead of answering directly.
- For ongoing tasks, inspect Session state and continue from the saved task status.
- After receiving a tool observation, decide whether another tool is needed or final answer is ready.
- If a user asks to continue or update progress, use the saved task status before producing a final answer.
- Keep answers concise and mention relevant task status when continuing across turns.
"""
        recent_messages = session.messages[-12:]
        return [{"role": "system", "content": system}, *recent_messages]

    def _parse_action(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        block = JSON_BLOCK_RE.search(text)
        if block:
            text = block.group(1)
        elif not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start : end + 1]

        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("LLM action must be a JSON object")
        return parsed
