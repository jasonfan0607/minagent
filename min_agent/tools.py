from __future__ import annotations

import ast
import operator
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from .session import Session


@dataclass
class ToolContext:
    session: Session


@dataclass
class Tool:
    name: str
    description: str
    args_schema: dict[str, Any]
    run: Callable[[dict[str, Any], ToolContext], Any]


def build_tool_registry() -> dict[str, Tool]:
    tools = [
        Tool(
            name="calculator",
            description="Safely evaluate basic arithmetic expressions.",
            args_schema={"expression": "string, arithmetic expression such as (12+8)*3"},
            run=calculator_tool,
        ),
        Tool(
            name="search",
            description="Mock search for public-looking information. Returns deterministic local results.",
            args_schema={"query": "string"},
            run=search_tool,
        ),
        Tool(
            name="read_docs",
            description="Read built-in project documents by topic.",
            args_schema={"topic": "string, one of: requirements, architecture, memory, tools"},
            run=read_docs_tool,
        ),
        Tool(
            name="todo",
            description="Create, update, list, or get persistent tasks in the current session.",
            args_schema={
                "action": "create | update | list | get",
                "title": "string, required for create",
                "task_id": "string, required for update/get",
                "status": "string, optional status",
                "note": "string, optional progress note",
            },
            run=todo_tool,
        ),
        Tool(
            name="weather",
            description="Mock weather lookup for a city.",
            args_schema={"city": "string"},
            run=weather_tool,
        ),
    ]
    return {tool.name: tool for tool in tools}


ALLOWED_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
ALLOWED_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculator_tool(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    expression = str(args.get("expression", "")).strip()
    if not expression:
        raise ValueError("expression is required")
    result = _eval_expr(ast.parse(expression, mode="eval").body)
    return {"expression": expression, "result": result}


def _eval_expr(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BIN_OPS:
        left = _eval_expr(node.left)
        right = _eval_expr(node.right)
        return ALLOWED_BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_UNARY_OPS:
        return ALLOWED_UNARY_OPS[type(node.op)](_eval_expr(node.operand))
    raise ValueError("only basic arithmetic is allowed")


def search_tool(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("query is required")
    return {
        "query": query,
        "results": [
            {
                "title": "Mock result: minimal agent runtime",
                "snippet": "A minimal Agent typically has an LLM planner, tool executor, memory, trace logs, and a max-step guard.",
                "url": "mock://agent-runtime",
            },
            {
                "title": "Mock result: session memory",
                "snippet": "Persistent session state lets later turns continue tasks instead of restarting from scratch.",
                "url": "mock://session-memory",
            },
        ],
    }


DOCS = {
    "requirements": "The exam requires multi-turn session support, a self-built runtime loop, at least three tools, max steps, exception handling, trace logs, real LLM API usage, and a cross-turn continuation scenario.",
    "architecture": "The runtime builds messages, asks the LLM for a JSON action, executes one tool if requested, appends the observation, and repeats until final answer or max steps.",
    "memory": "Memory is stored per session. Recent messages, structured tasks, and recent traces are recalled before each runtime loop.",
    "tools": "Built-in tools include calculator, mock search, read_docs, todo, and mock weather.",
}


def read_docs_tool(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    topic = str(args.get("topic", "")).strip().lower()
    if topic not in DOCS:
        raise ValueError(f"unknown topic: {topic}. Choose one of {', '.join(DOCS)}")
    return {"topic": topic, "content": DOCS[topic]}


def todo_tool(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    action = str(args.get("action", "")).strip().lower()
    tasks = context.session.tasks

    if action == "create":
        title = str(args.get("title", "")).strip()
        if not title:
            raise ValueError("title is required for create")
        task_id = uuid.uuid4().hex[:8]
        tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": str(args.get("status") or "created"),
            "notes": [],
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        }
        note = str(args.get("note", "")).strip()
        if note:
            tasks[task_id]["notes"].append(note)
        return tasks[task_id]

    if action == "update":
        task_id = str(args.get("task_id", "")).strip()
        if task_id not in tasks:
            raise ValueError(f"unknown task_id: {task_id}")
        status = args.get("status")
        note = str(args.get("note", "")).strip()
        if status:
            tasks[task_id]["status"] = str(status)
        if note:
            tasks[task_id].setdefault("notes", []).append(note)
        tasks[task_id]["updated_at"] = int(time.time())
        return tasks[task_id]

    if action == "get":
        task_id = str(args.get("task_id", "")).strip()
        if task_id not in tasks:
            raise ValueError(f"unknown task_id: {task_id}")
        return tasks[task_id]

    if action == "list":
        return {"tasks": list(tasks.values())}

    raise ValueError("action must be one of create, update, list, get")


def weather_tool(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    city = str(args.get("city", "")).strip()
    if not city:
        raise ValueError("city is required")
    profiles = {
        "北京": {"condition": "晴", "temperature_c": 26},
        "上海": {"condition": "多云", "temperature_c": 25},
        "深圳": {"condition": "阵雨", "temperature_c": 29},
    }
    return {"city": city, **profiles.get(city, {"condition": "mock clear", "temperature_c": 22})}
