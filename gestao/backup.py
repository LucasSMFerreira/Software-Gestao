"""Exporta uma cópia consistente do banco e tabelas legíveis em CSV."""
import csv
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from gestao.database import database_path

TABLES = ("stores", "products", "movements", "sales", "sale_returns", "purchases", "payables")

def suggested_name() -> str:
    return "gestao-dados-" + datetime.now().strftime("%Y-%m-%d_%H-%M") + ".zip"

def export_data(destination: str | Path) -> Path:
    target = Path(destination).expanduser().resolve()
    if target.suffix.lower() != ".zip":
        raise ValueError("Escolha um arquivo .zip para salvar os dados.")
    if not target.parent.is_dir():
        raise ValueError("A pasta escolhida não existe.")
    if target.exists():
        raise ValueError("Este arquivo já existe. Escolha outro nome para não substituir uma cópia antiga.")
    source = database_path()
    if not source.is_file():
        raise ValueError("Ainda não há dados para salvar.")
    with tempfile.TemporaryDirectory() as folder:
        snapshot = Path(folder) / "gestao.sqlite3"
        with closing(sqlite3.connect(source)) as live, closing(sqlite3.connect(snapshot)) as copy:
            live.backup(copy)
        created = False
        try:
            with ZipFile(target, "x", ZIP_DEFLATED) as archive:
                created = True
                archive.write(snapshot, "gestao.sqlite3")
                with closing(sqlite3.connect(snapshot)) as db:
                    for table in TABLES:
                        rows = db.execute(f"SELECT * FROM {table}")
                        names = [item[0] for item in rows.description]
                        csv_path = Path(folder) / f"{table}.csv"
                        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
                            writer = csv.writer(file)
                            writer.writerow(names)
                            writer.writerows(rows)
                        archive.write(csv_path, f"planilhas/{table}.csv")
                archive.writestr("LEIA-ME.txt", "Copia completa: gestao.sqlite3\nPlanilhas CSV: pasta planilhas.\nPara restaurar, feche o aplicativo e substitua o arquivo de dados pelo gestao.sqlite3 desta copia.\n")
        except Exception:
            if created:
                target.unlink(missing_ok=True)
            raise
    return target
