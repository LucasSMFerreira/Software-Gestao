"""Vendas com preço, data, cancelamento e devoluções; previsão usa vendas líquidas."""
from datetime import date, timedelta
from math import ceil
from uuid import uuid4

from gestao.catalog import price_cents
from gestao.database import session
from gestao.inventory import add_in, state_in, now


def record_sale(store_id: str, sku: str, quantity: int, sold_on: str | None = None,
                unit_price: str | None = None) -> str:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("A venda precisa ter quantidade inteira positiva.")
    try:
        day = date.fromisoformat(sold_on) if sold_on else date.today()
    except ValueError as error:
        raise ValueError("Data da venda deve estar em AAAA-MM-DD.") from error
    if day > date.today():
        raise ValueError("A venda não pode ter data futura.")
    identifier = uuid4().hex[:12].upper()
    with session() as db:
        product = db.execute("SELECT sale_cents FROM products WHERE store_id=? AND sku=?", (store_id, sku)).fetchone()
        if not product:
            raise ValueError("Produto não cadastrado nesta loja.")
        price = price_cents(unit_price) if unit_price is not None else product["sale_cents"]
        if state_in(db, store_id, sku)["disponivel"] < quantity:
            raise ValueError("Venda maior que o estoque disponível.")
        db.execute("""INSERT INTO sales(id,store_id,sku,quantity,sold_on,unit_cents,status,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (identifier, store_id, sku, quantity, day.isoformat(), price, "Ativa", now()))
        add_in(db, store_id, sku, "Venda", -quantity, "sale:"+identifier,
               reason="Venda "+identifier)
    return identifier


def returned_in(db, sale_id: str) -> int:
    return int(db.execute("SELECT COALESCE(SUM(quantity),0) FROM sale_returns WHERE sale_id=?", (sale_id,)).fetchone()[0])


def return_sale(sale_id: str, quantity: int) -> str:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("Informe uma quantidade devolvida positiva.")
    with session() as db:
        sale = db.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
        if not sale:
            raise ValueError("Venda não encontrada.")
        if sale["status"] != "Ativa":
            raise ValueError("Venda cancelada não aceita devolução.")
        if returned_in(db, sale_id)+quantity > sale["quantity"]:
            raise ValueError("Devolução maior que a quantidade ainda vendida.")
        identifier = uuid4().hex[:12].upper()
        db.execute("INSERT INTO sale_returns VALUES (?,?,?,?)", (identifier, sale_id, quantity, now()))
        add_in(db, sale["store_id"], sale["sku"], "Devolução", quantity,
               "return:"+identifier, reason="Devolução da venda "+sale_id)
    return identifier


def cancel_sale(sale_id: str) -> bool:
    with session() as db:
        sale = db.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
        if not sale:
            raise ValueError("Venda não encontrada.")
        if sale["status"] == "Cancelada":
            return False
        if returned_in(db, sale_id):
            raise ValueError("Esta venda já teve devolução. Devolva o restante, se necessário.")
        add_in(db, sale["store_id"], sale["sku"], "Cancelamento", sale["quantity"],
               "cancel:"+sale_id, reason="Cancelamento da venda "+sale_id)
        db.execute("UPDATE sales SET status='Cancelada' WHERE id=?", (sale_id,))
    return True


def daily_average_in(db, store_id: str, sku: str, today: date | None = None) -> float:
    today = today or date.today()
    start = today-timedelta(days=29)
    row = db.execute("""SELECT MIN(s.sold_on), COALESCE(SUM(s.quantity-COALESCE(r.returned,0)),0)
        FROM sales s LEFT JOIN (
            SELECT sale_id,SUM(quantity) AS returned FROM sale_returns GROUP BY sale_id
        ) r ON r.sale_id=s.id
        WHERE s.store_id=? AND s.sku=? AND s.status='Ativa'
          AND s.sold_on BETWEEN ? AND ?""",
        (store_id, sku, start.isoformat(), today.isoformat())).fetchone()
    if not row[0]:
        return 0.0
    days = max(1,(today-date.fromisoformat(row[0])).days+1)
    return row[1]/days


def prediction(store_id: str, sku: str, days: int = 7) -> dict:
    if not 1 <= days <= 90:
        raise ValueError("Escolha um horizonte de 1 a 90 dias.")
    with session() as db:
        state_in(db, store_id, sku)
        daily = daily_average_in(db, store_id, sku)
    return {"media_diaria":daily,"dias":days,"quantidade_prevista":ceil(daily*days)}


def sales() -> list[dict]:
    with session() as db:
        return [dict(row) for row in db.execute("""SELECT s.*,
            COALESCE(r.returned,0) AS returned_quantity,
            (s.quantity-COALESCE(r.returned,0))*s.unit_cents AS net_cents
            FROM sales s LEFT JOIN (
                SELECT sale_id,SUM(quantity) AS returned FROM sale_returns GROUP BY sale_id
            ) r ON r.sale_id=s.id
            ORDER BY s.created_at DESC,s.id DESC LIMIT 100""")]
