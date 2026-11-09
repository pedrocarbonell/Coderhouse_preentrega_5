"""Entrada del agente: chat async con persistencia y traza ReAct."""

import asyncio
import json
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from graph import build_graph
from orders import seed_orders

TRACE_PATH = Path(__file__).resolve().parent / "traces" / "react.json"
CHECKPOINTS_DB = Path(__file__).resolve().parent / "checkpoints.sqlite"


def _msg_entry(msg: Any) -> dict[str, Any]:
    """Serializa un mensaje de LangChain para la traza JSON."""
    entry: dict[str, Any] = {"type": type(msg).__name__}
    if isinstance(msg, AIMessage) and msg.tool_calls:
        entry["tool_calls"] = [
            {"name": tc["name"], "args": tc["args"]} for tc in msg.tool_calls
        ]
    content = getattr(msg, "content", None)
    if content:
        entry["content"] = content
    if isinstance(msg, ToolMessage):
        entry["name"] = msg.name
    return entry


def _last_ai(state: Any) -> str:
    """Obtiene el último texto del asistente sin tool calls."""
    for msg in reversed(state.values.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return str(msg.content)
    return "(sin respuesta)"


async def main() -> None:
    """Loop de chat: ejecuta el grafo, maneja interrupts y guarda la traza."""
    seed_orders()
    TRACE_PATH.parent.mkdir(exist_ok=True)
    trace: list[dict[str, Any]] = []

    thread_id = input("thread_id [demo]: ").strip() or "demo"
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 10,
    }

    async with AsyncSqliteSaver.from_conn_string(str(CHECKPOINTS_DB)) as saver:
        graph = build_graph(saver)
        print("Escribe un mensaje (vacío para salir). Si hay interrupt, pedirá un cliente_id.")

        while True:
            text = input("tú> ").strip()
            if not text:
                break

            payload: dict[str, Any] | Command = {
                "messages": [HumanMessage(content=text)]
            }
            trace.append({"event": "turn_start", "input": text})

            while True:
                async for update in graph.astream(
                    payload, config, stream_mode="updates"
                ):
                    for node, delta in update.items():
                        step: dict[str, Any] = {"node": node}
                        if isinstance(delta, dict) and "messages" in delta:
                            step["messages"] = [
                                _msg_entry(m) for m in delta["messages"]
                            ]
                        else:
                            step["delta"] = str(delta)
                        trace.append(step)

                state = await graph.aget_state(config)
                if not state.interrupts:
                    print("agente:", _last_ai(state))
                    break

                print("pausa:", state.interrupts[0].value)
                resume = input("cliente_id resume> ").strip()
                if not resume:
                    break
                payload = Command(resume=int(resume))
                trace.append({"event": "resume", "cliente_id": int(resume)})

    TRACE_PATH.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Traza ReAct → {TRACE_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
