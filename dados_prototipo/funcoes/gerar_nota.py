import random

from dados_prototipo.dicionarios.ARQUETIPOS import INICIO_RECUPERACAO


def gerar_nota(semana_idx, total_semanas, arquetipo, recupera=False, nivel=0.0):
    """Nota de 0 a 10, com tendencia conforme o arquetipo ao longo do semestre.

    nivel   = diferenca fixa do aluno em relacao a media (tem aluno naturalmente mais forte/fraco).
    recupera = o aluno de risco reage no meio do semestre e a nota volta a subir.
    """
    progresso = semana_idx / max(total_semanas - 1, 1)  # 0 -> inicio, 1 -> fim
    if arquetipo in ("estavel", "risco_financeiro"):
        base = random.gauss(8.0 + nivel, 0.7)
    else:
        queda = 4.5 if arquetipo == "risco_academico" else 5.0
        ruido = 0.7 if arquetipo == "risco_academico" else 1.0
        topo = 8.5 if arquetipo == "risco_academico" else 8.0
        prog_efetivo = progresso
        if recupera and progresso > INICIO_RECUPERACAO:
            # sobe de volta: reflete a queda ate o ponto de virada
            prog_efetivo = INICIO_RECUPERACAO - (progresso - INICIO_RECUPERACAO) * 0.8
        base = topo - prog_efetivo * queda + nivel * 0.5 + random.gauss(0, ruido)
    return round(min(max(base, 0), 10), 1)
