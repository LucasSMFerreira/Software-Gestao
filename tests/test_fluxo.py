import os
import tempfile
import unittest
from pathlib import Path

from gestao import catalog, finance, forecast, inventory, purchasing, replenishment
from gestao.database import initialize


class FluxoIntegradoTestes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.environ["GESTAO_DB_PATH"] = str(Path(self.temp.name)/"teste.sqlite3")
        initialize()
        catalog.save_product("Loja 1","SKU-1","Mouse","Fornecedor A",5,7,3,1,1)
        inventory.adjust("Loja 1","SKU-1",10)

    def tearDown(self):
        os.environ.pop("GESTAO_DB_PATH",None)
        self.temp.cleanup()

    def test_venda_baixa_estoque_e_alimenta_previsao(self):
        forecast.record_sale("Loja 1","SKU-1",4)
        self.assertEqual(inventory.balance("Loja 1","SKU-1"),6)
        self.assertEqual(forecast.prediction("Loja 1","SKU-1",7)["quantidade_prevista"],28)
        with self.assertRaises(ValueError):
            forecast.record_sale("Loja 1","SKU-1",7)
        self.assertEqual(len(forecast.sales()),1)

    def test_pedido_cria_conta_e_recebimento_unico(self):
        pedido = purchasing.create_order("Loja 1","SKU-1",5,"12,50","2026-10-15")
        self.assertEqual(len(finance.payables()),0)
        conta = purchasing.approve_order(pedido)
        self.assertEqual(finance.payables()[0]["id"],conta)
        self.assertEqual(finance.payables()[0]["amount_cents"],6250)
        self.assertTrue(purchasing.receive_order(pedido))
        self.assertFalse(purchasing.receive_order(pedido))
        self.assertEqual(inventory.balance("Loja 1","SKU-1"),15)
        self.assertEqual(len([m for m in inventory.movements() if m["kind"]=="Compra"]),1)
        self.assertTrue(finance.mark_paid(conta))
        self.assertFalse(finance.mark_paid(conta))

    def test_reposicao_considera_pedidos_pendentes(self):
        inventory.adjust("Loja 1","SKU-1",1)
        self.assertGreater(replenishment.suggestions()[0]["quantity"],0)
        pedido = purchasing.create_order("Loja 1","SKU-1",5,"10.00","2026-10-15")
        purchasing.approve_order(pedido)
        sugestao = replenishment.suggestions()[0]
        self.assertEqual(sugestao["pending"],5)
        self.assertEqual(sugestao["quantity"],0)

    def test_estoque_separado_por_loja(self):
        catalog.save_product("Loja 2","SKU-1","Mouse","Fornecedor A",5,7,3,1,1)
        inventory.adjust("Loja 2","SKU-1",2)
        self.assertEqual(inventory.balance("Loja 1","SKU-1"),10)
        self.assertEqual(inventory.balance("Loja 2","SKU-1"),2)


if __name__ == "__main__":
    unittest.main()
