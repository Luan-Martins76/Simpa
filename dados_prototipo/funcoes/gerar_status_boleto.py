import random


def gerar_status_boleto(mes_idx, arquetipo):
    if arquetipo in ("risco_financeiro", "risco_misto"):
        prob_pendente = 0.55
    else:
        prob_pendente = 0.08
    return "pendente" if random.random() < prob_pendente else "pago"
