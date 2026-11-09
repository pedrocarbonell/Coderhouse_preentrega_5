"""Pedidos en SQLite + herramienta buscar_pedidos."""

import sqlite3
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt

ORDERS_DB = Path(__file__).resolve().parent / "orders.db"


def seed_orders(db_path: Path = ORDERS_DB) -> None:
    """Crea la tabla pedidos y carga datos de ejemplo."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY,
                cliente_id INTEGER NOT NULL,
                monto REAL NOT NULL,
                fecha TEXT NOT NULL
            )
            """
        )
        conn.execute("DELETE FROM pedidos")
        conn.executemany(
            "INSERT INTO pedidos (id, cliente_id, monto, fecha) VALUES (?, ?, ?, ?)",
            [
                (1, 102, 4500.0, "2026-01-10"),
                (2, 102, 5000.0, "2026-02-15"),
                (3, 102, 5000.0, "2026-03-20"),
                (4, 201, 1200.0, "2026-03-01"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _query(cliente_id: int, db_path: Path = ORDERS_DB) -> list[tuple[int, float, str]]:
    """Devuelve los pedidos de un cliente ordenados por fecha."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT id, monto, fecha
            FROM pedidos
            WHERE cliente_id = ?
            ORDER BY fecha ASC
            """,
            (cliente_id,),
        )
        return list(cur.fetchall())
    finally:
        conn.close()


def _result(cliente_id: int, rows: list[tuple[int, float, str]]) -> dict[str, Any]:
    """Arma el resumen JSON (cantidad, total y último pedido)."""
    if not rows:
        return {"cliente_id": cliente_id, "pedidos": 0, "total": 0, "ultimo": None}
    ultimo = rows[-1]
    return {
        "cliente_id": cliente_id,
        "pedidos": len(rows),
        "total": sum(r[1] for r in rows),
        "ultimo": {"id": ultimo[0], "monto": ultimo[1], "fecha": ultimo[2]},
    }


@tool
async def buscar_pedidos(cliente_id: int) -> dict[str, Any]:
    """Busca pedidos de un cliente y devuelve cantidad, total y último pedido."""
    rows = _query(cliente_id)
    if not rows:
        nuevo = interrupt(
            f"Cliente {cliente_id} no encontrado. Indica un cliente_id válido."
        )
        cliente_id = int(nuevo)
        rows = _query(cliente_id)
        if not rows:
            return _result(cliente_id, [])
    return _result(cliente_id, rows)
