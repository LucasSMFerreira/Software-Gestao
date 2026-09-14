"""SQLite local: uma fonte para produtos, movimentos, compras e contas."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def database_path() -> Path:
    override = os.environ.get("GESTAO_DB_PATH")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return base / "GestaoIntegrada" / "gestao.sqlite3"


@contextmanager
def session():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize() -> None:
    with session() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS stores (
            id TEXT PRIMARY KEY, name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS products (
            store_id TEXT NOT NULL REFERENCES stores(id), sku TEXT NOT NULL,
            name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Geral',
            unit TEXT NOT NULL DEFAULT 'un', sale_cents INTEGER NOT NULL DEFAULT 0,
            barcode TEXT,
            supplier TEXT NOT NULL,
            lead_days INTEGER NOT NULL CHECK(lead_days >= 0),
            review_days INTEGER NOT NULL CHECK(review_days >= 0),
            safety INTEGER NOT NULL CHECK(safety >= 0),
            minimum INTEGER NOT NULL CHECK(minimum >= 1),
            multiple INTEGER NOT NULL CHECK(multiple >= 1),
            PRIMARY KEY(store_id, sku)
        );
        CREATE TABLE IF NOT EXISTS movements (
            id TEXT PRIMARY KEY, store_id TEXT NOT NULL, sku TEXT NOT NULL,
            kind TEXT NOT NULL, delta INTEGER NOT NULL,
            reserved_delta INTEGER NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT '',
            reference TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
            FOREIGN KEY(store_id, sku) REFERENCES products(store_id, sku)
        );
        CREATE TABLE IF NOT EXISTS sales (
            id TEXT PRIMARY KEY, store_id TEXT NOT NULL, sku TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0), sold_on TEXT NOT NULL,
            unit_cents INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'Ativa',
            created_at TEXT NOT NULL,
            FOREIGN KEY(store_id, sku) REFERENCES products(store_id, sku)
        );
        CREATE TABLE IF NOT EXISTS sale_returns (
            id TEXT PRIMARY KEY, sale_id TEXT NOT NULL REFERENCES sales(id),
            quantity INTEGER NOT NULL CHECK(quantity > 0), created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS purchases (
            id TEXT PRIMARY KEY, store_id TEXT NOT NULL, sku TEXT NOT NULL,
            supplier TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_cents INTEGER NOT NULL CHECK(unit_cents > 0), due_on TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Rascunho','Aprovado','Recebido')),
            created_at TEXT NOT NULL, received_at TEXT,
            FOREIGN KEY(store_id, sku) REFERENCES products(store_id, sku)
        );
        CREATE TABLE IF NOT EXISTS payables (
            id TEXT PRIMARY KEY, purchase_id TEXT NOT NULL UNIQUE REFERENCES purchases(id),
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0), due_on TEXT NOT NULL,
            paid_on TEXT
        );
        """)
        columns = {row[1] for row in db.execute("PRAGMA table_info(products)")}
        for name, declaration in (
            ("category", "TEXT NOT NULL DEFAULT 'Geral'"),
            ("unit", "TEXT NOT NULL DEFAULT 'un'"),
            ("sale_cents", "INTEGER NOT NULL DEFAULT 0"),
            ("barcode", "TEXT"),
        ):
            if name not in columns:
                db.execute(f"ALTER TABLE products ADD COLUMN {name} {declaration}")

        for table, fields in (
            ("movements", (("reserved_delta", "INTEGER NOT NULL DEFAULT 0"),
                           ("reason", "TEXT NOT NULL DEFAULT ''"))),
            ("sales", (("unit_cents", "INTEGER NOT NULL DEFAULT 0"),
                       ("status", "TEXT NOT NULL DEFAULT 'Ativa'"))),
        ):
            existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
            for name, declaration in fields:
                if name not in existing:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_products_barcode ON products(store_id,barcode) WHERE barcode IS NOT NULL")
