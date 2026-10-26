"""Gera o dados.db (dados acadêmicos usados pela predição). Sem usuários/senhas."""
import math
import os
import random
import sqlite3

from faker import Faker
from datetime import timedelta

from dados_prototipo.dicionarios.cursos import CURSOS
from dados_prototipo.dicionarios.DISCIPLINAS_POR_CURSO import DISCIPLINAS_POR_CURSO
from dados_prototipo.dicionarios.ESTRUTURA_UNIVERSIDADE import UNIVERSIDADE
from dados_prototipo.dicionarios.SCHEMA_DADOS import SCHEMA_DADOS

from dados_prototipo.dicionarios.ARQUETIPOS import PROB_RECUPERA
from dados_prototipo.funcoes.cursos_regulares import cursos_regulares
from dados_prototipo.funcoes.gerar_nota import gerar_nota
from dados_prototipo.funcoes.gerar_presenca import gerar_presenca
from dados_prototipo.funcoes.gerar_status_boleto import gerar_status_boleto
from dados_prototipo.funcoes.sortear_arquetipo import sortear_arquetipo

from dados_prototipo.config import (
    DB_DADOS_PATH, N_ALUNOS, N_AVALIACOES, N_MESES_FINANCEIRO, N_SEMANAS,
    SEMESTRE_INICIO, TURMAS_POR_PROFESSOR,
)

random.seed(42)
fake = Faker("pt_BR")
Faker.seed(42)


def gerar_banco():
    # Roda uma vez só: se o arquivo já existe, assume que o banco já foi
    # gerado nesta máquina e não sobrescreve.
    if os.path.exists(DB_DADOS_PATH):
        print(f"[dados] Já existe em: {DB_DADOS_PATH}")
        print("[dados] Nada foi gerado. Apague o arquivo se quiser recriar do zero.")
        return False

    os.makedirs(os.path.dirname(DB_DADOS_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_DADOS_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    cur.executescript(SCHEMA_DADOS)

    # Curso (o codigo é a chave que o acesso.db usa; nome = codigo por enquanto)
    curso_ids = {}
    for codigo in CURSOS:
        estrutura = UNIVERSIDADE["estruturas_academicas"].get(codigo)
        tipo = estrutura["tipo"] if estrutura else "regular"
        cur.execute("INSERT INTO curso (codigo, nome, tipo) VALUES (?, ?, ?)", (codigo, codigo, tipo))
        curso_ids[codigo] = cur.lastrowid

    # Docente + Turma: docentes do curso em rodízio entre as disciplinas
    turma_ids = {}  # (curso, disciplina) -> id_turma
    n_docente = 0
    for curso_nome, disciplinas_dict in DISCIPLINAS_POR_CURSO.items():
        disciplinas = disciplinas_dict.get("disciplina_online", []) + disciplinas_dict.get("disciplina_presenciais", [])
        if not disciplinas:
            continue
        n_prof = max(1, math.ceil(len(disciplinas) / TURMAS_POR_PROFESSOR))
        codigos_docentes = []
        for _ in range(n_prof):
            n_docente += 1
            codigo_docente = f"DOC{n_docente:04d}"
            cur.execute("INSERT INTO docente (codigo_docente, nome) VALUES (?, ?)", (codigo_docente, fake.name()))
            codigos_docentes.append(codigo_docente)
        for i, disciplina in enumerate(disciplinas):
            cur.execute(
                "INSERT INTO turma (id_curso, disciplina, codigo_docente) VALUES (?, ?, ?)",
                (curso_ids[curso_nome], disciplina, codigos_docentes[i % n_prof]),
            )
            turma_ids[(curso_nome, disciplina)] = cur.lastrowid

    # Aluno + arquétipo (mantido só em memória, não é campo do schema).
    # Alunos só nascem em cursos regulares: GRADUACAO e DISCIPLINAS_100%ON-LINE
    # não têm secretaria, então um aluno ali ficaria invisível pra todo mundo.
    regulares = cursos_regulares()
    alunos = []  # (id_aluno, curso_nome, arquetipo, recupera, nivel)
    for _ in range(N_ALUNOS):
        curso_nome = random.choice(regulares)
        nome = fake.name()
        periodo = random.randint(1, 8)
        telefone = fake.phone_number()
        email = fake.unique.email()
        cur.execute(
            "INSERT INTO aluno (nome, id_curso, periodo, telefone, email) VALUES (?, ?, ?, ?, ?)",
            (nome, curso_ids[curso_nome], periodo, telefone, email),
        )
        arquetipo = sortear_arquetipo()
        recupera = arquetipo in ("risco_academico", "risco_misto") and random.random() < PROB_RECUPERA
        nivel = random.gauss(0, 0.8)     # aluno naturalmente mais forte ou mais fraco
        alunos.append((cur.lastrowid, curso_nome, arquetipo, recupera, nivel))

    # Matricula + Registro Acadêmico + Frequência
    for id_aluno, curso_nome, arquetipo, recupera, nivel in alunos:
        disciplinas_curso = (
            DISCIPLINAS_POR_CURSO[curso_nome].get("disciplina_online", [])
            + DISCIPLINAS_POR_CURSO[curso_nome].get("disciplina_presenciais", [])
        )
        if len(disciplinas_curso) < 3:
            print(f"Aviso: curso '{curso_nome}' tem só {len(disciplinas_curso)} disciplina(s) cadastrada(s), pulando aluno {id_aluno}.")
            continue
        n_disciplinas = random.randint(3, min(6, len(disciplinas_curso)))
        disciplinas_aluno = random.sample(disciplinas_curso, n_disciplinas)

        for disciplina in disciplinas_aluno:
            id_turma = turma_ids[(curso_nome, disciplina)]
            cur.execute("INSERT INTO matricula (id_aluno, id_turma) VALUES (?, ?)", (id_aluno, id_turma))
            id_matricula = cur.lastrowid

            # imprevistos que acontecem ate com aluno estavel: uma prova ruim e/ou um bloco de faltas
            prova_ruim = random.randrange(N_AVALIACOES) if random.random() < 0.10 else None
            bloco = None
            if random.random() < 0.12:
                ini = random.randint(0, N_SEMANAS - 3)
                bloco = (ini, ini + random.randint(1, 2))

            for i in range(N_AVALIACOES):
                semana_avaliacao = int((i + 1) * N_SEMANAS / N_AVALIACOES) - 1
                data_avaliacao = SEMESTRE_INICIO + timedelta(weeks=semana_avaliacao)
                nota = gerar_nota(semana_avaliacao, N_SEMANAS, arquetipo, recupera, nivel)
                if i == prova_ruim:
                    nota = round(max(nota - random.uniform(2.0, 3.5), 0), 1)
                cur.execute(
                    "INSERT INTO registro_academico (id_matricula, nota, data) VALUES (?, ?, ?)",
                    (id_matricula, nota, data_avaliacao.isoformat()),
                )

            for semana in range(N_SEMANAS):
                data_aula = SEMESTRE_INICIO + timedelta(weeks=semana)
                presenca = gerar_presenca(semana, N_SEMANAS, arquetipo, recupera, bloco)
                cur.execute(
                    "INSERT INTO frequencia (id_matricula, presenca, data) VALUES (?, ?, ?)",
                    (id_matricula, presenca, data_aula.isoformat()),
                )

    # Financeiro: boletos mensais por aluno
    for id_aluno, _, arquetipo, _, _ in alunos:
        for mes in range(N_MESES_FINANCEIRO):
            data_boleto = SEMESTRE_INICIO.replace(day=10) + timedelta(days=30 * mes)
            status = gerar_status_boleto(mes, arquetipo)
            cur.execute(
                "INSERT INTO financeiro (id_aluno, status, data) VALUES (?, ?, ?)",
                (id_aluno, status, data_boleto.isoformat()),
            )

    conn.commit()

    print("[dados] gerado em:", DB_DADOS_PATH)
    for tabela in ["curso", "docente", "aluno", "turma", "matricula",
                   "registro_academico", "frequencia", "financeiro"]:
        cur.execute(f"SELECT COUNT(*) FROM {tabela}")
        print(f"  {tabela:20s} -> {cur.fetchone()[0]} linhas")

    conn.close()
    return True
