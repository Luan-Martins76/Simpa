import random

from dados_prototipo.dicionarios.ARQUETIPOS import INICIO_RECUPERACAO


def gerar_presenca(semana_idx, total_semanas, arquetipo, recupera=False, bloco=None):
    """1 = presente, 0 = ausente.

    recupera = aluno de risco que volta a frequentar no meio do semestre.
    bloco    = (semana_inicio, semana_fim) de uma ausencia pontual (doenca, viagem, trabalho),
               que acontece ate com aluno estavel e nao e tendencia.
    """
    if bloco and bloco[0] <= semana_idx <= bloco[1]:
        return 1 if random.random() < 0.25 else 0
    progresso = semana_idx / max(total_semanas - 1, 1)
    if arquetipo in ("estavel", "risco_financeiro"):
        prob_presenca = random.gauss(0.92, 0.06)
    else:
        prog_efetivo = progresso
        if recupera and progresso > INICIO_RECUPERACAO:
            prog_efetivo = INICIO_RECUPERACAO - (progresso - INICIO_RECUPERACAO) * 0.8
        if arquetipo == "risco_academico":
            prob_presenca = 0.90 - prog_efetivo * 0.45
        else:  # risco_misto
            prob_presenca = 0.88 - prog_efetivo * 0.55
    prob_presenca = min(max(prob_presenca, 0.05), 1.0)
    return 1 if random.random() < prob_presenca else 0
