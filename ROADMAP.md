# 🗺️ Roadmap do SIMPA — Projeto Integrador (2º período)

**Onde estamos:** Ciclo 2 (semanas 8 a 13) → **Marco 2: "Plataforma com módulo analítico e visualizações integradas"**
**Nível escolhido:** 2 (predição + recomendação)

**Legenda:** ✅ pronto · 🟡 parcial · ❌ falta

---

## 1. Diagnóstico em uma olhada

O SIMPA está **forte no que é analítico e de segurança** e **fraco em visualização, correlação e álgebra linear**, que são justamente o foco do Marco 2.

> 📝 **Nota:** os professores liberaram o desenvolvimento em **scripts `.py`** (como no 1º período). Por isso a estrutura orientada a objetos e a organização em camadas ficam como **opcionais** neste roadmap (seção 4) e saem do caminho crítico.

| Critério de avaliação (PDF, seção 6) | Situação |
|---|---|
| 1. Modelagem e arquitetura | 🟡 Código funcional em `.py`, liberado pelos professores. Já há separação por pastas (`login/`, `predicao/`, `ia/`). POO é opcional (seção 4). |
| 2. Implementação técnica e funcionamento | 🟡 Funciona bem, mas falta cadastro na API e testes. |
| 3. Estatística e interpretação | 🟡 Modelo preditivo excelente, porém **sem gráficos**, sem correlação e sem álgebra linear explícita. |
| 4. Segurança e robustez | 🟢 Login, perfis, CSRF e bloqueio prontos. Falta log de requisições e validação de dados. |
| 5. Documentação e comunicação | 🟡 README pronto. Faltam UML, dicionário de dados e relatório final. |
| 6. Evolução ao longo dos ciclos | 🟢 Bom, desde que a refatoração apareça no Marco 2. |

---

## 2. Marco 2 — checklist (foco agora)

O Marco 2 avalia **Estatística Aplicada, Álgebra Linear e interpretação analítica**.

| Exigência do PDF | Status | O que existe no código |
|---|---|---|
| Estatística descritiva (média, mediana, variância, desvio-padrão) | ✅ | O painel mostra média, mediana, desvio-padrão e variância das notas (`/api/indicadores`). |
| Métricas acadêmicas relevantes | ✅ | KPIs de média, frequência, inadimplência, reprovação prevista e reprovação consumada, além de agrupamento por matéria e por professor. |
| **Visualizações gráficas** (histograma, dispersão, boxplot, dashboard) | 🟡 | Histograma das médias e dispersão frequência × nota prontos, em SVG, com leitura em texto. Faltam boxplot e série por ciclo (opcionais). |
| **Correlação e regressão linear simples** | ✅ | Correlação de Pearson e reta de mínimos quadrados frequência × nota, com leitura e aviso de que correlação não é causa. |
| **Álgebra linear** | ❌ | Sem numpy e sem matrizes. O score é um produto escalar escrito com laços. |
| Identificação de risco por critérios | ✅ | Score, faixas, probabilidade de reprovar e reprovação consumada. |
| Predição (Nível 2) | ✅ | Binomial para faltas e normal para a média final, com backtest. Vai além do esperado. |
| Recomendação (Nível 2) | 🟡 | O diagnóstico é uma **hipótese de causa**, não uma ação sugerida. A IA escreve sugestões em texto livre, sem regra explícita. |
| Interpretabilidade ("explicar por que apontou risco") | ✅ | `motivo_principal`, `fatores` e `diagnostico` em cada aluno. |
| Integração dos cálculos à API | 🟡 | `/api/risco` e `/api/agrupado` existem. Falta um endpoint de indicadores estatísticos. |
| Relatórios automatizados | ✅ | CSV e relatório com IA. |
| Organização e qualidade dos dados | 🟡 | Dois bancos bem separados, mas **sem validação** (nota fora de 0 a 10, por exemplo) e sem dicionário de dados. |

---

## 3. Plano para fechar o Marco 2

Ordem pensada em valor para a nota. Ajuste as semanas conforme a data real do seu Marco 2.

### 🥇 Prioridade 1 — Visualizações (semana 10 no cronograma)

Hoje é a maior lacuna visível. O PDF recomenda **3 a 6 indicadores**, com título, escala e uma interpretação curta embaixo de cada gráfico.

- ✅ **Histograma** da distribuição das médias dos alunos
- ⬜ **Boxplot** de notas por curso ou disciplina (mostra variabilidade e outliers)
- ✅ **Dispersão frequência × nota**, com a reta de regressão e o valor de r
- ✅ Contagem por classificação (já existe nos chips do topo)
- ⬜ **Série por ciclo do semestre**: como o risco muda do ciclo 1 ao 3
- ✅ Texto de interpretação embaixo de cada gráfico ("o que isto indica?")

Como fazer sem quebrar o resto: novo endpoint `/api/indicadores` devolvendo os dados prontos, e o front desenha com Chart.js (CDN) ou SVG. O PDF também aceita Matplotlib, mas aqui o front já é web.

### 🥈 Prioridade 2 — Correlação e regressão (semana 11)

- ✅ Correlação de Pearson **frequência × nota** (segue os filtros de curso, matéria e ciclo)
- ⬜ Regressão linear simples da **tendência de notas por aluno**: reaproveitar a inclinação que já é calculada em `analisar_nota` e **mostrá-la** (melhorando ou piorando)
- ✅ Texto sobre os **limites** da modelagem, que o PDF pede para discutir na semana 11 (correlação não é causa, poucas avaliações por aluno, dados sintéticos)
- ✅ Mediana e variância nos indicadores descritivos

### 🥉 Prioridade 3 — Álgebra linear (semanas 11 e 12)

O Marco 2 avalia isso explicitamente, e hoje não aparece. A boa notícia é que o conceito já está no código, só não está escrito como matriz.

- ⬜ Representar os sinais como **matriz X (alunos × 4 sinais)** e o score como **`X @ w`** (produto matriz-vetor com o vetor de pesos), no lugar do laço
- ⬜ **Matriz de correlação** entre os sinais (frequência, nota, instabilidade, inadimplência), exibida como mapa de calor
- ⬜ Matriz **aluno × disciplina** de médias, para a comparação por similaridade (ideia citada no PDF para o nível avançado)
- ⬜ Adicionar `numpy` ao `requirements.txt`

### Prioridade 4 — Recomendação de verdade (semana 12)

- ⬜ Classe/regra `Recomendacao` (ação sugerida + motivo + evidência), derivada dos fatores. Exemplo: frequência alta de risco + nota ok → "contato do coordenador para entender conciliação de horários"
- ⬜ Mostrar a recomendação ao lado do diagnóstico, no detalhe do aluno
- ⬜ Opcional: recomendação por **similaridade** (alunos parecidos que se recuperaram)

### Prioridade 5 — Consolidação (semana 13)

- ⬜ `/api/indicadores` documentado e protegido pelo mesmo escopo dos demais
- ⬜ Relatório automático incluindo os indicadores e as interpretações
- ⬜ Ensaio da apresentação (roteiro na seção 7)

---

## 4. Estrutura e POO — opcional (liberado em `.py`)

Como os professores aceitam o formato em scripts `.py`, **nada desta seção bloqueia a nota**. Fica como melhoria se sobrar tempo, em ordem de custo-benefício.

| Item | Status | Observação |
|---|---|---|
| Código organizado em módulos | ✅ | `login/`, `predicao/`, `ia/`, `dados_prototipo/`. Já é separação de responsabilidades. |
| API por recurso (`/alunos`, `/turmas`...) | 🟡 | Hoje são `/api/risco`, `/api/agrupado` etc. Funciona; renomear é cosmético. |
| Cadastro pela API (POST) | ❌ | Os dados entram pelo gerador. Só vale a pena se a demonstração pedir "cadastro". |
| Classes (Aluno, Turma, Risco...) | ❌ | Opcional. |
| UML | ❌ | Ver abaixo: um diagrama simples já cobre. |

Se quiserem um mínimo seguro, sem refatorar nada:

- ⬜ **Um diagrama de classes/módulos simples** descrevendo a arquitetura *como ela é* (módulos e fluxo: login → escopo → predição → API → front). Vale como a "modelagem documentada" e custa pouco
- ⬜ **Duas ou três classes onde fizer sentido**, por exemplo `SinalDeRisco` com quatro tipos (frequência, nota, instabilidade, inadimplência). Os pesos `w1..w4` já se comportam assim

> ⚠️ O texto do PDF ainda cita POO, encapsulamento e UML nos critérios 1 e 2. Como a liberação foi dada pelos professores, vale **confirmar com eles, uma vez, que isso vale também para o SIMPA**, para não ter surpresa na nota do Marco 3.

---

## 5. Ciclo 3 / Marco 3 — o que já adiantar

| Item do Marco 3 | Status | Observação |
|---|---|---|
| API com autenticação e controle de acesso | ✅ | Sessão, perfis, escopo no servidor, CSRF e bloqueio por tentativas. O PDF aceita token simples, então está acima do exigido. |
| Princípios de segurança, proteção de dados | ✅ | Hash de senha, mensagens uniformes e dados mínimos na API (telefone e e-mail não saem). |
| **Logs e monitoramento de requisições** | 🟡 | Só existe `log_acesso` (tentativas de login). Falta log de requisições e de eventos. |
| **Validação rigorosa de entradas** | 🟡 | Pesos e parâmetros são tratados, mas não há validação de dados (nota 0 a 10, presença 0/1, datas). |
| **Testes de unidade** | ❌ | Não existe nenhum teste. |
| Código refatorado e documentado | 🟡 | Comentários bons; a refatoração está na seção 4. |
| Documentação técnica e relatório final | 🟡 | Ver seção 6. |

Ações:

- ⬜ **Logging** com o módulo `logging`: arquivo rotativo com usuário, rota, status e tempo por requisição, mais eventos (login, acesso negado, relatório gerado, CSV exportado)
- ⬜ **Validação e limpeza** (seção 7.3 do PDF): módulo que checa ausentes, nota fora de 0 a 10 e frequência acima de 100%; mais `CHECK` no schema de `dados.db`
- ⬜ **Testes com pytest** em `tests/`: `analisar_frequencia`, `analisar_nota`, `pesos_efetivos`, o isolamento de escopo (professor não vê financeiro, coordenador só vê o curso dele) e o bloqueio de login
- ⬜ **LGPD**: hoje o resumo enviado à IA inclui **nomes de alunos**. O Ollama é local, o que mitiga, mas vale decidir e justificar: mascarar nomes (pseudonimização) ou documentar por que não

---

## 6. Documentação final — checklist (PDF, seção 10)

| # | Item exigido | Status |
|---|---|---|
| 1 | Capa (projeto, integrantes, disciplina, período, data) | ⬜ |
| 2 | Resumo do projeto | 🟡 O README tem a base. |
| 3 | Objetivo e funcionalidades | ✅ Está no README. |
| 4 | Caminho técnico escolhido (Nível 2) e justificativa | ⬜ |
| 5 | Estrutura da lógica (fluxograma ou pseudocódigo) | 🟡 O README explica o modelo, falta o fluxograma. |
| 6 | Tecnologias utilizadas | ✅ `requirements.txt` e README. |
| 7 | Organização do grupo (quem fez o quê) | ⬜ |
| 8 | Desafios enfrentados | ⬜ |
| 9 | Capturas de tela, incluindo exemplos de resposta da IA | ⬜ |
| 10 | Reflexões finais | ⬜ |

Além do documento: ⬜ diagrama simples de arquitetura em `docs/` · ⬜ **dicionário de dados** (campos, significado, valores esperados) · ⬜ registro de decisões (por que esses pesos, por que binomial/normal).

---

## 7. Roteiro da apresentação do Marco 2 (8 a 12 minutos)

O PDF pede: explicar cálculos, justificar indicadores, mostrar como o sistema identifica padrões e a integração análise × arquitetura.

1. **Problema (1 min):** avisar a reprovação antes de acontecer.
2. **Dados e indicadores (2 min):** quais métricas e por quê (média, dispersão, frequência).
3. **Gráficos ao vivo (2 min):** histograma, boxplot e dispersão com a leitura de cada um.
4. **Correlação e regressão (2 min):** o que r mostra e os limites da análise.
5. **Predição de risco (2 min):** abrir um aluno e mostrar o que pesou e a recomendação. Mencionar o backtest como prova de que o modelo funciona.
6. **Arquitetura (1 min):** onde o cálculo vive e como chega à API.
7. **Próximo ciclo (1 min):** segurança, logs e testes.

**Todos os integrantes falam.** Apresentação feita por uma pessoa só é desconsiderada como trabalho de grupo.

---

## 8. Pontos de atenção

- **"Ciclo" tem dois sentidos.** No código, ciclo é a fase do **semestre letivo dos alunos** (semanas 5, 10 e 16). No PDF, ciclo é a fase do **projeto** (semanas 1–7, 8–13, 14–19). Na apresentação, diga sempre "ciclo do semestre" para o primeiro caso, senão o professor se perde.
- **Pesos e limiares são placeholders.** Assuma isso na apresentação e mostre o backtest como método de validação. É mais honesto e mais forte do que defendê-los como definitivos.
- **O modelo é mais sofisticado do que o exigido.** Isso é ótimo, mas o PDF avisa que todos precisam **explicar o que construíram**. Prepare uma explicação simples da binomial e da normal.
- **Dados sintéticos:** deixe claro que os padrões vêm do gerador (arquétipos de aluno), então r e tendências refletem a simulação, não a realidade.
- **Nota total = soma dos três marcos.** Com `.py` liberado, o que mais pesa agora é o Marco 2 (gráficos, estatística, álgebra linear) e, no Marco 3, testes, logs e documentação.

---

## 9. Depois da disciplina (visão de produto)

Já fora do escopo da nota, mas registrado: importar dados reais da secretaria, calibrar pesos com semestres fechados, trocar o proxy de evasão por trancamento real, registrar intervenções e medir se funcionaram, servidor de produção com HTTPS e política de LGPD completa.

---

## ✅ Já está pronto (e acima do exigido)

- Predição por ciclo do semestre com probabilidade de reprovar (binomial + normal) e **backtest**
- Score explicável: fatores, motivo principal e hipótese de causa
- Login com 6 perfis, escopo validado no servidor, CSRF, bloqueio por tentativas e sessão segura
- Painel com filtros, paginação, visão por matéria/professor e pesos ajustáveis
- Relatório conversacional com IA local (Ollama), com resumo calculado em Python
- Exportação em CSV, geração de dados sintéticos e checagem de consistência entre os bancos
- README e `requirements.txt`
