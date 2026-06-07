from __future__ import annotations

import argparse
import os
import sys

from .llm import LLMClient
from .runtime import AgentRuntime
from .session import SessionStore
from .tools import build_tool_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal self-built Agent runtime")
    parser.add_argument("--session", default="default", help="Session id")
    parser.add_argument("--message", help="Run one user message and exit")
    parser.add_argument("--data-dir", default=".agent_data", help="Directory for session files")
    parser.add_argument("--max-steps", type=int, default=int(os.getenv("AGENT_MAX_STEPS", "6")))
    return parser


def create_runtime(data_dir: str, max_steps: int) -> AgentRuntime:
    store = SessionStore(data_dir)
    llm = LLMClient.from_env()
    tools = build_tool_registry()
    return AgentRuntime(llm=llm, session_store=store, tools=tools, max_steps=max_steps)


def run_one(runtime: AgentRuntime, session_id: str, message: str) -> int:
    answer = runtime.run(session_id=session_id, user_input=message)
    print(answer)
    return 0


def repl(runtime: AgentRuntime, session_id: str) -> int:
    print(f"Minimal Agent session: {session_id}")
    print("Type 'exit' or 'quit' to stop.")
    while True:
        try:
            user_input = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if user_input.lower() in {"exit", "quit"}:
            return 0
        if not user_input:
            continue

        try:
            answer = runtime.run(session_id=session_id, user_input=user_input)
        except Exception as exc:
            print(f"Agent error: {exc}", file=sys.stderr)
            continue

        print(f"\nAgent> {answer}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        runtime = create_runtime(args.data_dir, args.max_steps)
    except Exception as exc:
        print(f"Failed to initialize runtime: {exc}", file=sys.stderr)
        return 2

    if args.message:
        return run_one(runtime, args.session, args.message)
    return repl(runtime, args.session)


if __name__ == "__main__":
    raise SystemExit(main())
