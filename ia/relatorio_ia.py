"""Relatório conversacional do SIMPA via Ollama (IA local).

Fluxo: o servidor já tem a lista de alunos filtrada pelo escopo do usuário (a mesma que vira o
CSV). Este módulo transforma essa lista num RESUMO compacto (totais, médias, piores matérias e os
alunos mais críticos), manda para o Ollama e devolve o texto pronto para exibir.

Por que resumo e não o CSV inteiro: um CSV com milhares de linhas estoura o contexto de modelos
locais (e deixa a resposta lenta). Os números gerais são calculados aqui, em Python (a IA não
faz conta), e ela só interpreta e escreve. Eu Luan particularmente odeio que LLM processe dados, interpretar sim processar não..

Variáveis de ambiente:
    SIMPA_OLLAMA_URL      padrão http://127.0.0.1:11434
    SIMPA_OLLAMA_MODEL    padrão llama3.1   (qualquer modelo que você tenha: ollama list)
    SIMPA_OLLAMA_TIMEOUT  segundos de espera pela resposta (padrão 180)

Antes, uma vez:  ollama pull llama3.1   (e deixe o Ollama rodando, da de fazer o codigo iniciar o ollama. Mas sinceramente muita preguiça)
"""
import os

import requests

OLLAMA_URL = os.environ.get("SIMPA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODELO = os.environ.get("SIMPA_OLLAMA_MODEL", "gemma3:4b")
OLLAMA_TIMEOUT = int(os.environ.get("SIMPA_OLLAMA_TIMEOUT", "180"))

TOP_ALUNOS = 15       # quantos alunos críticos vão detalhados para a IA
TOP_MATERIAS = 5      # quantas matérias com maior taxa de risco

SISTEMA = (
    "Você é um analista pedagógico que escreve para coordenadores e professores de uma "
    "universidade brasileira. Escreva em português do Brasil, em tom conversacional e claro, "
    "como se estivesse explicando para um colega. Use SOMENTE os dados fornecidos; não invente "
    "números, nomes ou causas. As 'hipóteses de causa' vêm de uma heurística numérica, então "
    "trate-as como hipóteses, nunca como certeza. Não use markdown (sem #, *, listas com "
    "hífen ou negrito): escreva parágrafos curtos separados por linha em branco. A reprovação "
    "ocorre com frequência abaixo de 75% ou média abaixo de 6 em qualquer disciplina; o sistema "
    "prevê isso durante o semestre, então priorize quem ainda dá tempo de salvar."
)


class IAIndisponivel(Exception):
    """Ollama fora do ar, modelo ausente ou resposta inválida. A mensagem é segura para o usuário."""


def _pct(v):
    return "n/d" if v is None else f"{v * 100:.0f}%"


def montar_resumo(resultados, kpis, financeiro, grupos_materia, escopo, filtros):
    """Texto compacto com tudo que a IA precisa. `resultados` já vem filtrado pelo escopo."""
    cont = {}
    for r in resultados:
        cont[r["classificacao"]] = cont.get(r["classificacao"], 0) + 1
    media = kpis.get("media_geral")

    linhas = [f"ESCOPO DO USUÁRIO: {escopo}"]
    if filtros:
        linhas.append("FILTROS APLICADOS: " + "; ".join(filtros))
    linhas += [
        "",
        f"TOTAL DE ALUNOS ANALISADOS: {len(resultados)}",
        f"- risco crítico (score >= 0,66): {cont.get('risco critico', 0)}",
        f"- ponto de atenção (0,40 a 0,65): {cont.get('ponto de atencao', 0)}",
        f"- regular: {cont.get('regular', 0)}",
        "",
        "INDICADORES GERAIS:",
        f"- média geral de notas: {media if media is not None else 'n/d'}",
        f"- frequência média: {_pct(kpis.get('frequencia_media'))}",
        f"- proporção em risco crítico de reprovar: {_pct(kpis.get('taxa_evasao_proxy'))}",
        f"- proporção com 50% ou mais de chance de reprovar: {_pct(kpis.get('taxa_reprovacao_prevista'))}",
        f"- alunos que já reprovaram em alguma disciplina (sem volta): {kpis.get('reprovacao_certa', 0)}",
    ]
    if financeiro:   # professor não recebe dado financeiro: nem a IA pode ver
        linhas.append(f"- inadimplência média: {_pct(kpis.get('taxa_inadimplencia'))}")

    if grupos_materia:
        linhas += ["", f"MATÉRIAS COM MAIOR PROPORÇÃO DE ALUNOS EM RISCO (top {TOP_MATERIAS}):"]
        for g in grupos_materia[:TOP_MATERIAS]:
            linhas.append(
                f"- {g['disciplina']} ({g['curso_nome'].replace('_', ' ')}), prof. {g['docente']}: "
                f"{g['alunos']} alunos, média {g['media'] if g['media'] is not None else 'n/d'}, "
                f"frequência {_pct(g['frequencia'])}, {g['criticos']} críticos, "
                f"{g['em_risco']} em risco")

    piores = sorted((r for r in resultados if r["classificacao"] != "regular"),
                    key=lambda r: -r["score"])[:TOP_ALUNOS]
    if piores:
        linhas += ["", f"ALUNOS MAIS PREOCUPANTES (top {len(piores)} por score):"]
        for r in piores:
            linhas.append(
                f"- {r['nome']} | {r['curso'].replace('_', ' ')}, {r['periodo']}º período | "
                f"score {r['score']:.2f} ({r['classificacao']}, {r['prob_reprovacao'] * 100:.0f}% de chance de reprovar"
            f"{', já reprovado' if r['reprovacao_certa'] else ''}) | principal fator: "
                f"{r['motivo_principal']} | hipótese: {r['diagnostico'] or 'sem hipótese'}")
    return "\n".join(linhas)


def montar_prompt(resumo):
    return (
        "Com base nos dados abaixo, escreva um relatório conversacional para quem acompanha "
        "esses alunos. Estrutura sugerida, em parágrafos corridos: (1) um panorama geral da "
        "situação; (2) os pontos que mais chamam atenção, citando matérias e alunos pelo nome "
        "quando fizer sentido; (3) padrões que se repetem entre os alunos em risco; "
        "(4) três ou quatro sugestões práticas de ação. Termine lembrando, em uma frase, que as "
        "causas são hipóteses a confirmar conversando com os alunos. "
        "Tamanho: no máximo umas 350 palavras.\n\n=== DADOS ===\n" + resumo
    )


def gerar_relatorio(resumo):
    """Envia o resumo ao Ollama e devolve o texto. Levanta IAIndisponivel com mensagem amigável."""
    corpo = {
        "model": OLLAMA_MODELO,
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 8192},
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": montar_prompt(resumo)},
        ],
    }
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/chat", json=corpo, timeout=OLLAMA_TIMEOUT)
    except requests.ConnectionError:
        raise IAIndisponivel("Não consegui falar com o Ollama. Confira se ele está rodando "
                             "(comando: ollama serve).")
    except requests.Timeout:
        raise IAIndisponivel("O Ollama demorou demais para responder. Tente de novo ou use um "
                             "modelo menor.")
    if resp.status_code == 404:
        raise IAIndisponivel(f"O modelo '{OLLAMA_MODELO}' não está instalado no Ollama "
                             f"(comando: ollama pull {OLLAMA_MODELO}).")
    if not resp.ok:
        raise IAIndisponivel(f"O Ollama respondeu com erro (HTTP {resp.status_code}).")
    try:
        texto = resp.json()["message"]["content"].strip()
    except (ValueError, KeyError, TypeError, AttributeError):
        raise IAIndisponivel("Resposta inesperada do Ollama.")
    if not texto:
        raise IAIndisponivel("O Ollama devolveu uma resposta vazia. Tente de novo.")
    return texto
