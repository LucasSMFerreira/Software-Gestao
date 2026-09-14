"""Inicia o aplicativo desktop unificado."""
from gestao.database import initialize
from gestao.ui import iniciar


if __name__ == "__main__":
    initialize()
    iniciar()
