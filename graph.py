"""StateGraph ReAct: prune → agent → tools (sin if/else de routing)."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, RemoveMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.base import BaseCheckpointSaver

from config import get_llm
from orders import buscar_pedidos

SYSTEM = (
    "Eres un asistente de pedidos. Usa la herramienta buscar_pedidos cuando "
    "necesites datos de un cliente. Responde en español, breve y claro. "
    "Cita siempre el campo cliente_id del JSON de la herramienta "
    "(puede diferir del id que pidió el usuario tras una corrección humana)."
)


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def prune(state: State) -> dict[str, list[RemoveMessage]]:
    """Recorta el historial si hay demasiados mensajes."""
    messages = state["messages"]
    if len(messages) <= 8:
        return {}
    to_drop = messages[:-4]
    return {
        "messages": [
            RemoveMessage(id=m.id) for m in to_drop if getattr(m, "id", None)
        ]
    }


async def agent(state: State) -> dict[str, list[AnyMessage]]:
    """Invoca el LLM con herramientas y agrega la respuesta al estado."""
    llm = get_llm().bind_tools([buscar_pedidos])
    msgs = state["messages"]
    if not msgs or not isinstance(msgs[0], SystemMessage):
        msgs = [SystemMessage(content=SYSTEM), *msgs]
    response = await llm.ainvoke(msgs)
    return {"messages": [response]}


def build_graph(checkpointer: BaseCheckpointSaver):
    """Compila el StateGraph ReAct con el checkpointer indicado."""
    builder = StateGraph(State)
    builder.add_node("prune", prune)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode([buscar_pedidos]))

    builder.add_edge(START, "prune")
    builder.add_edge("prune", "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "prune")

    return builder.compile(checkpointer=checkpointer)
