
""" 1. Reitor Geral e Administrador do Sistema
Quantidade: até 2 usuários.

Perfis: Reitor Geral e Desenvolvedor Administrador(deixa o nome do usuario de dev de "dev de extremo sucesso" kkkkk meme pessoal).

Permissões: acesso global a todos os cursos, secretarias, coordenadores, professores, alunos e informações institucionais.

Objetivo: permitir a gestão integral da universidade e a administração técnica da plataforma.

2. Secretarias e Reitores de Setor
Quantidade: até 2 usuários por setor.

Perfis: Secretário responsável e Reitor de Setor.

Permissões: acesso restrito aos cursos vinculados ao respectivo setor, incluindo os dados acadêmicos necessários para suas atribuições.

Objetivo: administrar e supervisionar as atividades acadêmicas dentro de sua área de responsabilidade, sem acesso automático aos dados de outros setores.

3. Coordenadores Pedagógicos
Quantidade: conforme a necessidade institucional.

Perfil: Coordenador Pedagógico.

Permissões: acesso exclusivo ao curso sob sua coordenação, incluindo alunos, professores, disciplinas, turmas e demais informações pertinentes.

Objetivo: acompanhar e gerenciar as atividades pedagógicas do curso pelo qual é responsável.

4. Professores
Quantidade: conforme o quadro docente.

Perfil: Professor.

Permissões: acesso exclusivo às disciplinas e turmas nas quais possui vínculo docente, incluindo os dados dos alunos necessários às atividades de ensino.

Objetivo: executar atividades acadêmicas, como consulta às turmas, lançamento de notas e registro de frequência, conforme as permissões concedidas.

Princípios gerais de segurança
Privilégio mínimo: cada usuário terá somente as permissões necessárias para desempenhar suas funções.

Isolamento de dados: usuários de uma secretaria ou setor não poderão consultar informações de outras áreas sem autorização explícita.

Validação no servidor: todas as operações protegidas deverão validar as permissões no backend, independentemente das restrições apresentadas na interface.

Responsabilidade individual: cada usuário deverá possuir sua própria conta, com permissões associadas ao seu perfil e aos seus vínculos institucionais.

Controle de acesso administrativo: os dois acessos globais serão limitados ao Reitor Geral e ao Desenvolvedor Administrador, conforme a política de segurança da plataforma.
GPT FEZ A BOA NESSA DIVISÂO KKK RAPEI SO OS CURSOS... ESSE NEGOCIO DE SECRETARIA NÂO TINHA O CONHECIMENTO

"""

UNIVERSIDADE = {
    "reitor_geral": {
        "nome": "Reitor Geral",
        "acesso": "global",
    },

    "setores": {
        "gestao_negocios": {
            "nome": "Setor de Gestão e Negócios",
            "reitor": "reitor_gestao",
            "secretarias": [
                "gestao_negocios",
            ],
        },

        "juridicas_internacionais": {
            "nome": "Setor de Ciências Jurídicas e Internacionais",
            "reitor": "reitor_juridico",
            "secretarias": [
                "ciencias_juridicas",
            ],
        },

        "saude": {
            "nome": "Setor de Ciências da Saúde",
            "reitor": "reitor_saude",
            "secretarias": [
                "ciencias_saude",
            ],
        },

        "agrarias_veterinarias": {
            "nome": "Setor de Ciências Agrárias e Veterinárias",
            "reitor": "reitor_agrarias",
            "secretarias": [
                "ciencias_agrarias_veterinarias",
            ],
        },

        "engenharias_tecnologia": {
            "nome": "Setor de Engenharias e Tecnologia",
            "reitor": "reitor_tecnologia",
            "secretarias": [
                "engenharias_tecnologia",
            ],
        },

        "comunicacao_design": {
            "nome": "Setor de Comunicação e Design",
            "reitor": "reitor_comunicacao",
            "secretarias": [
                "comunicacao_design",
            ],
        },

        "educacao_desenvolvimento": {
            "nome": "Setor de Educação e Desenvolvimento Humano",
            "reitor": "reitor_educacao",
            "secretarias": [
                "educacao_desenvolvimento",
            ],
        },

        "hospitalidade_bem_estar": {
            "nome": "Setor de Hospitalidade e Bem-Estar",
            "reitor": "reitor_hospitalidade",
            "secretarias": [
                "hospitalidade_estetica",
            ],
        },

        "arquitetura_urbanismo": {
            "nome": "Setor de Arquitetura e Urbanismo",
            "reitor": "reitor_arquitetura",
            "secretarias": [
                "arquitetura_urbanismo",
            ],
        },
    },

    "secretarias": {
        "gestao_negocios": {
            "nome": "Secretaria de Gestão e Negócios",
            "setor": "gestao_negocios",
            "cursos": [
                "ADMINISTRACAO",
                "CIENCIAS_CONTABEIS",
            ],
        },

        "ciencias_juridicas": {
            "nome": "Secretaria de Ciências Jurídicas e Relações Internacionais",
            "setor": "juridicas_internacionais",
            "cursos": [
                "DIREITO",
                "RELACOES_INTERNACIONAIS",
            ],
        },

        "ciencias_saude": {
            "nome": "Secretaria de Ciências da Saúde",
            "setor": "saude",
            "cursos": [
                "ENFERMAGEM",
                "FARMACIA",
                "FISIOTERAPIA",
                "MEDICINA",
                "NUTRICAO",
                "ODONTOLOGIA",
            ],
        },

        "ciencias_agrarias_veterinarias": {
            "nome": "Secretaria de Ciências Agrárias e Veterinárias",
            "setor": "agrarias_veterinarias",
            "cursos": [
                "AGRONOMIA",
                "CIENCIAS_BIOLOGICAS",
                "MEDICINA_VETERINARIA",
            ],
        },

        "engenharias_tecnologia": {
            "nome": "Secretaria de Engenharias e Tecnologia",
            "setor": "engenharias_tecnologia",
            "cursos": [
                "ENGENHARIA_CIVIL",
                "ENGENHARIA_SOFTWARE",
                "ENGENHARIA_ELETRICA",
                "ENGENHARIA_MECANICA",
                "INTELIGENCIA_ARTIFICIAL",
            ],
        },

        "comunicacao_design": {
            "nome": "Secretaria de Comunicação, Design e Artes",
            "setor": "comunicacao_design",
            "cursos": [
                "COMUNICACAO_SOCIAL:PUBLICIDADE_PROPAGANDA",
                "CURSO_SUPERIOR_DE_TECNOLOGIA_EM_DESIGN_GRAFICO",
            ],
        },

        "educacao_desenvolvimento": {
            "nome": "Secretaria de Educação e Desenvolvimento Humano",
            "setor": "educacao_desenvolvimento",
            "cursos": [
                "PEDAGOGIA",
                "PSICOLOGIA",
                "EDUCACAO_FISICA",
            ],
        },

        "hospitalidade_estetica": {
            "nome": "Secretaria de Hospitalidade, Gastronomia e Estética",
            "setor": "hospitalidade_bem_estar",
            "cursos": [
                "CURSO_SUPERIOR_TECNOLOGIA_EM_GASTRONOMIA",
                "CURSO_SUPERIOR_DE_TECNOLOGIA_EM_ESTETICA_COSMETICA",
            ],
        },

        "arquitetura_urbanismo": {
            "nome": "Secretaria de Arquitetura e Urbanismo",
            "setor": "arquitetura_urbanismo",
            "cursos": [
                "ARQUITETURA_URBANISMO",
            ],
        },
    },

    # Estes itens não são cursos regulares.
    "estruturas_academicas": {
        "GRADUACAO": {
            "tipo": "categoria_administrativa",
        },
        "DISCIPLINAS_100%ON-LINE": {
            "tipo": "modalidade_academica",
            "abrangencia": "institucional",
        },
    },
}
