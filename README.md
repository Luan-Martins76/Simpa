# 🎓 SIMPA

**Sistema de Indicador Preditivo de Reprovação Acadêmica**

O SIMPA não espera o semestre acabar para contar quem reprovou. Ele olha só para o que **já aconteceu** até o ciclo escolhido (aulas dadas, notas lançadas, boletos vencidos), projeta o resto do semestre e estima a **chance de cada aluno reprovar enquanto ainda dá tempo de agir**.

Cada pessoa que entra no sistema vê apenas os alunos do seu escopo: do Reitor Geral até o professor de uma única turma.

> ⚠️ **Protótipo.** Os dados são sintéticos (gerados com Faker) e os pesos do score são *placeholders*, pendentes de calibração com a secretaria.

---

## ✨ O que ele faz

- **Predição por ciclo:** o semestre tem 3 ciclos (semanas 5, 10 e 16). O sistema só enxerga o que aconteceu até o fim do ciclo escolhido.
- **Score de risco (0 a 1)** por aluno, com classificação em *regular*, *ponto de atenção* e *risco crítico*.
- **Explicação do score:** mostra o que pesou (frequência, nota, instabilidade, inadimplência) e uma hipótese de causa.
- **Painel por perfil:** cada usuário recebe os dados já filtrados pelo seu escopo no servidor.
- **Gráficos no painel:** histograma das médias e dispersão frequência × nota, com correlação (r), reta de regressão e uma leitura em texto de cada um.
- **Visão agrupada** por matéria ou por professor.
- **Pesos ajustáveis** direto na interface, com recálculo na hora.
- **Exportação em CSV** da seleção atual.
- **Relatório conversacional com IA local** (Ollama): o texto sai de um resumo calculado em Python, então os números não passam pela IA.
- **Backtest:** compara a previsão de cada ciclo com o resultado final do semestre.

---

## 🧠 Como a predição funciona

Um aluno reprova em uma disciplina se tiver **frequência abaixo de 75%** ou **média abaixo de 6,0**. Reprovou em qualquer uma, reprovou no semestre.

| Sinal | Peso padrão | Como é calculado |
|---|---|---|
| `w1_frequencia_invertida` | 0,40 | Probabilidade (binomial) de estourar o limite de faltas nas aulas que ainda faltam. O ritmo de faltas mistura o histórico inteiro com as últimas 4 semanas. |
| `w2_queda_desempenho` | 0,35 | Média parcial, nota ainda necessária e projeção da média final, com tendência de queda quando há 2 ou mais notas. |
| `w3_desvio_padrao` | 0,05 | Instabilidade das notas. |
| `w4_inadimplencia` | 0,20 | Boletos pendentes (sinal de evasão, por isso pesa menos). |

**Score do aluno** = `max(soma ponderada dos sinais, probabilidade de reprovar em alguma disciplina)`

| Classificação | Score |
|---|---|
| 🟢 Regular | abaixo de 0,40 |
| 🟠 Ponto de atenção | 0,40 a 0,65 |
| 🔴 Risco crítico | 0,66 ou mais |

Detalhes que importam:

- **Sinal sem dado sai da conta** e os demais pesos são renormalizados. Ausência de dado não é "sem risco".
- **Reprovação consumada** (faltas acima do limite ou nota necessária maior que 10) vira risco 1. Aí não adianta mais agir, e o valor do sistema está em pegar o aluno antes.
- **Professor não recebe dado financeiro** (privilégio mínimo). Para ele, os 3 pesos acadêmicos são renormalizados para somar 1.

---

## 👥 Perfis e permissões

| Perfil | O que enxerga |
|---|---|
| `admin` | Todos os cursos |
| `reitor_geral` | Todos os cursos |
| `reitor_setor` | Cursos de todas as secretarias do seu setor |
| `secretario` | Cursos da sua secretaria |
| `coordenador` | Os cursos que coordena |
| `professor` | Só os alunos das suas turmas, e só o que acontece nelas (sem financeiro) |

Se o perfil for desconhecido ou o vínculo estiver vazio, o escopo fica vazio (falha fechada: não vê nada).

---

## 🚀 Como rodar

**Pré-requisitos:** Python 3.9+ (testado com 3.12). O Ollama só é necessário para o relatório com IA.

```bash
# 1. Instalar as dependências
pip install -r requirements.txt

# 2. Gerar os bancos de demonstração (só uma vez)
python -m dados_prototipo.gerar_simpa_db

# 3. Subir o servidor
python app.py
```

Abra **http://127.0.0.1:5000** e entre com um dos usuários abaixo.

O passo 2 cria `dados.db` (13.000 alunos fictícios) e `acesso.db` em `dados_prototipo/banco_dados/`, e ainda confere a consistência entre os dois. Se os arquivos já existirem, nada é sobrescrito: apague-os para recriar do zero.

### 🔑 Usuários de demonstração

**Senha de todos: `simpa123`**

| Perfil | Login |
|---|---|
| Administrador | `dev` |
| Reitor Geral | `reitor_geral` |
| Reitor de setor | `reitor_saude`, `reitor_tecnologia`, `reitor_gestao`, `reitor_juridico`, `reitor_agrarias`, `reitor_comunicacao`, `reitor_educacao`... |
| Secretário | `sec_<chave_da_secretaria>`, ex.: `sec_ciencias_saude` |
| Coordenador | `coord_<curso>`, ex.: `coord_medicina`, `coord_engenharia_civil` |
| Professor | `prof_0001`, `prof_0002`... (um por docente) |

> Os nomes das pessoas são sorteados pelo Faker, mas os **logins** são fixos.

---

## 🤖 Relatório com IA (Ollama)

O botão **Gerar relatório com IA** monta um resumo compacto da seleção atual (totais, médias, matérias mais críticas e os 15 alunos mais preocupantes), manda para o Ollama e devolve um texto em português. O resumo já respeita o escopo do usuário, e o professor nunca envia dado financeiro para a IA.

```bash
ollama pull gemma3:4b     # modelo padrão do código
ollama serve              # deixe rodando
```

Só uma geração por vez é permitida (o Ollama local é lento). Se o Ollama estiver fora do ar ou o modelo não estiver instalado, a tela mostra uma mensagem explicando.

---

## ⚙️ Variáveis de ambiente

| Variável | Padrão | Para que serve |
|---|---|---|
| `SIMPA_SECRET_KEY` | aleatória a cada start | Chave que assina o cookie de sessão. **Defina uma fixa em produção**, senão todo mundo é deslogado a cada reinício. |
| `SIMPA_COOKIE_SECURE` | desligado | Use `1` quando servir por HTTPS. |
| `SIMPA_PORT` | `5000` | Porta do servidor. |
| `SIMPA_OLLAMA_URL` | `http://127.0.0.1:11434` | Endereço do Ollama. |
| `SIMPA_OLLAMA_MODEL` | `gemma3:4b` | Modelo usado no relatório. |
| `SIMPA_OLLAMA_TIMEOUT` | `180` | Segundos de espera pela resposta. |

Exemplo:

```bash
SIMPA_SECRET_KEY="troque-por-algo-longo-e-secreto" SIMPA_PORT=8000 python app.py
```

---

## 🔌 API

Todas as rotas exigem sessão ativa. As de dados já devolvem tudo filtrado pelo escopo do usuário.

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/me` | Dados do usuário logado, escopo, ciclos e token CSRF |
| `GET` | `/api/filtros` | Cursos e matérias visíveis para o usuário |
| `GET` | `/api/risco` | Lista paginada (10 por página) com contagens por classificação e KPIs |
| `GET` | `/api/agrupado` | Agregação por `modo=materia` ou `modo=professor` |
| `GET` | `/api/indicadores` | Estatística descritiva, histograma e dispersão frequência × nota (com r e reta de regressão) da mesma seleção |
| `GET` | `/api/risco.csv` | Exporta a seleção atual em CSV |
| `POST` | `/api/relatorio` | Gera o relatório com IA (exige header `X-CSRF-Token`) |
| `GET/POST` | `/login` | Tela e envio do login |
| `POST` | `/logout` | Encerra a sessão |

**Parâmetros de `/api/risco`, `/api/indicadores`, `/api/risco.csv` e `/api/relatorio`:**

| Parâmetro | Exemplo | Descrição |
|---|---|---|
| `ciclo` | `1`, `2` ou `3` | Ciclo do semestre (valor inválido cai no padrão, 2) |
| `q` | `maria` | Busca por nome |
| `curso` | `MEDICINA` | Filtra por código do curso |
| `classificacao` | `risco critico` | Filtra por faixa de risco |
| `mat` | `42` | Filtra por id da turma/matéria |
| `pagina` | `3` | Página (só em `/api/risco`) |
| `pesos` | `{"w1_frequencia_invertida":0.5}` | Pesos em JSON; o que faltar usa o padrão |

---

## 🖥️ Linha de comando

A predição também roda sem o servidor:

```bash
python predicao/simpa_predicao.py                  # relatório no console (ciclo padrão)
python predicao/simpa_predicao.py --ciclo 1        # como o sistema enxergaria no fim do ciclo 1
python predicao/simpa_predicao.py --top 20         # só os 20 de maior risco
python predicao/simpa_predicao.py --csv risco.csv  # exporta CSV
python predicao/simpa_predicao.py --backtest       # previsão de cada ciclo x resultado final
```

---

## 🗂️ Estrutura

```
.
├── app.py                      # servidor Flask: páginas e API
├── requirements.txt
├── login/
│   ├── auth.py                 # autenticação, hash de senha e bloqueio por tentativas
│   ├── escopo.py               # traduz perfil -> o que a pessoa pode ver
│   └── rotas.py                # /login, /logout, CSRF e decoradores
├── predicao/
│   └── simpa_predicao.py       # modelo de risco, KPIs, agrupamentos, CSV e backtest
├── ia/
│   └── relatorio_ia.py         # resumo + relatório conversacional via Ollama
├── templates/
│   ├── index.html              # painel (front)
│   └── login.html
└── dados_prototipo/
    ├── config.py               # semestre, ciclos, regras de reprovação, senha demo
    ├── gerar_simpa_db.py       # gera dados.db e acesso.db
    ├── banco_dados/            # (gerado) dados.db e acesso.db
    ├── dicionarios/            # cursos, disciplinas, schemas, arquétipos, estrutura da universidade
    └── funcoes/                # geradores de nota, presença, boleto, acesso e checagem de consistência
```

### Dois bancos, de propósito

| Banco | Conteúdo |
|---|---|
| `dados.db` | Alunos, turmas, matrículas, notas, frequência e financeiro (lido pela predição, **somente leitura**) |
| `acesso.db` | Usuários, perfis, permissões e log de tentativas de login |

Os dois se ligam por **código de negócio** (`codigo_curso`, `codigo_docente`), nunca por id autoincrementado, porque os ids mudam quando os dados reais entrarem.

---

## 🔒 Segurança

- Senhas guardadas só como **hash** (Werkzeug).
- **Mensagem de erro única** para login inexistente, senha errada e conta inativa, com tempo de resposta equalizado.
- **Bloqueio temporário:** 5 falhas em 10 minutos.
- Sessão nova a cada login (evita fixação de sessão) e **proteção CSRF** nas rotas `POST`.
- Cookie `HttpOnly` e `SameSite=Lax` (e `Secure` com `SIMPA_COOKIE_SECURE=1`).
- Conta desativada **perde o acesso na hora**: o usuário é relido do banco a cada requisição.
- Dado de aluno com `Cache-Control: no-store`.
- **Toda permissão é validada no servidor.** O front só esconde ou mostra coisas por conveniência.

---

## 🛠️ Ajustes rápidos

Tudo fica em `dados_prototipo/config.py`:

| Constante | Valor | O que muda |
|---|---|---|
| `N_ALUNOS` | 13000 | Quantidade de alunos gerados |
| `FREQ_MINIMA` | 0.75 | Frequência mínima para aprovar |
| `MEDIA_MINIMA` | 6.0 | Média mínima para aprovar |
| `CICLOS_FIM_SEMANA` | (5, 10, 16) | Semana em que cada ciclo termina |
| `CICLO_PADRAO` | 2 | Ciclo mostrado ao abrir o sistema |
| `JANELA_RECENTE_DIAS` | 28 | Janela do ritmo recente de faltas |

Depois de mudar dados ou regras de geração, apague os `.db` em `dados_prototipo/banco_dados/` e rode o passo 2 de novo.

---

## 📌 Próximos passos

- Calibrar os pesos e os parâmetros do modelo com a secretaria e dados reais.
- Trocar o gerador de dados sintéticos pela integração com o cadastro real.
- Rodar o backtest no fim de cada período para medir a qualidade da previsão.
