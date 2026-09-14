import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gestao import catalog, inventory
from gestao.database import initialize


class CadastroTestes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.environ["GESTAO_DB_PATH"] = str(Path(self.temp.name)/"cadastro.sqlite3")
        initialize()

    def tearDown(self):
        os.environ.pop("GESTAO_DB_PATH", None)
        self.temp.cleanup()

    def test_cadastro_completo_cria_saldo_inicial_uma_vez(self):
        criado = catalog.save_product("Loja 1", "SKU-1", "Mouse", "Fornecedor A",
            5, 7, 3, 1, 1, category="Periféricos", unit="un", sale_price="29,90", opening_balance=8)
        self.assertTrue(criado)
        self.assertEqual(inventory.balance("Loja 1", "SKU-1"), 8)
        produto = catalog.product("Loja 1", "SKU-1")
        self.assertEqual((produto["category"], produto["unit"], produto["sale_cents"]),
                         ("Periféricos", "un", 2990))
        criado = catalog.save_product("Loja 1", "SKU-1", "Mouse sem fio", "Fornecedor B",
            5, 7, 3, 1, 1, category="Periféricos", unit="un", sale_price="32.00", opening_balance=99)
        self.assertFalse(criado)
        self.assertEqual(inventory.balance("Loja 1", "SKU-1"), 8)
        self.assertEqual(len(inventory.movements()), 1)

    def test_banco_anterior_recebe_campos_novos(self):
        path = Path(os.environ["GESTAO_DB_PATH"])
        db = sqlite3.connect(path)
        try:
            db.execute("DROP TABLE products")
            db.execute("""CREATE TABLE products (store_id TEXT NOT NULL, sku TEXT NOT NULL,
                name TEXT NOT NULL, supplier TEXT NOT NULL, lead_days INTEGER NOT NULL,
                review_days INTEGER NOT NULL, safety INTEGER NOT NULL, minimum INTEGER NOT NULL,
                multiple INTEGER NOT NULL, PRIMARY KEY(store_id,sku))""")
            db.commit()
        finally:
            db.close()
        initialize()
        db = sqlite3.connect(path)
        try:
            columns = {row[1] for row in db.execute("PRAGMA table_info(products)")}
        finally:
            db.close()
        self.assertTrue({"category", "unit", "sale_cents"}.issubset(columns))
