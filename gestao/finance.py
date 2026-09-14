"""Contas geradas pelas compras aprovadas e baixa de pagamentos."""
from datetime import date

from gestao.database import session


def payables() -> list[dict]:
    with session() as db:
        return [dict(row) for row in db.execute("""SELECT a.*,p.store_id,p.sku,p.supplier,p.status AS purchase_status
            FROM payables a JOIN purchases p ON p.id=a.purchase_id
            ORDER BY a.due_on,a.id""")]


def mark_paid(identifier: str, paid_on: str | None = None) -> bool:
    try:
        day = date.fromisoformat(paid_on) if paid_on else date.today()
    except ValueError as error:
        raise ValueError("Data de pagamento inválida.") from error
    with session() as db:
        payable = db.execute("SELECT paid_on FROM payables WHERE id=?", (identifier,)).fetchone()
        if not payable:
            raise ValueError("Conta não encontrada.")
        if payable["paid_on"]:
            return False
        db.execute("UPDATE payables SET paid_on=? WHERE id=?", (day.isoformat(), identifier))
    return True
