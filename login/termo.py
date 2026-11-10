"""Termo de privacidade (LGPD): quem já leu e aceitou, e qual versão.

O aceite fica no acesso.db, na tabela aceite_termo. Ela é criada aqui (CREATE TABLE IF NOT EXISTS),
então não precisa regenerar o banco nem mexer no SCHEMA_ACESSO. Se um dia você mover para o schema
oficial, é só copiar o SQL de TABELA_ACEITE.

Subiu o TERMO_VERSAO (mudou o texto da tela)? Todo mundo vê o termo de novo no próximo acesso.
Ele aparece uma vez por versão, não a cada login.
"""
import os
from datetime import datetime, timezone

TERMO_VERSAO = "1.0"

# Dados exibidos na tela. Ajuste por variável de ambiente, sem mexer no HTML.
CONTROLADOR = os.environ.get("SIMPA_CONTROLADOR", "UniEVANGÉLICA")
CONTATO_ENCARREGADO = os.environ.get("SIMPA_DPO_EMAIL", "")      # vazio = texto genérico na tela
AMBIENTE_DEMO = os.environ.get("SIMPA_DEMO", "1") == "1"         # mostra o aviso "dados fictícios"

TABELA_ACEITE = """
CREATE TABLE IF NOT EXISTS aceite_termo (
    id_aceite INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario INTEGER NOT NULL REFERENCES usuario_sistema(id_usuario),
    versao TEXT NOT NULL,
    data_hora TEXT NOT NULL,
    UNIQUE (id_usuario, versao)
)
"""


def garantir_tabela(conn):
    conn.execute(TABELA_ACEITE)
    conn.commit()


def aceite_em(conn, id_usuario):
    """Data/hora (UTC) do aceite da versão atual, ou None se ainda não aceitou."""
    row = conn.execute(
        "SELECT data_hora FROM aceite_termo WHERE id_usuario = ? AND versao = ?",
        (id_usuario, TERMO_VERSAO)).fetchone()
    return row[0] if row else None


def registrar_aceite(conn, id_usuario):
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        "INSERT OR IGNORE INTO aceite_termo (id_usuario, versao, data_hora) VALUES (?, ?, ?)",
        (id_usuario, TERMO_VERSAO, agora))
    conn.commit()
