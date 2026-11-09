import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def _env(name: str) -> str:
    """Lee una variable de entorno o falla si no existe."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Falta {name} en .env")
    return value


def get_llm() -> ChatOpenAI:
    """Crea el modelo ChatOpenAI configurado para el agente."""
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=_env("OPENAI_API_KEY"),
        temperature=0,
    )
