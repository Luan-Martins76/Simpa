"""Gera o acesso.db (usuários, perfis e permissões). Não guarda dados acadêmicos."""
import os
import re
import sqlite3
from pathlib import Path

from faker import Faker
from werkzeug.security import generate_password_hash

from dados_prototipo.config import DB_ACESSO_PATH, DB_DADOS_PATH, SENHA_DEMO
from dados_prototipo.dicionarios.ESTRUTURA_UNIVERSIDADE import UNIVERSIDADE
from dados_prototipo.dicionarios.SCHEMA_ACESSO import SCHEMA_ACESSO
from dados_prototipo.funcoes.cursos_regulares import cursos_regulares

fake = Faker("pt_BR")


def _ler_docentes():
    """Lê (codigo_docente, nome) do dados.db em modo somente leitura.
    No sistema real, essa lista viria do cadastro de RH da faculdade."""
    uri = Path(DB_DADOS_PATH).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        return conn.execute("SELECT codigo_docente, nome FROM docente ORDER BY codigo_docente").fetchall()
    finally:
        conn.close()


def _inserir_usuario(cur, login, nome, perfil, id_setor=None, id_secretaria=None, codigo_docente=None):
    cur.execute(
        "INSERT INTO usuario_sistema "
        "(login, senha_hash, nome, perfil, id_setor, id_secretaria, codigo_docente) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (login, generate_password_hash(SENHA_DEMO), nome, perfil, id_setor, id_secretaria, codigo_docente),
    )
    return cur.lastrowid


def gerar_acesso():
    if os.path.exists(DB_ACESSO_PATH):
        print(f"[acesso] Já existe em: {DB_ACESSO_PATH}")
        print("[acesso] Nada foi gerado. Apague o arquivo se quiser recriar do zero.")
        return False
    if not os.path.exists(DB_DADOS_PATH):
        print(f"[acesso] Não achei o dados.db em {DB_DADOS_PATH}. Gere o banco de dados primeiro.")
        return False

    Faker.seed(43)
    docentes = _ler_docentes()

    os.makedirs(os.path.dirname(DB_ACESSO_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_ACESSO_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    cur.executescript(SCHEMA_ACESSO)

    # Estrutura: setor -> secretaria -> cursos (por código)
    setor_ids = {}
    for chave, setor in UNIVERSIDADE["setores"].items():
        cur.execute("INSERT INTO setor (chave, nome) VALUES (?, ?)", (chave, setor["nome"]))
        setor_ids[chave] = cur.lastrowid

    secretaria_ids = {}
    for chave, sec in UNIVERSIDADE["secretarias"].items():
        cur.execute(
            "INSERT INTO secretaria (chave, nome, id_setor) VALUES (?, ?, ?)",
            (chave, sec["nome"], setor_ids[sec["setor"]]),
        )
        secretaria_ids[chave] = cur.lastrowid
        for codigo_curso in sec["cursos"]:
            cur.execute(
                "INSERT INTO secretaria_curso (id_secretaria, codigo_curso) VALUES (?, ?)",
                (secretaria_ids[chave], codigo_curso),
            )

    # Acessos globais
    _inserir_usuario(cur, "dev", "dev de extremo sucesso", "admin")
    _inserir_usuario(cur, "reitor_geral", "Reitor Geral", "reitor_geral")

    # Reitor de cada setor (login = chave definida no desenho, ex.: reitor_saude)
    for chave, setor in UNIVERSIDADE["setores"].items():
        _inserir_usuario(cur, setor["reitor"], fake.name(), "reitor_setor", id_setor=setor_ids[chave])

    # Secretário de cada secretaria
    for chave in UNIVERSIDADE["secretarias"]:
        _inserir_usuario(cur, f"sec_{chave}", fake.name(), "secretario", id_secretaria=secretaria_ids[chave])

    # 1 coordenador por curso regular
    for codigo_curso in cursos_regulares():
        slug = re.sub(r"[^a-z0-9]+", "_", codigo_curso.lower()).strip("_")
        id_usuario = _inserir_usuario(cur, f"coord_{slug}", fake.name(), "coordenador")
        cur.execute(
            "INSERT INTO coordenacao_curso (id_usuario, codigo_curso) VALUES (?, ?)",
            (id_usuario, codigo_curso),
        )

    # Professores: 1 conta por docente do dados.db (DOC0001 -> prof_0001)
    for codigo_docente, nome in docentes:
        _inserir_usuario(cur, f"prof_{codigo_docente.removeprefix('DOC')}", nome, "professor",
                         codigo_docente=codigo_docente)

    conn.commit()

    print("[acesso] gerado em:", DB_ACESSO_PATH)
    for tabela in ["setor", "secretaria", "secretaria_curso", "usuario_sistema", "coordenacao_curso"]:
        cur.execute(f"SELECT COUNT(*) FROM {tabela}")
        print(f"  {tabela:20s} -> {cur.fetchone()[0]} linhas")

    conn.close()
    return True
