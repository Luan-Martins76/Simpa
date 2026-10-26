# Banco de ACESSO: quem pode entrar e o que cada um pode ver.
# Referencia os dados só por CÓDIGO (codigo_curso, codigo_docente), sem FK entre arquivos.
# A conferência cruzada fica em funcoes/verificar_consistencia.py.
SCHEMA_ACESSO = """
CREATE TABLE setor (
    id_setor INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL
);

CREATE TABLE secretaria (
    id_secretaria INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    id_setor INTEGER NOT NULL REFERENCES setor(id_setor)
);

-- Cursos de cada secretaria (um curso pertence a no máximo uma secretaria)
CREATE TABLE secretaria_curso (
    id_secretaria INTEGER NOT NULL REFERENCES secretaria(id_secretaria),
    codigo_curso TEXT NOT NULL UNIQUE,
    PRIMARY KEY (id_secretaria, codigo_curso)
);

CREATE TABLE usuario_sistema (
    id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    nome TEXT NOT NULL,
    perfil TEXT NOT NULL CHECK (perfil IN (
        'admin', 'reitor_geral', 'reitor_setor',
        'secretario', 'coordenador', 'professor'
    )),
    id_setor INTEGER REFERENCES setor(id_setor),                 -- só reitor_setor
    id_secretaria INTEGER REFERENCES secretaria(id_secretaria),  -- só secretario
    codigo_docente TEXT,                                         -- só professor
    ativo INTEGER NOT NULL DEFAULT 1,
    -- o escopo tem que ser coerente com o perfil
    CHECK (
        (perfil IN ('admin', 'reitor_geral', 'coordenador')
            AND id_setor IS NULL AND id_secretaria IS NULL AND codigo_docente IS NULL) OR
        (perfil = 'reitor_setor'
            AND id_setor IS NOT NULL AND id_secretaria IS NULL AND codigo_docente IS NULL) OR
        (perfil = 'secretario'
            AND id_secretaria IS NOT NULL AND id_setor IS NULL AND codigo_docente IS NULL) OR
        (perfil = 'professor'
            AND codigo_docente IS NOT NULL AND id_setor IS NULL AND id_secretaria IS NULL)
    )
);

-- No máximo 1 admin e 1 reitor geral (= os 2 acessos globais)
CREATE UNIQUE INDEX ux_acesso_global ON usuario_sistema(perfil)
    WHERE perfil IN ('admin', 'reitor_geral');
-- 1 reitor por setor e 1 secretário por secretaria (= até 2 por setor)
CREATE UNIQUE INDEX ux_reitor_setor ON usuario_sistema(id_setor)
    WHERE perfil = 'reitor_setor';
CREATE UNIQUE INDEX ux_secretario ON usuario_sistema(id_secretaria)
    WHERE perfil = 'secretario';
-- 1 conta por docente
CREATE UNIQUE INDEX ux_professor_docente ON usuario_sistema(codigo_docente)
    WHERE perfil = 'professor';

-- Coordenador pedagógico <-> curso (cada curso tem no máximo 1 coordenador)
CREATE TABLE coordenacao_curso (
    id_usuario INTEGER NOT NULL REFERENCES usuario_sistema(id_usuario),
    codigo_curso TEXT NOT NULL UNIQUE,
    PRIMARY KEY (id_usuario, codigo_curso)
);

-- Auditoria de tentativas de login
CREATE TABLE log_acesso (
    id_log INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario INTEGER REFERENCES usuario_sistema(id_usuario),  -- NULL se o login não existe
    login_tentado TEXT NOT NULL,
    data_hora TEXT NOT NULL,
    sucesso INTEGER NOT NULL
);
"""
