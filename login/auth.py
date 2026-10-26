"""Autenticação contra o acesso.db. Sem Flask aqui: só banco + regras.

- Senha: só o hash (werkzeug) fica no banco; a comparação é feita por check_password_hash.
- Mensagem de erro é sempre a mesma (login inexistente, senha errada e conta inativa),
  e quando o login não existe ainda se gasta o tempo de um hash, para não dar pra descobrir
  quais logins existem pelo tempo de resposta.
- Bloqueio temporário por login: MAX_FALHAS falhas dentro de JANELA_MIN minutos (conta as
  linhas de log_acesso, que já existe no schema). Tentativas feitas durante o bloqueio NÃO são
  gravadas como falha, senão o bloqueio nunca terminaria enquanto alguém continuasse tentando.
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from werkzeug.security import check_password_hash, generate_password_hash

MAX_FALHAS = 5
JANELA_MIN = 10

_HASH_FALSO = generate_password_hash("senha-descartavel")


@dataclass(frozen=True)
class Usuario:
    id_usuario: int
    login: str
    nome: str
    perfil: str
    id_setor: Optional[int]
    id_secretaria: Optional[int]
    codigo_docente: Optional[str]


def abrir_acesso(caminho):
    conn = sqlite3.connect(caminho, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _agora(delta_min=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_min)).strftime("%Y-%m-%dT%H:%M:%S")


def _como_usuario(row):
    return Usuario(row["id_usuario"], row["login"], row["nome"], row["perfil"],
                   row["id_setor"], row["id_secretaria"], row["codigo_docente"])


def _registrar(conn, id_usuario, login, sucesso):
    conn.execute(
        "INSERT INTO log_acesso (id_usuario, login_tentado, data_hora, sucesso) VALUES (?, ?, ?, ?)",
        (id_usuario, login, _agora(), 1 if sucesso else 0))
    conn.commit()


def _bloqueado(conn, login):
    """True se o login já falhou MAX_FALHAS vezes na janela, contando só depois do último sucesso."""
    n = conn.execute(
        "SELECT COUNT(*) FROM log_acesso "
        "WHERE login_tentado = ? AND sucesso = 0 AND data_hora > ? "
        "AND data_hora > COALESCE((SELECT MAX(data_hora) FROM log_acesso "
        "                          WHERE login_tentado = ? AND sucesso = 1), '')",
        (login, _agora(-JANELA_MIN), login)).fetchone()[0]
    return n >= MAX_FALHAS


def autenticar(caminho_acesso, login, senha):
    """Devolve (Usuario, None) se entrou, ou (None, motivo) com motivo 'invalido' | 'bloqueado'."""
    conn = abrir_acesso(caminho_acesso)
    try:
        if login and _bloqueado(conn, login):
            return None, "bloqueado"

        row = conn.execute("SELECT * FROM usuario_sistema WHERE login = ?", (login,)).fetchone()
        if row is None:
            check_password_hash(_HASH_FALSO, senha)          # equaliza o tempo de resposta
            if login:
                _registrar(conn, None, login, False)
            return None, "invalido"

        senha_ok = check_password_hash(row["senha_hash"], senha)
        if not (senha_ok and row["ativo"]):
            _registrar(conn, row["id_usuario"], login, False)
            return None, "invalido"

        _registrar(conn, row["id_usuario"], login, True)
        return _como_usuario(row), None
    finally:
        conn.close()


def carregar_usuario(conn, id_usuario):
    """Relê o usuário no banco a cada requisição: conta desativada perde o acesso na hora."""
    row = conn.execute(
        "SELECT * FROM usuario_sistema WHERE id_usuario = ? AND ativo = 1", (id_usuario,)).fetchone()
    return _como_usuario(row) if row else None
