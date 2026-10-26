# Banco de DADOS (predição). Não tem usuário, senha nem permissão: isso mora no acesso.db.
# O vínculo com o acesso.db é feito por CÓDIGO de negócio (curso.codigo, docente.codigo_docente),
# nunca por id autoincrement, porque os ids mudam quando os dados reais entrarem.
SCHEMA_DADOS = """
CREATE TABLE curso (
    id_curso INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,   -- chave de negócio (ex.: MEDICINA), usada pelo acesso.db
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'regular'
        CHECK (tipo IN ('regular', 'categoria_administrativa', 'modalidade_academica'))
);

CREATE TABLE docente (
    codigo_docente TEXT PRIMARY KEY,   -- chave de negócio (ex.: DOC0001)
    nome TEXT NOT NULL
);

CREATE TABLE aluno (
    id_aluno INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    id_curso INTEGER NOT NULL REFERENCES curso(id_curso),
    periodo INTEGER NOT NULL,
    telefone TEXT NOT NULL,
    email TEXT NOT NULL
);

CREATE TABLE turma (
    id_turma INTEGER PRIMARY KEY AUTOINCREMENT,
    id_curso INTEGER NOT NULL REFERENCES curso(id_curso),
    disciplina TEXT NOT NULL,
    codigo_docente TEXT NOT NULL REFERENCES docente(codigo_docente)
);

CREATE TABLE matricula (
    id_matricula INTEGER PRIMARY KEY AUTOINCREMENT,
    id_aluno INTEGER NOT NULL REFERENCES aluno(id_aluno),
    id_turma INTEGER NOT NULL REFERENCES turma(id_turma)
);

CREATE TABLE registro_academico (
    id_registro INTEGER PRIMARY KEY AUTOINCREMENT,
    id_matricula INTEGER NOT NULL REFERENCES matricula(id_matricula),
    nota REAL NOT NULL,
    data TEXT NOT NULL
);

CREATE TABLE frequencia (
    id_frequencia INTEGER PRIMARY KEY AUTOINCREMENT,
    id_matricula INTEGER NOT NULL REFERENCES matricula(id_matricula),
    presenca INTEGER NOT NULL,  -- 1 = presente, 0 = ausente
    data TEXT NOT NULL
);

CREATE TABLE financeiro (
    id_boleto INTEGER PRIMARY KEY AUTOINCREMENT,
    id_aluno INTEGER NOT NULL REFERENCES aluno(id_aluno),
    status TEXT NOT NULL CHECK (status IN ('pago', 'pendente')),
    data TEXT NOT NULL
);
"""
