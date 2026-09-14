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
    ttk.Label(stock_tab, text="Busque um produto ou clique em Novo produto. Entradas, saídas e reservas exigem motivo.").pack(anchor="w")
    search_bar = ttk.Frame(stock_tab)
    search_bar.pack(fill="x", pady=4)
    ttk.Label(search_bar,text="Buscar por nome, SKU ou código de barras:").pack(side="left")
    product_search = tk.StringVar()
    ttk.Entry(search_bar,textvariable=product_search,width=36).pack(side="left",padx=6)
    product_tree = table(stock_tab,[("store","Loja",75),("sku","SKU",95),("name","Produto",135),
        ("category","Categoria",90),("barcode","Cód. barras",120),("supplier","Fornecedor",120),
        ("price","Preço",80),("physical","Físico",60),("reserved","Reservado",70),
        ("available","Disponível",75),("rules","Prazo / Reserva",110)],6)
    product_form = ttk.LabelFrame(stock_tab,text="Cadastro de produto")
    product_form.pack(fill="x")
    product_fields = {
        "store":field(product_form,"Loja",0,0,"Loja 1"),
        "sku":field(product_form,"Código (SKU)",0,1),
        "name":field(product_form,"Nome do produto",0,2),
        "category":field(product_form,"Categoria",0,3,"Geral"),
        "unit":field(product_form,"Unidade",0,4,"un"),
        "sale":field(product_form,"Preço de venda (R$)",0,5,"0,00"),
        "barcode":field(product_form,"Código de barras",0,6),
        "supplier":field(product_form,"Fornecedor",2,0),
        "lead":field(product_form,"Prazo (dias)",2,1,"5"),
        "review":field(product_form,"Revisão (dias)",2,2,"7"),
        "safety":field(product_form,"Reserva mínima",2,3,"5"),
        "minimum":field(product_form,"Compra mínima",2,4,"1"),
        "multiple":field(product_form,"Múltiplo",2,5,"1"),
        "target":field(product_form,"Saldo inicial",2,6,"0"),
    }
    selected_product_key = None

    def select_product(_event=None):
        nonlocal selected_product_key
        selected = product_tree.selection()
        if not selected:
            return
        store,sku = selected[0].split("\x1f",1)
        selected_product_key = (store,sku)
        product = catalog.product(store,sku)
        values = {"store":store,"sku":sku,"name":product["name"],
            "category":product["category"],"unit":product["unit"],
            "sale":f"{product['sale_cents']/100:.2f}","barcode":product["barcode"] or "",
            "supplier":product["supplier"],"lead":product["lead_days"],
            "review":product["review_days"],"safety":product["safety"],
            "minimum":product["minimum"],"multiple":product["multiple"],
            "target":inventory.balance(store,sku)}
        for key,value in values.items():
            entry = product_fields[key]
            entry.delete(0,"end")
            entry.insert(0,str(value))

    product_tree.bind("<<TreeviewSelect>>",select_product)

    def clear_product():
        nonlocal selected_product_key
        selected_product_key = None
        product_tree.selection_remove(*product_tree.selection())
        defaults = {"store":"Loja 1","category":"Geral","unit":"un","sale":"0,00",
            "lead":"5","review":"7","safety":"5","minimum":"1","multiple":"1","target":"0"}
        for key,entry in product_fields.items():
            entry.delete(0,"end")
            entry.insert(0,defaults.get(key,""))
        product_fields["sku"].focus_set()

    def save_product():
        f = product_fields
        store,sku = f["store"].get().strip(),f["sku"].get().strip()
        if selected_product_key and selected_product_key != (store,sku):
            raise ValueError("Loja e SKU não podem mudar durante a edição. Use Novo produto.")
        created = catalog.save_product(store,sku,f["name"].get(),f["supplier"].get(),
            int(f["lead"].get()),int(f["review"].get()),int(f["safety"].get()),
            int(f["minimum"].get()),int(f["multiple"].get()),
            category=f["category"].get(),unit=f["unit"].get(),sale_price=f["sale"].get(),
            barcode=f["barcode"].get(),opening_balance=int(f["target"].get()),
            allow_update=selected_product_key is not None)
        return "Produto cadastrado com saldo inicial." if created else "Cadastro atualizado. O saldo não foi alterado."

    actions = ttk.Frame(stock_tab)
    actions.pack(fill="x",pady=5)
    ttk.Button(actions,text="Novo produto",command=clear_product).pack(side="left",padx=4)
    ttk.Button(actions,text="Cadastrar / salvar",command=lambda:run(save_product)).pack(side="left",padx=4)

    movement_form = ttk.LabelFrame(stock_tab,text="Movimentação manual do produto informado acima")
    movement_form.pack(fill="x",pady=4)
    ttk.Label(movement_form,text="Operação").grid(row=0,column=0,sticky="w",padx=5)
    movement_kind = ttk.Combobox(movement_form,state="readonly",values=("Entrada","Saída","Reservar","Liberar reserva","Conferência"),width=20)
    movement_kind.grid(row=1,column=0,sticky="ew",padx=5,pady=5)
    movement_kind.set("Entrada")
    movement_quantity = field(movement_form,"Quantidade (na conferência: saldo contado)",0,1,"1")
    movement_reason = field(movement_form,"Motivo obrigatório",0,2,width=32)
    movement_form.columnconfigure(2,weight=2)

    def register_movement():
        store,sku = product_fields["store"].get().strip(),product_fields["sku"].get().strip()
        quantity = int(movement_quantity.get())
        reason = movement_reason.get().strip()
        if movement_kind.get() == "Conferência":
            inventory.adjust(store,sku,quantity,reason)
        else:
            inventory.manual(store,sku,movement_kind.get(),quantity,reason)
        return "Movimentação registrada. O saldo e o histórico foram atualizados."

    ttk.Button(movement_form,text="Registrar movimentação",command=lambda:run(register_movement)).grid(row=1,column=3,padx=5,pady=5)
    ttk.Label(stock_tab,text="Últimas movimentações").pack(anchor="w")
    movement_tree = table(stock_tab,[("at","Data",145),("store","Loja",70),("sku","SKU",100),
        ("kind","Tipo",100),("delta","Físico +/-",80),("reserved","Reserva +/-",85),
        ("reason","Motivo",220),("ref","Referência",200)],4)
    # Vendas e previsão
    ttk.Label(sales_tab,text="A venda baixa o disponível. Cancelamentos e devoluções devolvem unidades ao estoque e corrigem a previsão.").pack(anchor="w")
    sale_form = ttk.LabelFrame(sales_tab,text="Registrar venda")
    sale_form.pack(fill="x",pady=8)
    ttk.Label(sale_form,text="Produto").grid(row=0,column=0,sticky="w",padx=5)
    sale_product = ttk.Combobox(sale_form,state="readonly",width=42)
    sale_product.grid(row=1,column=0,sticky="ew",padx=5,pady=6)
    sale_quantity = field(sale_form,"Quantidade vendida",0,1,"1")
    sale_price = field(sale_form,"Preço por unidade (R$)",0,2,"0,00")
    sale_date = field(sale_form,"Data AAAA-MM-DD",0,3,date.today().isoformat())
    sale_form.columnconfigure(0,weight=3)
    forecast_text = tk.StringVar(value="Cadastre um produto para começar.")

    def selected_sale_product():
        value = sale_product.get()
        if not value:
            raise ValueError("Escolha um produto.")
        return value.split(" | ",2)[:2]

    def fill_sale_price(_event=None):
        store,sku = selected_sale_product()
        price = catalog.product(store,sku)["sale_cents"]/100
        sale_price.delete(0,"end")
        sale_price.insert(0,f"{price:.2f}")

    sale_product.bind("<<ComboboxSelected>>",fill_sale_price)

    def save_sale():
        store,sku = selected_sale_product()
        sale_id = forecast.record_sale(store,sku,int(sale_quantity.get()),
            sold_on=sale_date.get().strip(),unit_price=sale_price.get().strip())
        return f"Venda {sale_id} registrada; estoque baixado."

    def show_prediction():
        store,sku = selected_sale_product()
        result = forecast.prediction(store,sku,7)
        forecast_text.set(f"Média líquida recente: {result['media_diaria']:.2f}/dia  •  Próximos 7 dias: cerca de {result['quantidade_prevista']} unidade(s). Estimativa simples; confira antes de comprar.")

    sale_actions = ttk.Frame(sales_tab)
    sale_actions.pack(fill="x",pady=6)
    ttk.Button(sale_actions,text="Registrar venda",command=lambda:run(save_sale)).pack(side="left",padx=4)
    ttk.Button(sale_actions,text="Calcular previsão",command=lambda:run(show_prediction)).pack(side="left",padx=4)
    ttk.Label(sales_tab,textvariable=forecast_text,wraplength=1000).pack(anchor="w",pady=8)
    ttk.Label(sales_tab,text="Vendas recentes: selecione uma linha para cancelar ou devolver unidades").pack(anchor="w")
    sales_tree = table(sales_tab,[("day","Data",100),("store","Loja",85),("sku","SKU",110),
        ("qty","Vendidas",75),("returned","Devolvidas",85),("unit","Preço/un.",90),
        ("net","Valor líquido",100),("status","Situação",90),("id","Registro",140)],12)

    def selected_sale():
        choice = sales_tree.selection()
        if not choice:
            raise ValueError("Selecione uma venda na lista.")
        return choice[0]

    def cancel_selected_sale():
        identifier = selected_sale()
        if not messagebox.askyesno("Cancelar venda",f"Cancelar a venda {identifier} e devolver todas as unidades ao estoque?",parent=root):
            return ""
        return "Venda cancelada e estoque corrigido." if forecast.cancel_sale(identifier) else "Venda já cancelada."

    def return_selected_sale():
        identifier = selected_sale()
        quantity = int(return_quantity.get())
        if not messagebox.askyesno("Registrar devolução",f"Devolver {quantity} unidade(s) da venda {identifier} ao estoque?",parent=root):
            return ""
        forecast.return_sale(identifier,quantity)
        return "Devolução registrada e estoque corrigido."

    return_actions = ttk.Frame(sales_tab)
    return_actions.pack(fill="x")
    ttk.Label(return_actions,text="Qtd. devolvida:").pack(side="left",padx=4)
    return_quantity = ttk.Entry(return_actions,width=8)
    return_quantity.insert(0,"1")
    return_quantity.pack(side="left",padx=4)
    ttk.Button(return_actions,text="Registrar devolução",command=lambda:run(return_selected_sale)).pack(side="left",padx=4)
    ttk.Button(return_actions,text="Cancelar venda",command=lambda:run(cancel_selected_sale)).pack(side="left",padx=4)

    # Reposição
    ttk.Label(replen_tab,text="Uma sugestão por produto. Pedidos aprovados já contam como 'a receber', evitando sugerir outra compra igual.").pack(anchor="w")
    suggestion_tree = table(replen_tab,[("store","Loja",100),("sku","SKU",140),("name","Produto",190),("stock","Disponível",85),("reserved","Reservado",85),("pending","A receber",90),("point","Ponto",75),("qty","Comprar",90),("supplier","Fornecedor",150)],14)
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
            order_quantity.insert(0,str(row[7]))

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
        term = product_search.get().strip().casefold()
        product_rows = []
        for p in all_products:
            store,sku = p["store_id"],p["sku"]
            if term and term not in (store+" "+sku+" "+p["name"]+" "+(p["barcode"] or "")).casefold():
                continue
            stock = inventory.state(store,sku)
            product_rows.append((store+"\x1f"+sku,(store,sku,p["name"],p["category"],
                p["barcode"] or "—",p["supplier"],brl(p["sale_cents"]),
                stock["fisico"],stock["reservado"],stock["disponivel"],
                f"{p['lead_days']} d / {p['safety']} un.")))
        replace(product_tree,product_rows)
        sale_product["values"] = [f"{p['store_id']} | {p['sku']} | {p['name']}" for p in all_products]
        if sale_product.get() not in sale_product["values"]:
            sale_product.set("")
        replace(movement_tree,[(m["id"],(m["created_at"][:19].replace("T"," "),
            m["store_id"],m["sku"],m["kind"],f"{m['delta']:+}",
            f"{m['reserved_delta']:+}",m["reason"] or "—",m["reference"]))
            for m in inventory.movements()])
        replace(sales_tree,[(s["id"],(s["sold_on"],s["store_id"],s["sku"],
            s["quantity"],s["returned_quantity"],brl(s["unit_cents"]),
            brl(s["net_cents"]),s["status"],s["id"])) for s in forecast.sales()])
        suggestions = replenishment.suggestions()
        replace(suggestion_tree,[(s["store_id"]+"\x1f"+s["sku"],
            (s["store_id"],s["sku"],s["name"],s["stock"],s["reserved"],
             s["pending"],s["point"],s["quantity"],s["supplier"])) for s in suggestions])
        all_orders = purchasing.orders()
        replace(order_tree,[(o["id"],(o["id"],o["store_id"],o["sku"],o["product_name"],
            o["supplier"],o["quantity"],brl(o["total_cents"]),o["status"])) for o in all_orders])
        all_accounts = finance.payables()
        today = date.today().isoformat()
        replace(payable_tree,[(a["id"],(a["id"],a["purchase_id"],a["supplier"],
            brl(a["amount_cents"]),a["due_on"],"Paga" if a["paid_on"] else
            "Vencida" if a["due_on"]<today else "Em aberto")) for a in all_accounts])
        summary.set(f"{len(all_products)} produto(s)  •  {sum(1 for s in suggestions if s['quantity']>0)} sugestão(ões) de compra  •  {sum(1 for a in all_accounts if not a['paid_on'])} conta(s) em aberto")

    ttk.Label(root,text=f"Dados locais: {database_path()}  •  Faça cópia deste arquivo para guardar seus registros.",wraplength=1080).pack(anchor="w",padx=18,pady=(0,10))
    product_search.trace_add("write",lambda *_:refresh())
    refresh()
    root.mainloop()
