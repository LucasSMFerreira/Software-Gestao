"""Cadastro único de lojas e produtos, com saldo inicial no primeiro cadastro."""
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from gestao.database import session
from gestao.inventory import add_in


def price_cents(text: str) -> int:
    try:
        value = Decimal(str(text).strip().replace(",", "."))
    except InvalidOperation as error:
        raise ValueError("Preço de venda inválido.") from error
    if not value.is_finite() or value < 0 or value != value.quantize(Decimal("0.01")):
        raise ValueError("Informe preço de venda não negativo com até duas casas decimais.")
    return int(value*100)


def save_product(store_id: str, sku: str, name: str, supplier: str,
                 lead_days: int, review_days: int, safety: int,
                 minimum: int, multiple: int, *, category: str = "Geral",
                 unit: str = "un", sale_price: str = "0", opening_balance: int | None = None,
                 barcode: str = "", allow_update: bool = True) -> bool:
    store_id, sku, name, supplier, category, unit = (x.strip() for x in (store_id, sku, name, supplier, category, unit))
    if not all((store_id, sku, name, supplier, category, unit)):
        raise ValueError("Informe loja, SKU, produto, categoria, unidade e fornecedor.")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (lead_days, review_days, safety, minimum, multiple)):
        raise ValueError("Prazo, reserva e limites precisam ser números inteiros.")
    if min(lead_days, review_days, safety) < 0 or minimum < 1 or multiple < 1:
        raise ValueError("Prazo e reserva não podem ser negativos; mínimo e múltiplo devem ser positivos.")
    if opening_balance is not None and (isinstance(opening_balance, bool) or not isinstance(opening_balance, int) or opening_balance < 0):
        raise ValueError("Saldo inicial deve ser um inteiro maior ou igual a zero.")
    barcode = barcode.strip() or None
    if barcode and len(barcode) > 64:
        raise ValueError("Código de barras muito longo.")
    cents = price_cents(sale_price)
    with session() as db:
        db.execute("INSERT OR IGNORE INTO stores(id,name) VALUES (?,?)", (store_id, store_id))
        existed = bool(db.execute("SELECT 1 FROM products WHERE store_id=? AND sku=?", (store_id, sku)).fetchone())
        if existed and not allow_update:
            raise ValueError("Este SKU já existe nesta loja. Selecione o produto na lista para editar.")
        if barcode:
            other = db.execute("SELECT sku FROM products WHERE store_id=? AND barcode=?", (store_id, barcode)).fetchone()
            if other and other["sku"] != sku:
                raise ValueError("Código de barras já usado por outro produto nesta loja.")
        db.execute("""INSERT INTO products(store_id,sku,name,category,unit,sale_cents,barcode,supplier,
                    lead_days,review_days,safety,minimum,multiple)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(store_id,sku) DO UPDATE SET
                    name=excluded.name,category=excluded.category,unit=excluded.unit,
                    sale_cents=excluded.sale_cents,barcode=excluded.barcode,supplier=excluded.supplier,
                    lead_days=excluded.lead_days,review_days=excluded.review_days,
                    safety=excluded.safety,minimum=excluded.minimum,multiple=excluded.multiple""",
                   (store_id, sku, name, category, unit, cents, barcode, supplier,
                    lead_days, review_days, safety, minimum, multiple))
        if not existed and opening_balance is not None:
            add_in(db, store_id, sku, "Saldo inicial", opening_balance, "opening:"+uuid4().hex, reason="Cadastro do produto")
    return not existed


def products() -> list[dict]:
    with session() as db:
        return [dict(row) for row in db.execute("SELECT * FROM products ORDER BY store_id,sku")]


def product(store_id: str, sku: str) -> dict:
    with session() as db:
        row = db.execute("SELECT * FROM products WHERE store_id=? AND sku=?", (store_id, sku)).fetchone()
    if not row:
        raise ValueError("Produto não cadastrado nesta loja.")
    return dict(row)
