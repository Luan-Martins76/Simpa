from dados_prototipo.dicionarios.cursos import CURSOS
from dados_prototipo.dicionarios.ESTRUTURA_UNIVERSIDADE import UNIVERSIDADE


def cursos_regulares():
    """Cursos que de fato têm alunos (exclui GRADUACAO e DISCIPLINAS_100%ON-LINE)."""
    nao_regulares = UNIVERSIDADE["estruturas_academicas"]
    return [c for c in CURSOS if c not in nao_regulares]
