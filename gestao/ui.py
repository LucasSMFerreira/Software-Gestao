"""Cinco telas simples sobre os mesmos serviços e o mesmo banco."""
import sqlite3
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk

from gestao import catalog, finance, forecast, inventory, purchasing, replenishment
from gestao.database import database_path


def brl(cents: int) -> str:
    return f"R$ {cents/100:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def iniciar() -> None:
    root = tk.Tk()
    root.title("Gestão Integrada")
    root.geometry("1120x760")
    root.minsize(970, 640)
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    ttk.Label(root, text="Gestão Integrada", font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=18, pady=(14, 2))
    summary = tk.StringVar()
    ttk.Label(root, textvariable=summary).pack(anchor="w", padx=18, pady=(0, 10))
    tabs = ttk.Notebook(root)
    tabs.pack(fill="both", expand=True, padx=18, pady=(0, 10))

    def tab(title):
        frame = ttk.Frame(tabs, padding=10)
        tabs.add(frame, text=title)
        return frame

    stock_tab = tab("1. Produtos e Estoque")
    sales_tab = tab("2. Vendas e Previsão")
    replen_tab = tab("3. Reposição")
    purchases_tab = tab("4. Compras")
    finance_tab = tab("5. Contas a Pagar")

    def table(parent, columns, height=10):
        tree = ttk.Treeview(parent, columns=[c[0] for c in columns], show="headings", height=height)
        for key, title, width in columns:
            tree.heading(key, text=title)
            tree.column(key, width=width)
        tree.pack(fill="both", expand=True, pady=(4, 10))
        return tree

    def field(parent, label, row, col, value="", width=18):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=5, pady=(5, 1))
        entry = ttk.Entry(parent, width=width)
        entry.grid(row=row+1, column=col, sticky="ew", padx=5, pady=(0, 6))
        if value:
            entry.insert(0, str(value))
        parent.columnconfigure(col, weight=1)
        return entry

    def run(action):
        try:
            result = action()
            refresh()
            if result:
                messagebox.showinfo("Concluído", result, parent=root)
        except (ValueError, sqlite3.Error, OSError) as error:
            messagebox.showerror("Não foi possível concluir", str(error), parent=root)

    # Cadastro e saldo
    ttk.Label(stock_tab, text="Cadastre um produto com saldo inicial em um passo. Clique numa linha para editar os dados ou conferir o saldo.").pack(anchor="w")
    product_tree = table(stock_tab, [("store", "Loja", 95), ("sku", "SKU", 115),
        ("name", "Produto", 170), ("category", "Categoria", 120),
        ("supplier", "Fornecedor", 150), ("price", "Preço venda", 100),
        ("stock", "Saldo", 70), ("rules", "Prazo / Reserva", 130)], 7)
    product_form = ttk.LabelFrame(stock_tab, text="Cadastro de produto")
    product_form.pack(fill="x")
    product_fields = {
        "store": field(product_form, "Loja", 0, 0, "Loja 1"),
        "sku": field(product_form, "Código (SKU)", 0, 1),
        "name": field(product_form, "Nome do produto", 0, 2),
        "category": field(product_form, "Categoria", 0, 3, "Geral"),
        "unit": field(product_form, "Unidade", 0, 4, "un"),
        "sale": field(product_form, "Preço de venda (R$)", 0, 5, "0,00"),
        "supplier": field(product_form, "Fornecedor", 2, 0),
        "lead": field(product_form, "Prazo (dias)", 2, 1, "5"),
        "review": field(product_form, "Revisão (dias)", 2, 2, "7"),
        "safety": field(product_form, "Reserva", 2, 3, "5"),
        "minimum": field(product_form, "Compra mínima", 2, 4, "1"),
        "multiple": field(product_form, "Múltiplo", 2, 5, "1"),
        "target": field(product_form, "Saldo inicial ou conferido", 4, 0, "0"),
    }

    def select_product(_event=None):
        selected = product_tree.selection()
        if not selected:
            return
        store, sku = selected[0].split("\x1f", 1)
        p = catalog.product(store, sku)
        values = {"store":store,"sku":sku,"name":p["name"],"category":p["category"],
                  "unit":p["unit"],"sale":f"{p['sale_cents']/100:.2f}","supplier":p["supplier"],
                  "lead":p["lead_days"],"review":p["review_days"],"safety":p["safety"],
                  "minimum":p["minimum"],"multiple":p["multiple"],"target":inventory.balance(store,sku)}
        for key, value in values.items():
            entry = product_fields[key]
            entry.delete(0,"end")
            entry.insert(0,str(value))

    product_tree.bind("<<TreeviewSelect>>", select_product)

    def save_product():
        f = product_fields
        created = catalog.save_product(
            f["store"].get(), f["sku"].get(), f["name"].get(), f["supplier"].get(),
            int(f["lead"].get()), int(f["review"].get()), int(f["safety"].get()),
            int(f["minimum"].get()), int(f["multiple"].get()),
            category=f["category"].get(), unit=f["unit"].get(),
            sale_price=f["sale"].get(), opening_balance=int(f["target"].get()))
        return "Produto cadastrado com saldo inicial e já aparece na lista." if created else "Produto atualizado. Para mudar o saldo, use 'Ajustar saldo'."

    def clear_product():
        product_tree.selection_remove(*product_tree.selection())
        defaults = {"store":"Loja 1","category":"Geral","unit":"un","sale":"0,00",
                    "lead":"5","review":"7","safety":"5","minimum":"1","multiple":"1","target":"0"}
        for key, entry in product_fields.items():
            entry.delete(0,"end")
            entry.insert(0,defaults.get(key,""))
        product_fields["sku"].focus_set()

    def adjust_stock():
        f = product_fields
        inventory.adjust(f["store"].get().strip(), f["sku"].get().strip(), int(f["target"].get()))
        return "Saldo atualizado com uma movimentação de conferência."

    product_actions = ttk.Frame(stock_tab)
    product_actions.pack(fill="x", pady=6)
    ttk.Button(product_actions, text="Novo produto", command=clear_product).pack(side="left", padx=4)
    ttk.Button(product_actions, text="Cadastrar / salvar produto", command=lambda:run(save_product)).pack(side="left", padx=4)
    ttk.Button(product_actions, text="Ajustar saldo", command=lambda:run(adjust_stock)).pack(side="left", padx=4)
    ttk.Label(stock_tab, text="Últimas movimentações").pack(anchor="w")
    movement_tree = table(stock_tab, [("at", "Data", 155), ("store", "Loja", 80), ("sku", "SKU", 120), ("kind", "Motivo", 120), ("delta", "Variação", 80), ("ref", "Referência", 260)], 5)

    # Vendas e previsão
    ttk.Label(sales_tab, text="A venda confirmada baixa o saldo. A previsão inicial usa a média diária dos últimos 30 dias.").pack(anchor="w")
    sale_form = ttk.LabelFrame(sales_tab, text="Registrar venda")
    sale_form.pack(fill="x", pady=8)
    ttk.Label(sale_form, text="Produto").grid(row=0,column=0,sticky="w",padx=5)
    sale_product = ttk.Combobox(sale_form, state="readonly", width=45)
    sale_product.grid(row=1,column=0,sticky="ew",padx=5,pady=6)
    sale_quantity = field(sale_form, "Quantidade vendida", 0, 1, "1")
    sale_form.columnconfigure(0,weight=3)
    forecast_text = tk.StringVar(value="Cadastre um produto para começar.")

    def selected_sale_product():
        value = sale_product.get()
        if not value:
            raise ValueError("Escolha um produto.")
        return value.split(" | ",2)[:2]

    def save_sale():
        store, sku = selected_sale_product()
        forecast.record_sale(store,sku,int(sale_quantity.get()))
        return "Venda registrada e estoque baixado uma única vez."

    def show_prediction():
        store,sku = selected_sale_product()
        result = forecast.prediction(store,sku,7)
        forecast_text.set(f"Média recente: {result['media_diaria']:.2f}/dia  •  Próximos 7 dias: cerca de {result['quantidade_prevista']} unidade(s). Estimativa simples; confira antes de comprar.")

    sale_actions = ttk.Frame(sales_tab)
    sale_actions.pack(fill="x", pady=6)
    ttk.Button(sale_actions,text="Registrar venda",command=lambda:run(save_sale)).pack(side="left",padx=4)
    ttk.Button(sale_actions,text="Calcular previsão",command=lambda:run(show_prediction)).pack(side="left",padx=4)
    ttk.Label(sales_tab,textvariable=forecast_text,wraplength=1000).pack(anchor="w",pady=8)
    ttk.Label(sales_tab,text="Vendas recentes").pack(anchor="w")
    sales_tree = table(sales_tab, [("day","Data",120),("store","Loja",120),("sku","SKU",150),("qty","Quantidade",100),("id","Registro",170)], 14)

    # Reposição
    ttk.Label(replen_tab,text="Uma sugestão por produto. Pedidos aprovados já contam como 'a receber', evitando sugerir outra compra igual.").pack(anchor="w")
    suggestion_tree = table(replen_tab,[("store","Loja",100),("sku","SKU",140),("name","Produto",190),("stock","Saldo",75),("pending","A receber",90),("point","Ponto",75),("qty","Comprar",90),("supplier","Fornecedor",150)],14)
    order_form = ttk.LabelFrame(replen_tab,text="Criar pedido a partir da sugestão selecionada")
    order_form.pack(fill="x")
    order_quantity = field(order_form,"Quantidade",0,0)
    order_price = field(order_form,"Preço por unidade (R$)",0,1)
    order_due = field(order_form,"Vencimento AAAA-MM-DD",0,2,(date.today()+timedelta(days=30)).isoformat())

    def select_suggestion(_event=None):
        choice = suggestion_tree.selection()
        if choice:
            row = suggestion_tree.item(choice[0])["values"]
            order_quantity.delete(0,"end")
            order_quantity.insert(0,str(row[6]))

    suggestion_tree.bind("<<TreeviewSelect>>",select_suggestion)

    def create_from_suggestion():
        choice = suggestion_tree.selection()
        if not choice:
            raise ValueError("Selecione uma sugestão.")
        store,sku = choice[0].split("\x1f",1)
        quantity = int(order_quantity.get())
        if quantity <= 0:
            raise ValueError("Informe uma quantidade positiva.")
        identifier = purchasing.create_order(store,sku,quantity,order_price.get(),order_due.get())
        return f"Pedido {identifier} criado como rascunho. Confira e aprove na aba Compras."

    ttk.Button(replen_tab,text="Criar pedido",command=lambda:run(create_from_suggestion)).pack(anchor="w",pady=8)

    # Compras
    ttk.Label(purchases_tab,text="Aprovar cria a conta a pagar. Receber registra a entrada no estoque. Cada pedido é processado uma vez.").pack(anchor="w")
    order_tree = table(purchases_tab,[("id","Pedido",160),("store","Loja",90),("sku","SKU",120),("name","Produto",160),("supplier","Fornecedor",140),("qty","Qtd.",60),("total","Total",100),("status","Status",90)],18)

    def selected_order():
        choice = order_tree.selection()
        if not choice:
            raise ValueError("Selecione um pedido.")
        return choice[0]

    def approve():
        identifier = selected_order()
        if not messagebox.askyesno("Confirmar compra",f"Aprovar {identifier} e criar a conta a pagar?",parent=root):
            return ""
        account = purchasing.approve_order(identifier)
        return f"Pedido aprovado. Conta {account} criada."

    def receive():
        identifier = selected_order()
        if not messagebox.askyesno("Confirmar entrega",f"A mercadoria do pedido {identifier} chegou?",parent=root):
            return ""
        return "Entrega registrada e saldo atualizado." if purchasing.receive_order(identifier) else "Pedido já recebido; saldo não foi somado novamente."

    order_actions = ttk.Frame(purchases_tab)
    order_actions.pack(fill="x")
    ttk.Button(order_actions,text="Aprovar e criar conta",command=lambda:run(approve)).pack(side="left",padx=4)
    ttk.Button(order_actions,text="Marcar recebido",command=lambda:run(receive)).pack(side="left",padx=4)

    # Financeiro
    ttk.Label(finance_tab,text="As contas são criadas automaticamente quando uma compra é aprovada. Registre o pagamento aqui.").pack(anchor="w")
    payable_tree = table(finance_tab,[("id","Conta",150),("purchase","Pedido",160),("supplier","Fornecedor",150),("amount","Valor",110),("due","Vencimento",110),("status","Situação",140)],18)

    def mark_paid():
        choice = payable_tree.selection()
        if not choice:
            raise ValueError("Selecione uma conta.")
        identifier = choice[0]
        if not messagebox.askyesno("Confirmar pagamento",f"Marcar a conta {identifier} como paga?",parent=root):
            return ""
        return "Pagamento registrado." if finance.mark_paid(identifier) else "Esta conta já estava paga."

    ttk.Button(finance_tab,text="Marcar como paga",command=lambda:run(mark_paid)).pack(anchor="w")

    def replace(tree, rows):
        tree.delete(*tree.get_children())
        for identifier, values in rows:
            tree.insert("","end",iid=identifier,values=values)

    def refresh():
        all_products = catalog.products()
        product_rows = []
        for p in all_products:
            store,sku = p["store_id"],p["sku"]
            product_rows.append((store+"\x1f"+sku,(store,sku,p["name"],p["category"],p["supplier"],brl(p["sale_cents"]),inventory.balance(store,sku),f"{p['lead_days']} dias / {p['safety']} un.")))
        replace(product_tree,product_rows)
        sale_product["values"] = [f"{p['store_id']} | {p['sku']} | {p['name']}" for p in all_products]
        if sale_product.get() not in sale_product["values"]:
            sale_product.set("")
        replace(movement_tree,[(m["id"],(m["created_at"][:19].replace("T"," "),m["store_id"],m["sku"],m["kind"],f"{m['delta']:+}",m["reference"])) for m in inventory.movements()])
        replace(sales_tree,[(s["id"],(s["sold_on"],s["store_id"],s["sku"],s["quantity"],s["id"])) for s in forecast.sales()])
        suggestions = replenishment.suggestions()
        replace(suggestion_tree,[(s["store_id"]+"\x1f"+s["sku"],(s["store_id"],s["sku"],s["name"],s["stock"],s["pending"],s["point"],s["quantity"],s["supplier"])) for s in suggestions])
        all_orders = purchasing.orders()
        replace(order_tree,[(o["id"],(o["id"],o["store_id"],o["sku"],o["product_name"],o["supplier"],o["quantity"],brl(o["total_cents"]),o["status"])) for o in all_orders])
        all_accounts = finance.payables()
        today = date.today().isoformat()
        replace(payable_tree,[(a["id"],(a["id"],a["purchase_id"],a["supplier"],brl(a["amount_cents"]),a["due_on"],"Paga" if a["paid_on"] else "Vencida" if a["due_on"]<today else "Em aberto")) for a in all_accounts])
        summary.set(f"{len(all_products)} produto(s)  •  {sum(1 for s in suggestions if s['quantity']>0)} sugestão(ões) de compra  •  {sum(1 for a in all_accounts if not a['paid_on'])} conta(s) em aberto")

    ttk.Label(root,text=f"Dados locais: {database_path()}  •  Faça cópia deste arquivo para guardar seus registros.",wraplength=1080).pack(anchor="w",padx=18,pady=(0,10))
    refresh()
    root.mainloop()
