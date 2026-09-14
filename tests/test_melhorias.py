import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from gestao import catalog, forecast, inventory, replenishment
from gestao.database import initialize


class MelhoriasTestes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.environ["GESTAO_DB_PATH"] = str(Path(self.temp.name)/"teste.sqlite3")
        initialize()
        catalog.save_product("Loja 1", "SKU-1", "Mouse", "Fornecedor", 5, 7, 2, 1, 1,
            category="Periféricos", unit="un", sale_price="25,00",
            barcode="789123", opening_balance=10)

    def tearDown(self):
        os.environ.pop("GESTAO_DB_PATH", None)
        self.temp.cleanup()

    def test_novo_sku_nao_sobrescreve_e_codigo_barras_unico(self):
        with self.assertRaisesRegex(ValueError, "SKU já existe"):
            catalog.save_product("Loja 1", "SKU-1", "Outro", "Fornecedor", 5, 7, 2, 1, 1,
                allow_update=False, opening_balance=99)
        self.assertEqual(catalog.product("Loja 1", "SKU-1")["name"], "Mouse")
        self.assertEqual(inventory.balance("Loja 1", "SKU-1"), 10)
        with self.assertRaisesRegex(ValueError, "Código de barras"):
            catalog.save_product("Loja 1", "SKU-2", "Teclado", "Fornecedor", 5, 7, 2, 1, 1,
                barcode="789123", allow_update=False)

    def test_reserva_protege_estoque_e_exige_motivo(self):
        inventory.manual("Loja 1", "SKU-1", "Reservar", 4, "Pedido de cliente")
        self.assertEqual(inventory.state("Loja 1", "SKU-1"),
                         {"fisico":10,"reservado":4,"disponivel":6})
        with self.assertRaises(ValueError):
            forecast.record_sale("Loja 1", "SKU-1", 7)
        with self.assertRaisesRegex(ValueError, "motivo"):
            inventory.manual("Loja 1", "SKU-1", "Entrada", 1, "")
        with self.assertRaises(ValueError):
            inventory.adjust("Loja 1", "SKU-1", 3, "Contagem")
        forecast.record_sale("Loja 1", "SKU-1", 6)
        self.assertEqual(inventory.state("Loja 1", "SKU-1")["disponivel"], 0)
        inventory.manual("Loja 1", "SKU-1", "Liberar reserva", 4, "Cliente desistiu")
        self.assertEqual(inventory.state("Loja 1", "SKU-1")["disponivel"], 4)
        self.assertEqual(inventory.movements()[0]["reason"], "Cliente desistiu")

    def test_cancelamento_e_devolucao_corrigem_saldo_e_previsao(self):
        first = forecast.record_sale("Loja 1", "SKU-1", 4, date.today().isoformat(), "30,00")
        self.assertEqual(inventory.balance("Loja 1", "SKU-1"), 6)
        forecast.return_sale(first, 2)
        self.assertEqual(inventory.balance("Loja 1", "SKU-1"), 8)
        self.assertEqual(forecast.prediction("Loja 1", "SKU-1", 7)["quantidade_prevista"], 14)
        self.assertEqual(forecast.sales()[0]["net_cents"], 6000)
        with self.assertRaises(ValueError):
            forecast.return_sale(first, 3)
        with self.assertRaises(ValueError):
            forecast.cancel_sale(first)
        second = forecast.record_sale("Loja 1", "SKU-1", 3)
        self.assertTrue(forecast.cancel_sale(second))
        self.assertFalse(forecast.cancel_sale(second))
        self.assertEqual(inventory.balance("Loja 1", "SKU-1"), 8)
        self.assertEqual(forecast.prediction("Loja 1", "SKU-1", 7)["quantidade_prevista"], 14)

    def test_reposicao_usa_disponivel(self):
        inventory.manual("Loja 1", "SKU-1", "Reservar", 9, "Encomenda")
        sugestao = replenishment.suggestions()[0]
        self.assertEqual((sugestao["physical"], sugestao["reserved"], sugestao["stock"]),
                         (10, 9, 1))
        self.assertGreater(sugestao["quantity"], 0)
