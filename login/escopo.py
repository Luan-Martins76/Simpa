"""O que cada perfil pode ver. Traduz (usuário -> escopo) lendo o acesso.db.

Regras (ESTRUTURA_UNIVERSIDADE.py):
    admin, reitor_geral -> todos os cursos
    reitor_setor        -> cursos de todas as secretarias do setor
    secretario          -> cursos da secretaria
    coordenador         -> o(s) curso(s) em coordenacao_curso
    professor           -> só as turmas dele (codigo_docente)

Falha fechada: perfil desconhecido ou vínculo vazio = escopo vazio (não vê nada).
O acesso.db guarda só CÓDIGO de curso/docente; quem aplica o filtro nos dados é a predição.
"""
from dataclasses import dataclass
from typing import Optional

ROTULO_PERFIL = {
    "admin": "Administrador do sistema",
    "reitor_geral": "Reitor Geral",
    "reitor_setor": "Reitor de Setor",
    "secretario": "Secretário(a)",
    "coordenador": "Coordenador(a) pedagógico(a)",
    "professor": "Professor(a)",
}


@dataclass(frozen=True)
class Escopo:
    todos_os_cursos: bool
    cursos: frozenset
    codigo_docente: Optional[str]
    descricao: str

    @property
    def e_professor(self):
        return self.codigo_docente is not None

    @property
    def ve_financeiro(self):
        # Privilégio mínimo: professor não recebe dado financeiro do aluno.
        return not self.e_professor

    @property
    def cursos_ou_none(self):
        """None = sem filtro de curso (formato que a predição espera)."""
        return None if self.todos_os_cursos else self.cursos


def _codigos(conn, sql, *args):
    return frozenset(r[0] for r in conn.execute(sql, args))


def resolver_escopo(conn, usuario):
    p = usuario.perfil

    if p in ("admin", "reitor_geral"):
        return Escopo(True, frozenset(), None, "Todos os cursos da instituição")

    if p == "reitor_setor":
        setor = conn.execute("SELECT nome FROM setor WHERE id_setor = ?", (usuario.id_setor,)).fetchone()
        cursos = _codigos(
            conn,
            "SELECT sc.codigo_curso FROM secretaria_curso sc "
            "JOIN secretaria s ON s.id_secretaria = sc.id_secretaria WHERE s.id_setor = ?",
            usuario.id_setor)
        return Escopo(False, cursos, None, setor["nome"] if setor else "Setor")

    if p == "secretario":
        sec = conn.execute(
            "SELECT nome FROM secretaria WHERE id_secretaria = ?", (usuario.id_secretaria,)).fetchone()
        cursos = _codigos(
            conn, "SELECT codigo_curso FROM secretaria_curso WHERE id_secretaria = ?", usuario.id_secretaria)
        return Escopo(False, cursos, None, sec["nome"] if sec else "Secretaria")

    if p == "coordenador":
        cursos = _codigos(
            conn, "SELECT codigo_curso FROM coordenacao_curso WHERE id_usuario = ?", usuario.id_usuario)
        nomes = ", ".join(sorted(c.replace("_", " ") for c in cursos)) or "nenhum curso"
        return Escopo(False, cursos, None, f"Curso: {nomes}")

    if p == "professor" and usuario.codigo_docente:
        return Escopo(False, frozenset(), usuario.codigo_docente,
                      f"Alunos das suas turmas ({usuario.codigo_docente})")

    return Escopo(False, frozenset(), None, "Sem acesso")
