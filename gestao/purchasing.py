"""Pedido único: aprovação cria a despesa; recebimento dá entrada no estoque."""
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from gestao.database import session
from gestao.inventory import add_in, now


def cents(value: str) -> int:
    try:
        number = Decimal(value.strip().replace(",", "."))
    except (InvalidOperation, AttributeError) as error:
        raise ValueError("Preço inválido.") from error
    if not number.is_finite() or number <= 0 or number != number.quantize(Decimal("0.01")):
        raise ValueError("Informe preço positivo com até duas casas decimais.")
    return int(number*100)


def create_order(store_id: str, sku: str, quantity: int, unit_price: str, due_on: str) -> str:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("Quantidade precisa ser um inteiro positivo.")
    price = cents(unit_price)
    try:
        date.fromisoformat(due_on)
    except ValueError as error:
        raise ValueError("Vencimento deve estar em AAAA-MM-DD.") from error
    identifier = "PED-"+uuid4().hex[:12].upper()
    with session() as db:
        product = db.execute("SELECT supplier FROM products WHERE store_id=? AND sku=?", (store_id, sku)).fetchone()
        if not product:
            raise ValueError("Produto não cadastrado nesta loja.")
        db.execute("INSERT INTO purchases VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (identifier, store_id, sku, product["supplier"], quantity, price, due_on, "Rascunho", now(), None))
    return identifier


def approve_order(identifier: str) -> str:
    with session() as db:
        order = db.execute("SELECT * FROM purchases WHERE id=?", (identifier,)).fetchone()
        if not order:
            raise ValueError("Pedido não encontrado.")
        if order["status"] != "Rascunho":
            raise ValueError("Somente rascunhos podem ser aprovados.")
        payable_id = "CTA-"+uuid4().hex[:12].upper()
        db.execute("UPDATE purchases SET status='Aprovado' WHERE id=?", (identifier,))
        db.execute("INSERT INTO payables VALUES (?,?,?,?,?)",
                   (payable_id, identifier, order["quantity"]*order["unit_cents"], order["due_on"], None))
    return payable_id


def receive_order(identifier: str) -> bool:
    with session() as db:
        order = db.execute("SELECT * FROM purchases WHERE id=?", (identifier,)).fetchone()
        if not order:
            raise ValueError("Pedido não encontrado.")
        if order["status"] == "Recebido":
            return False
        if order["status"] != "Aprovado":
            raise ValueError("Aprove o pedido antes de registrar a entrega.")
        add_in(db, order["store_id"], order["sku"], "Compra", order["quantity"], "purchase:"+identifier)
        db.execute("UPDATE purchases SET status='Recebido',received_at=? WHERE id=?", (now(), identifier))
    return True


def orders() -> list[dict]:
    with session() as db:
        return [dict(row) for row in db.execute("""SELECT p.*,x.name AS product_name,
            (p.quantity*p.unit_cents) AS total_cents FROM purchases p
            JOIN products x ON x.store_id=p.store_id AND x.sku=p.sku
            ORDER BY p.created_at DESC,p.id DESC""")]
