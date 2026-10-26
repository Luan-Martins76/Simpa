import random
from dados_prototipo.dicionarios.ARQUETIPOS import ARQUETIPOS


def sortear_arquetipo():
    r = random.random()
    acumulado = 0
    for nome, peso in ARQUETIPOS:
        acumulado += peso
        if r <= acumulado:
            return nome
    return ARQUETIPOS[-1][0]