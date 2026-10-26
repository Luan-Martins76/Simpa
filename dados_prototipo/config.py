import os
from datetime import date

N_ALUNOS = 13000                     # numero de alunos no banco
SEMESTRE_INICIO = date(2026, 2, 2)   # início do semestre letivo
N_SEMANAS = 16                       # duração aproximada do semestre
N_AVALIACOES = 3                     # avaliações por disciplina no semestre
N_MESES_FINANCEIRO = 6               # meses de boleto a gerar

# ---- Regras de reprovação e ciclos (usadas pela predição) ----
FREQ_MINIMA = 0.75                   # abaixo de 75% de presença em QUALQUER disciplina = reprovado
MEDIA_MINIMA = 6.0                   # média da disciplina abaixo de 6 = reprovado
CICLOS_FIM_SEMANA = (5, 10, 16)      # o semestre tem 3 ciclos; cada valor = semanas decorridas no fim do ciclo
CICLO_PADRAO = 2                     # ciclo "em andamento" que o sistema mostra por padrão (1, 2 ou 3)
JANELA_RECENTE_DIAS = 28             # janela usada para medir o ritmo RECENTE de faltas

# ---- Usuários de demonstração ----
SENHA_DEMO = "simpa123"      # TODOS os usuários do protótipo usam esta senha (só demo!)
TURMAS_POR_PROFESSOR = 4     # quantas turmas, em média, cada professor leciona

# ---- Bancos (dois arquivos independentes) ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))            # dados_prototipo/
BANCO_DIR = os.path.join(BASE_DIR, "banco_dados")
DB_DADOS_PATH = os.path.join(BANCO_DIR, "dados.db")    # dados acadêmicos (predição)
DB_ACESSO_PATH = os.path.join(BANCO_DIR, "acesso.db")  # login, perfis e permissões
