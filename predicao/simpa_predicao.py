"""
SIMPA - Indicador PREDITIVO de reprovacao (calculo + visao por perfil de acesso).

O que mudou em relacao a versao analitica
-----------------------------------------
O sistema nao olha mais o semestre fechado. Ele recebe um CICLO (1, 2 ou 3) e enxerga somente o
que ja aconteceu ate o fim dele: aulas dadas, notas ja lancadas e boletos ja vencidos. A partir
disso PROJETA o resto do semestre e estima a chance de o aluno reprovar ANTES de acontecer.

Regras de reprovacao (por disciplina; reprovou em qualquer uma = aluno reprovado):
    * frequencia abaixo de 75%   (FREQ_MINIMA)
    * media final abaixo de 6,0  (MEDIA_MINIMA)

Como cada regra vira um risco (0 a 1)
    * Frequencia: o limite de faltas do semestre e fixo (16 aulas, 75% -> no maximo 4 faltas). Ve-se
      quantas faltas o aluno ja tem, estima-se o ritmo de faltas (misturando o historico inteiro com
      as ultimas semanas, com um prior para nao concluir demais com poucas aulas) e calcula-se a
      probabilidade de estourar o limite nas aulas que ainda faltam (distribuicao binomial).
    * Nota: com as notas lancadas, calcula-se a media parcial, a nota que ainda precisa tirar nas
      avaliacoes restantes e projeta-se a media final (com tendencia de queda, quando ha 2+ notas).
      A incerteza e maior quanto menos avaliacoes ja ocorreram (normal), e a probabilidade de a
      media final ficar abaixo de 6 e o risco.
    * Reprovacao "consumada": faltas ja acima do limite, ou nota necessaria acima de 10. Risco = 1.
      Nesse ponto nao adianta mais agir; o valor do sistema esta em pegar o aluno ANTES.

Score do aluno = max( soma ponderada dos sinais, probabilidade de reprovar em alguma disciplina ).
Os pesos continuam parametro (calibrar com a secretaria). Sinal sem dado ainda (ex.: nenhuma nota
lancada no inicio do ciclo 1) sai da conta e os pesos dos demais sao renormalizados: ausencia de
dado nao e "sem risco".

Bancos (dois arquivos independentes, ver dados_prototipo/):
    dados.db   -> alunos, turmas, notas, frequencia, financeiro (lido aqui, SOMENTE LEITURA)
    acesso.db  -> usuarios e permissoes (lido pelo pacote login/, nunca por este modulo)

Este modulo NAO sabe quem e o usuario: quem decide o escopo e o pacote login/. Ele so recebe
o resultado ja resolvido -- `cursos` (None = todos) ou `codigo_docente` -- e devolve apenas
os alunos daquele escopo. Assim a regra de seguranca fica num ponto so (resultados_visiveis).

Visoes:
    * Global / setor / secretaria / coordenacao: score completo (4 sinais) dos alunos dos
      cursos do escopo.
    * Professor: so os alunos matriculados nas turmas dele, e so o que acontece NAS turmas
      dele (notas e frequencia da disciplina). Inadimplencia e dados de outras disciplinas
      nao entram (privilegio minimo). Os pesos dos sinais academicos sao renormalizados.

Uso:
    python predicao/simpa_predicao.py                 # relatorio no console (ciclo padrao)
    python predicao/simpa_predicao.py --ciclo 1       # como o sistema enxergaria no fim do ciclo 1
    python predicao/simpa_predicao.py --csv r.csv     # exporta CSV
    python predicao/simpa_predicao.py --backtest      # compara a previsao de cada ciclo com o resultado final
    python app.py                                     # front com login (Flask)
"""
# merece um refatoramento, depois... quando a vontade tiver muita
import argparse
import csv
import json
import math
import os
import sqlite3
import statistics
import sys
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:          # permite rodar este arquivo direto: python predicao/simpa_predicao.py
    sys.path.insert(0, str(RAIZ))

from dados_prototipo.config import (  # noqa: E402
    CICLO_PADRAO, CICLOS_FIM_SEMANA, DB_DADOS_PATH, FREQ_MINIMA, JANELA_RECENTE_DIAS,
    MEDIA_MINIMA, N_AVALIACOES, N_SEMANAS, SEMESTRE_INICIO,
)

DB_PATH_PADRAO = DB_DADOS_PATH
N_CICLOS = len(CICLOS_FIM_SEMANA)

# Pesos PLACEHOLDER -- pendentes de validacao com a secretaria.
# w1 = risco de reprovar por falta, w2 = risco de reprovar por media, w3 = instabilidade das notas,
# w4 = inadimplencia (sinal de evasao, nao de reprovacao: pesa menos).
PESOS_PADRAO = {
    "w1_frequencia_invertida": 0.40,
    "w2_queda_desempenho": 0.35,
    "w3_desvio_padrao": 0.05,
    "w4_inadimplencia": 0.20,
}
CHAVES_ACADEMICAS = ("w1_frequencia_invertida", "w2_queda_desempenho", "w3_desvio_padrao")

# Parametros do modelo de projecao (placeholders a calibrar com dados reais)
PRIOR_FALTA = 0.08            # taxa de faltas esperada de um aluno "tipico" (so pesa no comeco)
PRIOR_PESO = 3                # quantas aulas de "evidencia" o prior vale
SIGMA_NOTA_PRIOR = 1.2        # variacao esperada entre avaliacoes quando so ha 1 nota
SIGMA_NOTA_MIN = 0.8          # piso da variacao entre avaliacoes (nunca assumir nota "certa")

FAIXAS = [
    (0.66, "risco critico", "#C62828"),
    (0.40, "ponto de atencao", "#E65100"),
    (0.0, "regular", "#2E7D32"),
]


def classificar(score):
    for limiar, rotulo, cor in FAIXAS:
        if score >= limiar:
            return rotulo, cor
    return FAIXAS[-1][1], FAIXAS[-1][2]


def pesos_efetivos(pesos, financeiro=True):
    """Pesos de fato usados no score. Sem financeiro (professor), os 3 sinais academicos
    sao renormalizados para somar 1."""
    if financeiro:
        return dict(pesos)
    soma = sum(pesos[k] for k in CHAVES_ACADEMICAS)
    if soma <= 0:
        return {k: 0.0 for k in CHAVES_ACADEMICAS}
    return {k: round(pesos[k] / soma, 4) for k in CHAVES_ACADEMICAS}



# Ciclos: ate onde o sistema "enxerga"
def ciclo_valido(ciclo):
    try:
        c = int(ciclo)
    except (TypeError, ValueError):
        return CICLO_PADRAO
    return c if 1 <= c <= N_CICLOS else CICLO_PADRAO


def corte_do_ciclo(ciclo):
    """Data de corte EXCLUSIVA (so entra dado com data < corte). None no ultimo ciclo = tudo."""
    ciclo = ciclo_valido(ciclo)
    if ciclo == N_CICLOS:
        return None
    return (SEMESTRE_INICIO + timedelta(weeks=CICLOS_FIM_SEMANA[ciclo - 1])).isoformat()


def _fim_efetivo(corte):
    if corte:
        return datetime.fromisoformat(corte).date()
    return SEMESTRE_INICIO + timedelta(weeks=N_SEMANAS)



# Carga em lote do dados.db (somente leitura). Poucas queries no total, nada por aluno.
def _abrir_ro(db_path):
    return sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)


class Dados:
    """Tudo que o calculo precisa, carregado uma vez do dados.db (ja cortado no ciclo)."""

    def __init__(self, alunos, turmas, matriculas, freq_mat, notas_mat, fin, ciclo):
        self.ciclo = ciclo
        self.alunos = alunos            # [(id_aluno, nome, curso_codigo, curso_nome, periodo)]
        self.turmas = turmas            # id_turma -> {curso, curso_nome, disciplina, codigo_docente, docente}
        self.freq_mat = freq_mat        # id_matricula -> (presencas, aulas, presencas_recentes, aulas_recentes)
        self.notas_mat = notas_mat      # id_matricula -> [(nota, data)]
        self.fin = fin                  # id_aluno -> [status do boleto]
        self.por_aluno = defaultdict(list)   # id_aluno -> [(id_turma, id_matricula)]
        self.por_turma = defaultdict(list)   # id_turma -> [(id_aluno, id_matricula)]
        for id_mat, id_aluno, id_turma in matriculas:
            self.por_aluno[id_aluno].append((id_turma, id_mat))
            self.por_turma[id_turma].append((id_aluno, id_mat))
        self.alunos_por_id = {a[0]: a for a in alunos}
        self.cursos = sorted({(a[2], a[3]) for a in alunos})   # so cursos que tem aluno


def carregar_tudo(db_path, ciclo=None):
    ciclo = ciclo_valido(ciclo)
    corte = corte_do_ciclo(ciclo)
    fim = _fim_efetivo(corte)
    inicio_recente = (fim - timedelta(days=JANELA_RECENTE_DIAS)).isoformat()
    filtro = "WHERE data < ?" if corte else ""
    arg = (corte,) if corte else ()

    conn = _abrir_ro(db_path)
    try:
        alunos = conn.execute(
            "SELECT a.id_aluno, a.nome, c.codigo, c.nome, a.periodo "
            "FROM aluno a JOIN curso c ON c.id_curso = a.id_curso"
        ).fetchall()
        turmas = {
            i: {"curso": cod, "curso_nome": cnome, "disciplina": disc, "codigo_docente": cd, "docente": dnome}
            for i, cod, cnome, disc, cd, dnome in conn.execute(
                "SELECT t.id_turma, c.codigo, c.nome, t.disciplina, t.codigo_docente, d.nome "
                "FROM turma t JOIN curso c ON c.id_curso = t.id_curso "
                "JOIN docente d ON d.codigo_docente = t.codigo_docente"
            )
        }
        matriculas = conn.execute("SELECT id_matricula, id_aluno, id_turma FROM matricula").fetchall()
        freq_mat = {
            i: (p or 0, t, pr or 0, tr or 0)
            for i, p, t, pr, tr in conn.execute(
                "SELECT id_matricula, SUM(presenca), COUNT(*), "
                "SUM(CASE WHEN data >= ? THEN presenca ELSE 0 END), "
                "SUM(CASE WHEN data >= ? THEN 1 ELSE 0 END) "
                f"FROM frequencia {filtro} GROUP BY id_matricula",
                (inicio_recente, inicio_recente) + arg)
        }
        notas_mat = defaultdict(list)
        for i, n, d in conn.execute(f"SELECT id_matricula, nota, data FROM registro_academico {filtro}", arg):
            notas_mat[i].append((n, d))
        fin = defaultdict(list)
        for i, s in conn.execute(f"SELECT id_aluno, status FROM financeiro {filtro}", arg):
            fin[i].append(s)
    finally:
        conn.close()
    return Dados(alunos, turmas, matriculas, freq_mat, notas_mat, fin, ciclo)



# Probabilidades auxiliares
def _binom_cauda(n, q, k):
    """P(X >= k) para X ~ Binomial(n, q)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    q = min(max(q, 0.0), 1.0)
    return min(1.0, sum(math.comb(n, j) * q ** j * (1 - q) ** (n - j) for j in range(k, n + 1)))


def _normal_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _fmt(x, casas=1):
    return f"{x:.{casas}f}".replace(".", ",")



# Os sinais de risco (agora por DISCIPLINA, projetando o resto do semestre)
def faltas_maximas():
    """Quantas faltas o semestre inteiro admite (16 aulas e 75% -> 4)."""
    return N_SEMANAS - math.ceil(round(FREQ_MINIMA * N_SEMANAS, 9))


def analisar_frequencia(presencas, aulas, pres_rec, aulas_rec, taxa_prior=PRIOR_FALTA):
    """Risco de estourar o limite de faltas ate o fim do semestre. None = ainda sem aulas.

    taxa_prior = taxa de faltas do aluno nas disciplinas em conjunto: com poucas aulas de UMA disciplina,
    o ritmo do aluno em geral e uma evidencia melhor do que uma taxa fixa para todos."""
    if not aulas:
        return None
    fmax = faltas_maximas()
    faltas = aulas - presencas
    restantes = max(N_SEMANAS - aulas, 0)
    folga = fmax - faltas
    info = {"faltas": faltas, "aulas": aulas, "faltas_max": fmax, "folga": folga,
            "restantes": restantes, "consumado": False}
    if folga < 0:
        info.update(prob=1.0, consumado=True, projecao=float(faltas),
                    texto=f"{faltas} faltas em {aulas} aulas, acima do limite de {fmax} do semestre "
                          f"(75% de presenca): reprovacao por frequencia ja consumada")
        return info
    if restantes == 0:
        info.update(prob=0.0, projecao=float(faltas),
                    texto=f"fechou o semestre com {faltas} faltas (limite {fmax}): dentro da frequencia minima")
        return info
    q_geral = (faltas + PRIOR_PESO * taxa_prior) / (aulas + PRIOR_PESO)
    faltas_rec = aulas_rec - pres_rec
    q_rec = (faltas_rec + 2 * q_geral) / (aulas_rec + 2)
    q = min(max(0.5 * q_geral + 0.5 * q_rec, 0.0), 1.0)      # ritmo atual pesa tanto quanto o historico
    prob = _binom_cauda(restantes, q, folga + 1)
    projecao = faltas + q * restantes
    info.update(prob=prob, projecao=projecao, taxa=q,
                texto=f"{faltas} faltas em {aulas} aulas (limite {fmax} no semestre, folga de {folga}); "
                      f"no ritmo atual chega a {_fmt(projecao)} faltas")
    return info


def analisar_nota(notas, media_aluno=None, sigma_aluno=None):
    """Risco de a media final da disciplina ficar abaixo de MEDIA_MINIMA. None = nenhuma nota lancada.

    media_aluno/sigma_aluno = media e dispersao das notas do aluno em todas as disciplinas. So entram
    quando a disciplina tem uma unica nota (inicio do ciclo 1): ai o desempenho geral do aluno e
    evidencia melhor do que uma nota isolada."""
    if not notas:
        return None
    valores = [n for n, _ in sorted(notas, key=lambda x: x[1])]
    k = len(valores)
    soma = sum(valores)
    media_parcial = soma / k
    restantes = max(N_AVALIACOES - k, 0)
    info = {"feitas": k, "previstas": N_AVALIACOES, "restantes": restantes,
            "media_parcial": media_parcial, "consumado": False}

    if restantes == 0:
        reprovou = media_parcial < MEDIA_MINIMA
        info.update(prob=1.0 if reprovou else 0.0, consumado=reprovou, media_projetada=media_parcial,
                    texto=f"media final {_fmt(media_parcial)} "
                          + ("(abaixo de 6,0): reprovacao por nota consumada" if reprovou else "(aprovado por nota)"))
        return info

    necessaria = (MEDIA_MINIMA * N_AVALIACOES - soma) / restantes
    info["necessaria"] = necessaria
    base = (f"media parcial {_fmt(media_parcial)} ({k} de {N_AVALIACOES} avaliacoes)")
    if necessaria > 10:
        info.update(prob=1.0, consumado=True, media_projetada=(soma + 10 * restantes) / N_AVALIACOES,
                    texto=f"{base}; precisaria de {_fmt(necessaria)} nas {restantes} restantes "
                          f"(acima de 10): reprovacao por nota ja consumada")
        return info
    if necessaria <= 0:
        info.update(prob=0.0, media_projetada=soma / N_AVALIACOES,
                    texto=f"{base}; ja garantiu a media {_fmt(MEDIA_MINIMA)} mesmo zerando o resto")
        return info

    # tendencia (so com 2+ notas), com peso crescente conforme ha mais evidencia
    mu = media_parcial
    if k == 1 and media_aluno is not None:
        mu = (media_parcial + media_aluno) / 2
    if k >= 2:
        x_m = (k - 1) / 2
        den = sum((i - x_m) ** 2 for i in range(k))
        b = sum((i - x_m) * (v - media_parcial) for i, v in enumerate(valores)) / den
        futuras = [min(max(media_parcial + b * (i - x_m), 0.0), 10.0) for i in range(k, N_AVALIACOES)]
        w = min(1.0, (k - 1) / 2) * 0.7
        mu = (1 - w) * media_parcial + w * (sum(futuras) / len(futuras))
    if k >= 2:
        sigma = max(statistics.stdev(valores), SIGMA_NOTA_MIN)
    else:
        sigma = max(sigma_aluno, SIGMA_NOTA_MIN) if sigma_aluno is not None else SIGMA_NOTA_PRIOR
    media_final = (soma + restantes * mu) / N_AVALIACOES
    var = (restantes * sigma ** 2 + restantes ** 2 * sigma ** 2 / k) / N_AVALIACOES ** 2
    prob = _normal_cdf((MEDIA_MINIMA - media_final) / math.sqrt(var))
    info.update(prob=prob, media_projetada=media_final, mu=mu,
                texto=f"{base}; precisa de {_fmt(necessaria)} nas {restantes} restantes para fechar em "
                      f"{_fmt(MEDIA_MINIMA)} (projecao da media final: {_fmt(media_final)})")
    return info


def sinal_desvio_padrao(notas):
    """Instabilidade das notas (None enquanto houver menos de 2 notas)."""
    if len(notas) < 2:
        return None, "menos de 2 notas lancadas: instabilidade ainda nao medida"
    desvio = statistics.stdev(n for n, _ in notas)
    return min(desvio / 5.0, 1.0), f"desvio-padrao das notas de {_fmt(desvio, 2)}"


def sinal_inadimplencia(status_boletos):
    if not status_boletos:
        return None, "nenhum boleto vencido ate o momento"
    pendentes = status_boletos.count("pendente")
    return pendentes / len(status_boletos), f"{pendentes}/{len(status_boletos)} boletos pendentes"


def _analisar_aluno(dados, pares):
    """pares = [(id_turma, id_matricula)] -> (freq, notas, materias, analises)
    freq = (presencas, aulas); notas = [(nota, data)];
    materias = [(id_turma, media_parcial, presencas, aulas)]; analises = uma por disciplina."""
    p_tot = t_tot = 0
    notas, materias, analises = [], [], []
    for _, id_mat in pares:
        p, t, _, _ = dados.freq_mat.get(id_mat, (0, 0, 0, 0))
        p_tot += p
        t_tot += t
        notas.extend(dados.notas_mat.get(id_mat, []))
    # priors do proprio aluno (todas as disciplinas em conjunto)
    taxa_aluno = ((t_tot - p_tot) + PRIOR_PESO * PRIOR_FALTA) / (t_tot + PRIOR_PESO)
    vals = [n for n, _ in notas]
    media_aluno = sum(vals) / len(vals) if vals else None
    sigma_aluno = statistics.stdev(vals) if len(vals) >= 3 else None

    for id_turma, id_mat in pares:
        p, t, pr, tr = dados.freq_mat.get(id_mat, (0, 0, 0, 0))
        ns = dados.notas_mat.get(id_mat, [])
        media = round(sum(n for n, _ in ns) / len(ns), 1) if ns else None
        materias.append((id_turma, media, p, t))
        af = analisar_frequencia(p, t, pr, tr, taxa_aluno)
        an = analisar_nota(ns, media_aluno, sigma_aluno)
        pf = af["prob"] if af else 0.0
        pn = an["prob"] if an else 0.0
        analises.append({"id_turma": id_turma, "freq": af, "nota": an,
                         "prob": 1 - (1 - pf) * (1 - pn)})
    return (p_tot, t_tot), notas, materias, analises



# Hipotese de causa provavel: combina os sinais em um diagnostico legivel.
# Depende so dos valores dos sinais (nao dos pesos). Limiares sao placeholder.
RISCO_LIMIAR, DESVIO_LIMIAR, INADIMP_LIMIAR = 0.40, 0.30, 0.30


def diagnosticar(fatores, financeiro=True, certa=False):
    """financeiro=False (visao do professor): o sinal de inadimplencia nao existe, entao
    o texto nao pode afirmar 'sem pendencia financeira' -- nao sabemos."""
    nem_fin = " nem pendencia financeira" if financeiro else ""
    v = {f["fator"]: f["valor"] for f in fatores}
    freq_alta = v["frequencia_invertida"] >= RISCO_LIMIAR
    nota_alta = v["queda_desempenho"] >= RISCO_LIMIAR
    instavel = v["desvio_padrao"] > DESVIO_LIMIAR
    inadimplente = v.get("inadimplencia", 0) > INADIMP_LIMIAR

    #A essência do desenvolvimento: há quem diga que um código sem uma função cheia de if não é confiável
    prefixo = "Reprovacao ja consumada em ao menos uma disciplina -- " if certa else ""
    if freq_alta and nota_alta and inadimplente:
        return (prefixo + "Faltas, media em risco e pendencia financeira ao mesmo tempo -- quadro mais "
                "grave, sugere abandono em curso, nao um fator isolado.")
    if freq_alta and nota_alta:
        return (prefixo + "Faltas acumuladas e media abaixo do necessario na mesma janela -- sugere "
                "desengajamento progressivo" + ("." if certa else "; ainda ha tempo de agir se a abordagem for agora."))
    if freq_alta and inadimplente:
        return (prefixo + "Faltas no limite junto com pendencia financeira -- padrao comum de quem "
                "reduz a presenca ao mesmo tempo em que atrasa os pagamentos.")
    if freq_alta:
        return (prefixo + f"Risco de reprovar por frequencia, sem problema de nota{nem_fin} -- pode indicar "
                "dificuldade de conciliar horarios (trabalho, deslocamento) mais do que desinteresse.")
    if nota_alta and instavel:
        return (prefixo + "Media em risco com notas instaveis e frequencia ok -- sugere dificuldade com o "
                "conteudo de disciplinas especificas.")
    if nota_alta and inadimplente:
        return (prefixo + "Media em risco e pendencia financeira juntas -- a dificuldade financeira pode "
                "estar afetando a dedicacao aos estudos.")
    if nota_alta:
        return (prefixo + "Media em risco com frequencia ok -- vale checar com o professor a disciplina "
                "indicada e quanto falta recuperar nas proximas avaliacoes.")
    if inadimplente:
        return ("Pendencia financeira predominante, sem risco de reprovacao ate agora -- risco financeiro "
                "isolado, nao ligado ao desempenho.")
    if instavel:
        return "Notas instaveis sem risco de reprovacao ate agora -- pode ser variacao normal entre avaliacoes."
    if any(val and val > 0.05 for val in v.values()):
        return "Combinacao leve de fatores, nenhum isoladamente forte -- acompanhamento preventivo."
    return "Sem sinais de risco relevantes nos dados disponiveis ate agora."


def _pior(analises, chave):
    """Disciplina com maior risco no sinal `chave` ('freq' ou 'nota'); None se nenhuma tem dado."""
    cand = [a for a in analises if a[chave]]
    return max(cand, key=lambda a: a[chave]["prob"]) if cand else None


def calcular_risco_aluno(aluno, freq, notas, fin, pesos, financeiro=True, analises=(), turmas=None):
    """`pesos` ja deve ser o dicionario efetivo (ver pesos_efetivos).
    financeiro=False -> o fator de inadimplencia nem e calculado."""
    id_aluno, nome, curso, curso_nome, periodo = aluno
    turmas = turmas or {}
    disc = lambda a: turmas.get(a["id_turma"], {}).get("disciplina", f"turma {a['id_turma']}")  # noqa: E731

    pf, pn = _pior(analises, "freq"), _pior(analises, "nota")
    v_freq = pf["freq"]["prob"] if pf else None
    m_freq = f"{disc(pf)}: {pf['freq']['texto']}" if pf else "ainda sem aulas registradas"
    v_nota = pn["nota"]["prob"] if pn else None
    m_nota = f"{disc(pn)}: {pn['nota']['texto']}" if pn else "ainda sem notas lancadas"
    v_desv, m_desv = sinal_desvio_padrao(notas)

    valores = [
        ("frequencia_invertida", "w1_frequencia_invertida", v_freq, m_freq),
        ("queda_desempenho", "w2_queda_desempenho", v_nota, m_nota),
        ("desvio_padrao", "w3_desvio_padrao", v_desv, m_desv),
    ]
    if financeiro:
        v_fin, m_fin = sinal_inadimplencia(fin)
        valores.append(("inadimplencia", "w4_inadimplencia", v_fin, m_fin))

    # sinal sem dado sai da conta e os pesos dos demais sao renormalizados
    soma_pesos = sum(pesos[ch] for _, ch, v, _ in valores if v is not None)
    fatores = []
    for nome_f, chave, v, motivo in valores:
        peso = (pesos[chave] / soma_pesos) if (v is not None and soma_pesos > 0) else 0.0
        fatores.append({"fator": nome_f, "peso": round(peso, 4),
                        "valor": round(v if v is not None else 0.0, 3), "motivo": motivo})
    score_ponderado = sum(f["peso"] * f["valor"] for f in fatores)

    # probabilidade de reprovar em ALGUMA disciplina (qualquer regra) = o pior caso por disciplina
    prob_reprov = max((a["prob"] for a in analises), default=0.0)
    certa = any((a["freq"] and a["freq"]["consumado"]) or (a["nota"] and a["nota"]["consumado"])
                for a in analises)
    score = round(min(max(score_ponderado, prob_reprov), 1.0), 3)
    rotulo, cor = classificar(score)

    if prob_reprov >= score_ponderado and (v_freq is not None or v_nota is not None):
        principal = max((f for f in fatores if f["fator"] in ("frequencia_invertida", "queda_desempenho")),
                        key=lambda f: f["valor"])
    else:
        principal = max(fatores, key=lambda f: f["peso"] * f["valor"])

    alertas = []
    for a in sorted(analises, key=lambda a: -a["prob"]):
        if a["prob"] < 0.25 or len(alertas) == 3:
            continue
        partes = [x["texto"] for x in (a["freq"], a["nota"]) if x and x["prob"] >= 0.25]
        alertas.append({"id_turma": a["id_turma"], "disciplina": disc(a), "prob": round(a["prob"], 3),
                        "consumada": bool((a["freq"] and a["freq"]["consumado"])
                                          or (a["nota"] and a["nota"]["consumado"])),
                        "detalhe": " | ".join(partes)})

    notas_valores = [n for n, _ in notas]
    return {
        "id_aluno": id_aluno, "nome": nome, "curso": curso, "curso_nome": curso_nome, "periodo": periodo,
        "score": score, "classificacao": rotulo, "cor": cor,
        "motivo_principal": principal["motivo"], "fatores": fatores,
        "diagnostico": diagnosticar(fatores, financeiro, certa),
        "nota_media": round(sum(notas_valores) / len(notas_valores), 2) if notas_valores else None,
        "freq_taxa": (freq[0] / freq[1]) if freq[1] else None,
        "prob_reprovacao": round(prob_reprov, 3), "reprovacao_certa": certa, "alertas": alertas,
    }



# Cache + visoes por escopo (tudo indexado pelo CICLO)
_lock = threading.Lock()
_cache = {"db": None, "dados": {}, "res": {}, "doc": {}}


def obter_dados(db_path, ciclo=None):
    ciclo = ciclo_valido(ciclo)
    with _lock:
        if _cache["db"] != str(db_path):
            _cache.update(db=str(db_path), dados={}, res={}, doc={})
        dados = _cache["dados"].get(ciclo)
    if dados is None:
        dados = carregar_tudo(db_path, ciclo)
        with _lock:
            _cache["dados"][ciclo] = dados
    return dados


def _chave_pesos(pesos):
    return json.dumps(pesos, sort_keys=True)


def obter_resultados(db_path, pesos, ciclo=None):
    """Visao GLOBAL (todos os alunos, 4 sinais). Uso interno + admin/reitor geral."""
    ciclo = ciclo_valido(ciclo)
    dados = obter_dados(db_path, ciclo)
    chave = (ciclo, _chave_pesos(pesos))
    with _lock:
        res = _cache["res"].get(chave)
    if res is None:
        res = []
        for aluno in dados.alunos:
            freq, notas, materias, analises = _analisar_aluno(dados, dados.por_aluno.get(aluno[0], []))
            r = calcular_risco_aluno(aluno, freq, notas, dados.fin.get(aluno[0], []), pesos,
                                     analises=analises, turmas=dados.turmas)
            r["materias"] = materias
            res.append(r)
        res.sort(key=lambda r: r["score"], reverse=True)
        with _lock:
            if len(_cache["res"]) > 12:
                _cache["res"].clear()
            _cache["res"][chave] = res
    return res


def obter_resultados_docente(db_path, codigo_docente, pesos, ciclo=None):
    """Visao do PROFESSOR: so alunos das turmas dele, so dados dessas turmas, sem financeiro."""
    ciclo = ciclo_valido(ciclo)
    dados = obter_dados(db_path, ciclo)
    chave = (ciclo, codigo_docente, _chave_pesos(pesos))
    with _lock:
        res = _cache["doc"].get(chave)
    if res is None:
        efetivos = pesos_efetivos(pesos, financeiro=False)
        minhas = [i for i, t in dados.turmas.items() if t["codigo_docente"] == codigo_docente]
        por_aluno = defaultdict(list)
        for id_turma in minhas:
            for id_aluno, id_mat in dados.por_turma.get(id_turma, []):
                por_aluno[id_aluno].append((id_turma, id_mat))
        res = []
        for id_aluno, pares in por_aluno.items():
            freq, notas, materias, analises = _analisar_aluno(dados, pares)
            r = calcular_risco_aluno(dados.alunos_por_id[id_aluno], freq, notas, [], efetivos,
                                     financeiro=False, analises=analises, turmas=dados.turmas)
            r["materias"] = materias
            res.append(r)
        res.sort(key=lambda r: r["score"], reverse=True)
        with _lock:
            if len(_cache["doc"]) > 600:
                _cache["doc"].clear()
            _cache["doc"][chave] = res
    return res


def resultados_visiveis(db_path, pesos, cursos=None, codigo_docente=None, ciclo=None):
    """PONTO UNICO de controle de escopo. Devolve (resultados, financeiro).

    codigo_docente != None -> visao do professor (cursos e ignorado).
    cursos is None         -> visao global.
    cursos = {...}         -> so alunos desses cursos (conjunto vazio = ninguem: falha fechada).
    """
    if codigo_docente is not None:
        return obter_resultados_docente(db_path, codigo_docente, pesos, ciclo), False
    todos = obter_resultados(db_path, pesos, ciclo)
    if cursos is None:
        return todos, True
    return [r for r in todos if r["curso"] in cursos], True


def filtros_visiveis(db_path, cursos=None, codigo_docente=None):
    """Cursos e materias (turmas) que o usuario pode ver, para montar os filtros do front."""
    dados = obter_dados(db_path)
    if codigo_docente is not None:
        turmas = {i: t for i, t in dados.turmas.items() if t["codigo_docente"] == codigo_docente}
        codigos = {t["curso"] for t in turmas.values()}
        lista_cursos = [(c, n) for c, n in dados.cursos if c in codigos]
    else:
        lista_cursos = [(c, n) for c, n in dados.cursos if cursos is None or c in cursos]
        permitidos = {c for c, _ in lista_cursos}
        turmas = {i: t for i, t in dados.turmas.items() if t["curso"] in permitidos}
    materias = sorted(
        ({"id": i, "curso": t["curso"], "disciplina": t["disciplina"], "docente": t["docente"]}
         for i, t in turmas.items()),
        key=lambda m: (m["curso"], m["disciplina"]))
    return [{"codigo": c, "nome": n} for c, n in lista_cursos], materias


def serializar(r, turmas):
    """Resultado -> dict JSON do front (materias com nome da disciplina/docente)."""
    return {
        "nome": r["nome"], "curso": r["curso"], "curso_nome": r["curso_nome"], "periodo": r["periodo"],
        "score": r["score"], "classificacao": r["classificacao"], "cor": r["cor"],
        "motivo_principal": r["motivo_principal"], "fatores": r["fatores"],
        "diagnostico": r["diagnostico"], "nota_media": r["nota_media"],
        "prob_reprovacao": r["prob_reprovacao"], "reprovacao_certa": r["reprovacao_certa"],
        "alertas": r["alertas"],
        "materias": [
            {"id_turma": i, "disciplina": turmas[i]["disciplina"], "docente": turmas[i]["docente"],
             "media": m, "presencas": p, "total": t}
            for i, m, p, t in r["materias"]
        ],
    }


def calcular_kpis(resultados, financeiro=True):
    """Metricas de contexto pro painel, calculadas sobre a lista JA FILTRADA (escopo + filtros).

    taxa_reprovacao_prevista = alunos com 50% ou mais de chance de reprovar em alguma disciplina.
    reprovacao_certa = alunos que ja passaram do ponto sem volta (faltas acima do limite ou nota
    necessaria acima de 10): nao adianta mais agir, o valor do sistema esta em pegar antes.
    taxa_evasao_proxy continua sendo a fatia em "risco critico" (nao ha trancamento no schema).
    Sem financeiro (professor), taxa_inadimplencia vem None e o front esconde o card.
    """
    n = len(resultados)
    if not n:
        return {"media_geral": None, "frequencia_media": None, "taxa_inadimplencia": None,
                "taxa_evasao_proxy": None, "taxa_reprovacao_prevista": None,
                "reprovacao_certa": 0, "total_alunos": 0}
    notas = [r["nota_media"] for r in resultados if r.get("nota_media") is not None]
    freqs = [r["freq_taxa"] for r in resultados if r.get("freq_taxa") is not None]
    inadimp, criticos, previstos, certos = [], 0, 0, 0
    for r in resultados:
        if financeiro:
            v = {f["fator"]: f for f in r["fatores"]}["inadimplencia"]
            if v["peso"] > 0:
                inadimp.append(v["valor"])
        criticos += r["classificacao"] == "risco critico"
        previstos += r["prob_reprovacao"] >= 0.5
        certos += bool(r["reprovacao_certa"])
    return {
        "media_geral": round(sum(notas) / len(notas), 2) if notas else None,
        "frequencia_media": round(sum(freqs) / len(freqs), 3) if freqs else None,
        "taxa_inadimplencia": (round(sum(inadimp) / len(inadimp), 3) if inadimp else None) if financeiro else None,
        "taxa_evasao_proxy": round(criticos / n, 3),
        "taxa_reprovacao_prevista": round(previstos / n, 3),
        "reprovacao_certa": certos,
        "total_alunos": n,
    }



# Indicadores estatisticos para os graficos do painel (estatistica descritiva,
# correlacao de Pearson e regressao linear simples por minimos quadrados)
MAX_PONTOS_DISPERSAO = 600     # o grafico mostra uma amostra; r e a reta usam TODOS os alunos


def _br(x, casas=2):
    return f"{x:.{casas}f}".replace(".", ",")


def _descritiva(valores):
    """Media, mediana, variancia e desvio-padrao (amostrais). None se nao houver dado."""
    n = len(valores)
    if not n:
        return None
    var = statistics.variance(valores) if n > 1 else 0.0
    return {"n": n, "media": round(sum(valores) / n, 2), "mediana": round(statistics.median(valores), 2),
            "variancia": round(var, 2), "desvio_padrao": round(math.sqrt(var), 2)}


def _reta_minimos_quadrados(xs, ys):
    """y = intercepto + inclinacao * x e correlacao de Pearson r. None sem variacao ou com poucos pontos."""
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0 or syy == 0:
        return None
    b = sxy / sxx
    return {"inclinacao": b, "intercepto": my - b * mx, "r": sxy / math.sqrt(sxx * syy)}


def _leitura_correlacao(reta, n):
    if reta is None:
        return "Poucos alunos (ou sem variação) para medir a relação entre frequência e nota."
    r, b = reta["r"], reta["inclinacao"]
    forca = abs(r)
    if forca < 0.2:
        return (f"r = {_br(r)}: quase nenhuma relação linear entre frequência e nota nesta seleção "
                f"({n} alunos). Correlação não é causa.")
    nivel = "fraca a moderada" if forca < 0.5 else "moderada a forte" if forca < 0.8 else "forte"
    sentido = ("quem frequenta mais tende a tirar notas maiores" if r > 0
               else "frequência maior vem acompanhada de notas menores")
    return (f"r = {_br(r)}: relação {nivel} ({n} alunos); {sentido}. "
            f"A cada 10 pontos percentuais de frequência, a nota média varia cerca de {_br(b * 10, 1)}. "
            f"Correlação não é causa: o gráfico mostra associação, não o motivo.")


def calcular_indicadores(resultados):
    """Dados prontos para os graficos, sobre a lista JA FILTRADA (escopo + filtros)."""
    notas = [r["nota_media"] for r in resultados if r.get("nota_media") is not None]
    freqs = [r["freq_taxa"] for r in resultados if r.get("freq_taxa") is not None]
    pares = [(r["freq_taxa"] * 100, r["nota_media"], r["classificacao"]) for r in resultados
             if r.get("freq_taxa") is not None and r.get("nota_media") is not None]

    faixas = [0] * 10                                  # [0,1), [1,2) ... [9,10]
    for n in notas:
        faixas[min(max(int(n), 0), 9)] += 1
    desc = _descritiva(notas)
    abaixo = sum(1 for n in notas if n < MEDIA_MINIMA)
    leitura_hist = ("Ainda não há notas lançadas nesta seleção." if not desc else
                    f"{round(100 * abaixo / len(notas))}% dos alunos estão com média abaixo de {_br(MEDIA_MINIMA, 1)} "
                    f"(faixas em vermelho). Mediana {_br(desc['mediana'], 1)}; "
                    f"quanto maior o desvio-padrão ({_br(desc['desvio_padrao'])}), mais espalhadas as notas.")

    reta = _reta_minimos_quadrados([x for x, _, _ in pares], [y for _, y, _ in pares])
    passo = max(len(pares) // MAX_PONTOS_DISPERSAO, 1)
    pontos = [[round(x, 1), round(y, 2), c] for x, y, c in pares[::passo]]
    return {
        "nota": desc, "frequencia": _descritiva([f * 100 for f in freqs]),
        "histograma": {"faixas": faixas, "n": len(notas), "abaixo_minimo": abaixo, "leitura": leitura_hist},
        "dispersao": {"pontos": pontos, "n": len(pares), "amostra": len(pontos), "reta": reta,
                      "leitura": _leitura_correlacao(reta, len(pares))},
    }


def agrupar(db_path, resultados, modo="materia", limite=100):
    """Agrega os resultados (ja no escopo) por materia ou por professor.
    Devolve (total_de_grupos, linhas[:limite]) ordenadas pela taxa de risco critico (proxy de evasao)."""
    turmas = obter_dados(db_path).turmas
    ag = {}
    for r in resultados:
        em_risco = r["classificacao"] != "regular"
        critico = r["classificacao"] == "risco critico"
        for id_turma, media, p, t in r["materias"]:
            chave = turmas[id_turma]["codigo_docente"] if modo == "professor" else id_turma
            a = ag.get(chave)
            if a is None:
                a = ag[chave] = {"n": 0, "soma": 0.0, "nmedia": 0, "p": 0, "t": 0,
                                 "risco": 0, "critico": 0, "turmas": set()}
            a["n"] += 1
            if media is not None:
                a["soma"] += media
                a["nmedia"] += 1
            a["p"] += p
            a["t"] += t
            a["risco"] += em_risco
            a["critico"] += critico
            a["turmas"].add(id_turma)
    linhas = []
    for chave, a in ag.items():
        n = a["n"]
        linha = {
            "alunos": n,
            "media": round(a["soma"] / a["nmedia"], 1) if a["nmedia"] else None,
            "frequencia": round(a["p"] / a["t"], 3) if a["t"] else None,
            "em_risco": a["risco"], "criticos": a["critico"],
            "pct_risco": a["risco"] / n, "pct_critico": a["critico"] / n,
        }
        if modo == "professor":
            t0 = turmas[next(iter(a["turmas"]))]
            linha.update(codigo_docente=chave, docente=t0["docente"], turmas=len(a["turmas"]))
        else:
            t0 = turmas[chave]
            linha.update(id_turma=chave, disciplina=t0["disciplina"], curso=t0["curso"],
                         curso_nome=t0["curso_nome"], docente=t0["docente"])
        linhas.append(linha)
    linhas.sort(key=lambda x: (-x["pct_critico"], -x["pct_risco"], -x["alunos"]))
    return len(linhas), linhas[:limite]



# Saidas: console, CSV
def imprimir_relatorio(resultados, top=None, ciclo=None):
    if top:
        resultados = resultados[:top]
    print(f"\nSIMPA - Indicador de Risco de Reprovacao, ciclo {ciclo_valido(ciclo)} de {N_CICLOS} "
          f"({datetime.now():%d/%m/%Y %H:%M})")
    print("=" * 78)
    for r in resultados:
        marca = " [JA REPROVADO EM ALGUMA MATERIA]" if r["reprovacao_certa"] else ""
        print(f"[{r['classificacao'].upper():15s}] {r['nome']:30s} score={r['score']:.3f}{marca}")
        print(f"    motivo principal: {r['motivo_principal']}")
        print(f"    hipotese de causa: {r['diagnostico']}")
    print("=" * 78)
    criticos = sum(1 for r in resultados if r["classificacao"] == "risco critico")
    atencao = sum(1 for r in resultados if r["classificacao"] == "ponto de atencao")
    print(f"Total: {len(resultados)} alunos | {criticos} em risco critico | {atencao} em ponto de atencao\n")


def _celula(valor):
    """Evita injecao de formula quando o CSV e aberto no Excel (=, +, -, @ no inicio)."""
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@"):
        return "'" + valor
    return valor


def escrever_csv(resultados, f):
    w = csv.writer(f)
    w.writerow(["id_aluno", "nome", "curso", "periodo", "score", "classificacao", "prob_reprovacao",
                "reprovacao_ja_consumada", "motivo_principal", "hipotese_causa"])
    for r in resultados:
        w.writerow([_celula(x) for x in (r["id_aluno"], r["nome"], r["curso"], r["periodo"], r["score"],
                                          r["classificacao"], r["prob_reprovacao"],
                                          "sim" if r["reprovacao_certa"] else "nao",
                                          r["motivo_principal"], r["diagnostico"])])


def exportar_csv(resultados, caminho):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escrever_csv(resultados, f)
    print(f"CSV exportado em: {caminho}")


def ler_pesos(raw):
    pesos = dict(PESOS_PADRAO)
    try:
        for k, v in json.loads(raw or "{}").items():
            if k in pesos and float(v) >= 0:
                pesos[k] = float(v)
    except (ValueError, TypeError, AttributeError):
        pass
    return pesos



# Backtest: a previsao de cada ciclo contra o que de fato aconteceu no fim do semestre.
# So e possivel porque o banco sintetico esta completo; com dados reais, rodar no fim do periodo.

def backtest(db_path, pesos=None):
    pesos = pesos or dict(PESOS_PADRAO)
    final = {r["id_aluno"]: r["reprovacao_certa"] for r in obter_resultados(db_path, pesos, N_CICLOS)}
    reprovados = {i for i, v in final.items() if v}
    linhas = []
    for ciclo in range(1, N_CICLOS):
        res = obter_resultados(db_path, pesos, ciclo)
        consumados = {r["id_aluno"] for r in res if r["reprovacao_certa"]}
        sinalizados = {r["id_aluno"] for r in res if r["classificacao"] != "regular" and not r["reprovacao_certa"]}
        criticos = {r["id_aluno"] for r in res if r["classificacao"] == "risco critico" and not r["reprovacao_certa"]}
        a_tempo = reprovados & sinalizados          # reprovaram no fim e ja estavam sinalizados, ainda recuperaveis
        linhas.append({
            "ciclo": ciclo, "alunos": len(res), "reprovam_no_fim": len(reprovados),
            "ja_consumados": len(reprovados & consumados),
            "pegos_a_tempo": len(a_tempo),
            "pegos_a_tempo_criticos": len(reprovados & criticos),
            "ainda_nao_visiveis": len(reprovados - consumados - sinalizados),
            "sinalizados_total": len(sinalizados),
            "falsos_alarmes": len(sinalizados - reprovados),
            "precisao": (len(a_tempo) / len(sinalizados)) if sinalizados else None,
            "precisao_critico": (len(reprovados & criticos) / len(criticos)) if criticos else None,
        })
    return linhas


def imprimir_backtest(linhas):
    if not linhas:
        return
    total = linhas[0]["reprovam_no_fim"]
    print(f"\nBACKTEST: {total} de {linhas[0]['alunos']} alunos reprovam em alguma disciplina no fim do semestre.")
    print("Para cada ciclo: de quem reprova no fim, quantos ja estavam avisados com tempo de agir.\n")
    for l in linhas:
        pct = lambda x: f"{x / total:.0%}" if total else "-"        # noqa: E731
        prec = f"{l['precisao']:.0%}" if l["precisao"] is not None else "-"
        prec_c = f"{l['precisao_critico']:.0%}" if l["precisao_critico"] is not None else "-"
        print(f"Ciclo {l['ciclo']}:")
        print(f"   ja reprovados (tarde demais)        : {l['ja_consumados']:5d}  ({pct(l['ja_consumados'])})")
        print(f"   pegos a tempo (atencao ou critico)  : {l['pegos_a_tempo']:5d}  ({pct(l['pegos_a_tempo'])})")
        print(f"      so os criticos                   : {l['pegos_a_tempo_criticos']:5d}  ({pct(l['pegos_a_tempo_criticos'])})")
        print(f"   ainda sem sinal (nao previstos)     : {l['ainda_nao_visiveis']:5d}  ({pct(l['ainda_nao_visiveis'])})")
        print(f"   alertas ainda evitaveis             : {l['sinalizados_total']:5d}  | falsos alarmes {l['falsos_alarmes']}"
              f"  | precisao {prec} (criticos: {prec_c})\n")


def main():
    parser = argparse.ArgumentParser(description="SIMPA - indicador preditivo de reprovacao (visao global, via console)")
    parser.add_argument("--db", default=DB_PATH_PADRAO, help="Caminho do dados.db")
    parser.add_argument("--ciclo", type=int, default=CICLO_PADRAO,
                        help=f"Ciclo do semestre (1 a {N_CICLOS}): o sistema so enxerga o que ocorreu ate o fim dele")
    parser.add_argument("--pesos", default=None, help='Pesos em JSON, ex: \'{"w1_frequencia_invertida":0.4}\'')
    parser.add_argument("--top", type=int, default=None, help="Mostrar so os N de maior risco")
    parser.add_argument("--csv", default=None, help="Exportar relatorio em CSV")
    parser.add_argument("--backtest", action="store_true",
                        help="Compara a previsao de cada ciclo com o resultado final do semestre")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"Banco nao encontrado em '{args.db}'. Rode antes: python -m dados_prototipo.gerar_simpa_db")

    pesos = ler_pesos(args.pesos)
    if abs(sum(pesos.values()) - 1.0) > 1e-6:
        print(f"Aviso: soma dos pesos = {sum(pesos.values()):.3f} (recomendado somar 1.0)")
    if args.backtest:
        imprimir_backtest(backtest(args.db, pesos))
        return
    resultados = obter_resultados(args.db, pesos, args.ciclo)
    imprimir_relatorio(resultados, top=args.top, ciclo=args.ciclo)
    if args.csv:
        exportar_csv(resultados, args.csv)


if __name__ == "__main__":
    main()
