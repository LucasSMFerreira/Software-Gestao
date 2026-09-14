"""Livro único de estoque físico e reservado, com motivo por movimento manual."""
from datetime import datetime, timezone
from uuid import uuid4

from gestao.database import session


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def state_in(db, store_id: str, sku: str) -> dict[str, int]:
    exists = db.execute("SELECT 1 FROM products WHERE store_id=? AND sku=?", (store_id, sku)).fetchone()
    if not exists:
        raise ValueError("Produto não cadastrado nesta loja.")
    row = db.execute("""SELECT COALESCE(SUM(delta),0),COALESCE(SUM(reserved_delta),0)
        FROM movements WHERE store_id=? AND sku=?""", (store_id, sku)).fetchone()
    physical, reserved = int(row[0]), int(row[1])
    return {"fisico":physical,"reservado":reserved,"disponivel":physical-reserved}


def state(store_id: str, sku: str) -> dict[str, int]:
    with session() as db:
        return state_in(db, store_id, sku)


def balance_in(db, store_id: str, sku: str) -> int:
    return state_in(db, store_id, sku)["fisico"]


def available_in(db, store_id: str, sku: str) -> int:
    return state_in(db, store_id, sku)["disponivel"]


def balance(store_id: str, sku: str) -> int:
    return state(store_id, sku)["fisico"]


def add_in(db, store_id: str, sku: str, kind: str, delta: int, reference: str,
           reserved_delta: int = 0, reason: str = "") -> str:
    if not reference.strip():
        raise ValueError("Referência do movimento obrigatória.")
    before = state_in(db, store_id, sku)
    physical = before["fisico"] + delta
    reserved = before["reservado"] + reserved_delta
    if physical < 0:
        raise ValueError(f"Saldo físico insuficiente: {before['fisico']} unidade(s).")
    if reserved < 0:
        raise ValueError(f"Só há {before['reservado']} unidade(s) reservada(s).")
    if physical < reserved:
        raise ValueError(f"Saldo disponível insuficiente: {before['disponivel']} unidade(s).")
    identifier = uuid4().hex[:12].upper()
    db.execute("""INSERT INTO movements(id,store_id,sku,kind,delta,reserved_delta,
        reason,reference,created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        (identifier, store_id, sku, kind, delta, reserved_delta, reason.strip(), reference, now()))
    return identifier


def adjust(store_id: str, sku: str, target: int, reason: str = "Conferência") -> int:
    if isinstance(target, bool) or not isinstance(target, int) or target < 0:
        raise ValueError("Informe um saldo inteiro maior ou igual a zero.")
    if not reason.strip():
        raise ValueError("Informe o motivo da conferência.")
    with session() as db:
        current = balance_in(db, store_id, sku)
        add_in(db, store_id, sku, "Conferência", target-current,
               "count:"+uuid4().hex, reason=reason)
    return target


def manual(store_id: str, sku: str, action: str, quantity: int, reason: str) -> dict[str, int]:
    if action not in {"Entrada", "Saída", "Reservar", "Liberar reserva"}:
        raise ValueError("Escolha entrada, saída, reservar ou liberar reserva.")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("Informe quantidade inteira positiva.")
    if not reason.strip():
        raise ValueError("Informe o motivo da movimentação.")
    delta = quantity if action == "Entrada" else -quantity if action == "Saída" else 0
    reserved = quantity if action == "Reservar" else -quantity if action == "Liberar reserva" else 0
    with session() as db:
        add_in(db, store_id, sku, action, delta, "manual:"+uuid4().hex,
               reserved_delta=reserved, reason=reason)
        return state_in(db, store_id, sku)


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
        return [dict(row) for row in db.execute(query+" ORDER BY rowid DESC LIMIT 100", values)]
