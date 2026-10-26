ARQUETIPOS = [
    ("estavel", 0.78),
    ("risco_academico", 0.09),
    ("risco_financeiro", 0.07),
    ("risco_misto", 0.06),
]

# Realismo: nem todo aluno em risco desiste. Parte deles reage no meio do semestre
# (leva um susto na 1a prova, volta a frequentar) e a trajetoria volta a subir.
PROB_RECUPERA = 0.35          # chance de um aluno de risco (academico/misto) se recuperar
INICIO_RECUPERACAO = 0.5      # a partir de que ponto do semestre (0 a 1) a recuperacao comeca
