"""Uma única regra operacional para sugerir compras."""
from math import ceil

from gestao.database import session
from gestao.forecast import daily_average_in
from gestao.inventory import state_in


def suggestions() -> list[dict]:
    result = []
    with session() as db:
        for p in db.execute("SELECT * FROM products ORDER BY store_id,sku").fetchall():
            store, sku = p["store_id"], p["sku"]
            stock_state = state_in(db, store, sku)
            stock = stock_state["disponivel"]
            daily = daily_average_in(db, store, sku)
            pending = int(db.execute("SELECT COALESCE(SUM(quantity),0) FROM purchases WHERE store_id=? AND sku=? AND status='Aprovado'", (store, sku)).fetchone()[0])
            available = stock + pending
            point = ceil(daily*p["lead_days"] + p["safety"])
            target = ceil(daily*(p["lead_days"]+p["review_days"]) + p["safety"])
            needed = max(0, target-available) if available <= point else 0
            quantity = 0
            if needed:
                minimum = max(needed, p["minimum"])
                quantity = ceil(minimum/p["multiple"])*p["multiple"]
            result.append({"store_id":store,"sku":sku,"name":p["name"],"supplier":p["supplier"],
                           "stock":stock,"physical":stock_state["fisico"],"reserved":stock_state["reservado"],"pending":pending,"daily":daily,"point":point,"quantity":quantity})
    return result
