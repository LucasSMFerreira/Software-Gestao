import csv
from contextlib import closing
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from gestao import backup, catalog, forecast
from gestao.database import initialize

class BackupTests(unittest.TestCase):
    def test_exporta_banco_consistente_e_csv_sem_substituir_copia(self):
        with tempfile.TemporaryDirectory() as folder:
            os.environ["GESTAO_DB_PATH"] = str(Path(folder)/"dados.sqlite3")
            try:
                initialize()
                catalog.save_product("Loja 1","A1","Caderno","Papelaria",5,7,2,1,1,opening_balance=5)
                forecast.record_sale("Loja 1","A1",2,unit_price="12,50")
                target = Path(folder)/"copia.zip"
                backup.export_data(target)
                with ZipFile(target) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertIn("gestao.sqlite3", archive.namelist())
                    with tempfile.TemporaryDirectory() as extracted:
                        path=Path(archive.extract("gestao.sqlite3", extracted))
                        with closing(sqlite3.connect(path)) as db:
                            self.assertEqual(db.execute("SELECT COUNT(*) FROM products").fetchone()[0],1)
                            self.assertEqual(db.execute("SELECT COUNT(*) FROM sales").fetchone()[0],1)
                    rows=list(csv.DictReader(archive.read("planilhas/products.csv").decode("utf-8-sig").splitlines()))
                    self.assertEqual(rows[0]["name"],"Caderno")
                with self.assertRaisesRegex(ValueError,"já existe"):
                    backup.export_data(target)
                self.assertTrue(target.exists())
            finally:
                os.environ.pop("GESTAO_DB_PATH",None)
