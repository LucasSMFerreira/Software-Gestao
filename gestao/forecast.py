"""Vendas confirmadas e previsão inicial leve baseada no histórico recente."""
from datetime import date, timedelta
from math import ceil
from uuid import uuid4

from gestao.database import session
from gestao.inventory import add_in, balance_in, now


def record_sale(store_id: str, sku: str, quantity: int, sold_on: str | None = None) -> str:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("A venda precisa ter quantidade inteira positiva.")
    day = date.fromisoformat(sold_on) if sold_on else date.today()
    if day > date.today():
        raise ValueError("A venda não pode ter data futura.")
    identifier = uuid4().hex[:12].upper()
    with session() as db:
        balance_in(db, store_id, sku)
        db.execute("INSERT INTO sales VALUES (?,?,?,?,?,?)", (identifier, store_id, sku, quantity, day.isoformat(), now()))
        add_in(db, store_id, sku, "Venda", -quantity, "sale:"+identifier)
    return identifier


def daily_average_in(db, store_id: str, sku: str, today: date | None = None) -> float:
    today = today or date.today()
    start = today - timedelta(days=29)
    row = db.execute("SELECT MIN(sold_on),COALESCE(SUM(quantity),0) FROM sales WHERE store_id=? AND sku=? AND sold_on BETWEEN ? AND ?",
                     (store_id, sku, start.isoformat(), today.isoformat())).fetchone()
    if not row[0]:
        return 0.0
    days = max(1, (today-date.fromisoformat(row[0])).days+1)
    return row[1]/days


def prediction(store_id: str, sku: str, days: int = 7) -> dict:
    if not 1 <= days <= 90:
        raise ValueError("Escolha um horizonte de 1 a 90 dias.")
    with session() as db:
        balance_in(db, store_id, sku)
        daily = daily_average_in(db, store_id, sku)
    return {"media_diaria": daily, "dias": days, "quantidade_prevista": ceil(daily*days)}


def sales() -> list[dict]:
    with session() as db:
        return [dict(row) for row in db.execute("SELECT * FROM sales ORDER BY created_at DESC,id DESC LIMIT 100")]
