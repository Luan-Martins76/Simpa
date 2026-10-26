"""Como não há FK entre dados.db e acesso.db, esta conferência cruza os códigos."""
import sqlite3
from pathlib import Path

from dados_prototipo.config import DB_ACESSO_PATH, DB_DADOS_PATH


def _abrir_ro(caminho):
    return sqlite3.connect(Path(caminho).resolve().as_uri() + "?mode=ro", uri=True)


def verificar_consistencia():
    """Devolve a lista de problemas encontrados (vazia = tudo certo)."""
    dados, acesso = _abrir_ro(DB_DADOS_PATH), _abrir_ro(DB_ACESSO_PATH)
    try:
        cursos_regulares = {r[0] for r in dados.execute("SELECT codigo FROM curso WHERE tipo = 'regular'")}
        cursos_todos = {r[0] for r in dados.execute("SELECT codigo FROM curso")}
        docentes = {r[0] for r in dados.execute("SELECT codigo_docente FROM docente")}

        em_secretaria = {r[0] for r in acesso.execute("SELECT codigo_curso FROM secretaria_curso")}
        em_coordenacao = {r[0] for r in acesso.execute("SELECT codigo_curso FROM coordenacao_curso")}
        usuarios_docentes = {r[0] for r in acesso.execute(
            "SELECT codigo_docente FROM usuario_sistema WHERE perfil = 'professor'")}

        problemas = []
        for c in sorted((em_secretaria | em_coordenacao) - cursos_todos):
            problemas.append(f"acesso aponta pra curso que não existe nos dados: {c}")
        for c in sorted(cursos_regulares - em_secretaria):
            problemas.append(f"curso regular sem secretaria no acesso: {c}")
        for c in sorted(cursos_regulares - em_coordenacao):
            problemas.append(f"curso regular sem coordenador no acesso: {c}")
        for d in sorted(usuarios_docentes - docentes):
            problemas.append(f"professor no acesso com docente inexistente nos dados: {d}")
        for d in sorted(docentes - usuarios_docentes):
            problemas.append(f"docente sem conta de acesso: {d}")
        return problemas
    finally:
        dados.close()
        acesso.close()
