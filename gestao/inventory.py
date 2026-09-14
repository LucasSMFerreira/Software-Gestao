"""Movimentos são a única fonte do saldo; vendas e compras usam este módulo."""
from datetime import datetime, timezone
from uuid import uuid4

from gestao.database import session


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def balance_in(db, store_id: str, sku: str) -> int:
    exists = db.execute("SELECT 1 FROM products WHERE store_id=? AND sku=?", (store_id, sku)).fetchone()
    if not exists:
        raise ValueError("Produto não cadastrado nesta loja.")
    return int(db.execute("SELECT COALESCE(SUM(delta),0) FROM movements WHERE store_id=? AND sku=?", (store_id, sku)).fetchone()[0])


def balance(store_id: str, sku: str) -> int:
    with session() as db:
        return balance_in(db, store_id, sku)


def add_in(db, store_id: str, sku: str, kind: str, delta: int, reference: str) -> str:
    current = balance_in(db, store_id, sku)
    if current + delta < 0:
        raise ValueError(f"Saldo insuficiente: {current} unidade(s).")
    identifier = uuid4().hex[:12].upper()
    db.execute("INSERT INTO movements VALUES (?,?,?,?,?,?,?)",
               (identifier, store_id, sku, kind, delta, reference, now()))
    return identifier


def adjust(store_id: str, sku: str, target: int) -> int:
    if isinstance(target, bool) or not isinstance(target, int) or target < 0:
        raise ValueError("Informe um saldo inteiro maior ou igual a zero.")
    with session() as db:
        current = balance_in(db, store_id, sku)
        add_in(db, store_id, sku, "Conferência", target-current, "count:"+uuid4().hex)
    return target


def movements(store_id: str | None = None, sku: str | None = None) -> list[dict]:
    query = "SELECT * FROM movements WHERE 1=1"
    values = []
    if store_id:
        query += " AND store_id=?"
        values.append(store_id)
    if sku:
        query += " AND sku=?"
        values.append(sku)
    with session() as db:
        return [dict(row) for row in db.execute(query+" ORDER BY created_at DESC,id DESC LIMIT 100", values)]
