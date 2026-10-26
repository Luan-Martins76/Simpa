"""
Teste de isolamento do login/permissões. Rode da raiz do projeto:

    python testes/testar_acesso.py

Usa os bancos gerados (dados.db / acesso.db) e confere, via SQL direto, que cada perfil
recebe da API exatamente (e só) os alunos do seu escopo.

Seguro de rodar: o teste trabalha numa CÓPIA TEMPORÁRIA do acesso.db (ele apaga linhas de
log_acesso, desativa contas e mexe em vínculos para testar bloqueio e "falha fechada") e o
dados.db é aberto só para leitura. Os seus arquivos originais não são alterados.
"""
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dados_prototipo.config import DB_ACESSO_PATH, DB_DADOS_PATH, SENHA_DEMO  # noqa: E402
from app import criar_app  # noqa: E402

_tmp = tempfile.mkdtemp(prefix="simpa_teste_")
_acesso_copia = os.path.join(_tmp, "acesso.db")
shutil.copy(DB_ACESSO_PATH, _acesso_copia)

app = criar_app()
app.config["DB_ACESSO_PATH"] = _acesso_copia          # o app passa a usar a cópia
dados = sqlite3.connect(f"file:{DB_DADOS_PATH}?mode=ro", uri=True)
acesso = sqlite3.connect(_acesso_copia)
falhas = []


def ok(cond, msg):
    print(("  ok   " if cond else "  FALHA ") + msg)
    if not cond:
        falhas.append(msg)


def csrf_de(html):
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def entrar(login, senha=SENHA_DEMO):
    c = app.test_client()
    tok = csrf_de(c.get("/login").get_data(as_text=True))
    r = c.post("/login", data={"login": login, "senha": senha, "csrf": tok})
    return c, r


def todos_os_alunos(c, **params):
    """Percorre todas as páginas de /api/risco e devolve (total, itens)."""
    itens, pagina = [], 1
    while True:
        d = c.get("/api/risco", query_string={"pagina": pagina, **params}).get_json()
        itens += d["itens"]
        if pagina >= d["paginas"]:
            return d, itens
        pagina += 1


def alunos_sql(cursos=None, docente=None):
    if docente:
        q = ("SELECT DISTINCT a.id_aluno, a.nome, c.codigo FROM aluno a JOIN curso c ON c.id_curso=a.id_curso "
             "JOIN matricula m ON m.id_aluno=a.id_aluno JOIN turma t ON t.id_turma=m.id_turma "
             "WHERE t.codigo_docente=?")
        # por id_aluno: nomes se repetem (homônimos), então DISTINCT por nome subcontaria
        return sorted((n, c) for _, n, c in dados.execute(q, (docente,)).fetchall())
    q = "SELECT a.nome, c.codigo FROM aluno a JOIN curso c ON c.id_curso=a.id_curso"
    rows = dados.execute(q).fetchall()
    return sorted(r for r in rows if cursos is None or r[1] in cursos)


def cursos_de(sql, *a):
    return {r[0] for r in acesso.execute(sql, a)}


print("\n[1] Sem login, nada de dados")
c = app.test_client()
ok(c.get("/").status_code == 302 and "/login" in c.get("/").headers["Location"], "/ redireciona para /login")
for rota in ("/api/me", "/api/risco", "/api/filtros", "/api/agrupado", "/api/risco.csv"):
    ok(c.get(rota).status_code == 401, f"{rota} -> 401")

print("\n[2] Credenciais")
c, r = entrar("dev", "senha-errada")
ok(r.status_code == 401 and "inválidos" in r.get_data(as_text=True), "senha errada -> 401 + mensagem genérica")
c, r = entrar("nao_existe")
ok(r.status_code == 401 and "inválidos" in r.get_data(as_text=True), "login inexistente -> mesma mensagem")
c = app.test_client()
r = c.post("/login", data={"login": "dev", "senha": SENHA_DEMO, "csrf": "forjado"})
ok(r.status_code == 400 and c.get("/api/me").status_code == 401, "POST /login sem CSRF válido é recusado")
c, r = entrar("dev")
ok(r.status_code == 302 and c.get("/api/me").status_code == 200, "login correto entra")
ok("no-store" in c.get("/api/risco").headers.get("Cache-Control", ""), "API com Cache-Control: no-store")
tok = c.get("/api/me").get_json()["csrf"]
ok(c.post("/logout").status_code == 400, "logout sem CSRF é recusado")
ok(c.post("/logout", headers={"X-CSRF-Token": tok}).status_code == 204 and c.get("/api/me").status_code == 401,
   "logout com CSRF encerra a sessão")

print("\n[3] Bloqueio após 5 falhas")
acesso.execute("DELETE FROM log_acesso WHERE login_tentado='coord_direito'")
acesso.commit()
for _ in range(5):
    entrar("coord_direito", "x")
c, r = entrar("coord_direito", SENHA_DEMO)
ok(r.status_code == 429, "6ª tentativa (mesmo com senha certa) -> 429")
acesso.execute("DELETE FROM log_acesso WHERE login_tentado='coord_direito'")
acesso.commit()
c, r = entrar("coord_direito")
ok(r.status_code == 302, "sem falhas recentes, entra normal")

print("\n[4] Escopo por perfil (API x SQL)")
total_geral = dados.execute("SELECT COUNT(*) FROM aluno").fetchone()[0]

c, _ = entrar("dev")
d, itens = todos_os_alunos(c)
ok(d["total"] == total_geral, f"admin vê todos os alunos ({d['total']})")
ok(any(f["fator"] == "inadimplencia" for f in itens[0]["fatores"]), "admin recebe o fator financeiro")
c, _ = entrar("reitor_geral")
ok(todos_os_alunos(c)[0]["total"] == total_geral, "reitor geral vê todos")

c, _ = entrar("reitor_saude")
cs = cursos_de("SELECT sc.codigo_curso FROM secretaria_curso sc JOIN secretaria s USING(id_secretaria) "
               "JOIN setor st ON st.id_setor=s.id_setor WHERE st.chave='saude'")
d, itens = todos_os_alunos(c)
ok(sorted((i["nome"], i["curso"]) for i in itens) == alunos_sql(cs), f"reitor de setor (saúde): {d['total']} alunos, só dos cursos do setor")

c, _ = entrar("sec_ciencias_saude")
d, itens = todos_os_alunos(c)
ok(sorted((i["nome"], i["curso"]) for i in itens) == alunos_sql(cs), "secretário da saúde: mesmos alunos do setor")
ok({x["codigo"] for x in c.get("/api/filtros").get_json()["cursos"]} <= cs, "filtros do secretário só listam cursos dele")

c, _ = entrar("sec_gestao_negocios")
d, itens = todos_os_alunos(c)
cs_g = cursos_de("SELECT codigo_curso FROM secretaria_curso sc JOIN secretaria s USING(id_secretaria) WHERE s.chave='gestao_negocios'")
ok({i["curso"] for i in itens} <= cs_g and d["total"] == len(alunos_sql(cs_g)), "secretário de gestão não vê a saúde")
d2 = c.get("/api/risco", query_string={"curso": "MEDICINA"}).get_json()
ok(d2["total"] == 0, "pedir ?curso=MEDICINA fora do escopo -> 0 resultados")
nomes_saude = {r[0] for r in alunos_sql(cs)}
d3 = c.get("/api/risco", query_string={"q": next(iter(nomes_saude))}).get_json()
ok(all(i["curso"] in cs_g for i in d3["itens"]), "busca por nome não vaza aluno de outro setor")

c, _ = entrar("coord_direito")
d, itens = todos_os_alunos(c)
ok(sorted((i["nome"], i["curso"]) for i in itens) == alunos_sql({"DIREITO"}) and d["total"] > 0,
   f"coordenador de Direito: {d['total']} alunos, só DIREITO")
ok(c.get("/api/agrupado").get_json()["total"] > 0, "agrupado por matéria funciona")
ag = c.get("/api/agrupado", query_string={"modo": "professor"}).get_json()
docs_curso = {r[0] for r in dados.execute(
    "SELECT d.nome FROM turma t JOIN curso c USING(id_curso) JOIN docente d USING(codigo_docente) WHERE c.codigo='DIREITO'")}
ok({i["docente"] for i in ag["itens"]} <= docs_curso, "agrupado por professor só traz professores do curso")
filt = c.get("/api/filtros").get_json()
ok([x["codigo"] for x in filt["cursos"]] == ["DIREITO"] and all(m["curso"] == "DIREITO" for m in filt["materias"]),
   "filtros do coordenador: só DIREITO")

print("\n[5] Professor: só as turmas dele, sem financeiro")
amostra = [r[0] for r in dados.execute(
    "SELECT codigo_docente FROM docente ORDER BY codigo_docente LIMIT 3")] + ["DOC0100", "DOC0250"]
for cod in amostra:
    c, _ = entrar("prof_" + cod.removeprefix("DOC"))
    d, itens = todos_os_alunos(c)
    esperado = alunos_sql(docente=cod)
    ok(sorted((i["nome"], i["curso"]) for i in itens) == esperado and d["total"] == len(esperado),
       f"{cod}: {d['total']} alunos = matriculados nas turmas dele")
    fatores = {f["fator"] for i in itens for f in i["fatores"]}
    ok("inadimplencia" not in fatores, f"{cod}: sem fator de inadimplência")
    ok(d["kpis"]["taxa_inadimplencia"] is None and d["visao"]["financeiro"] is False, f"{cod}: KPI financeiro oculto")
    docs = {m["docente"] for i in itens for m in i["materias"]}
    ok(len(docs) == 1, f"{cod}: matérias detalhadas só da própria turma ({len(docs)} docente)")
    ok(abs(sum(d["pesos"].values()) - 1) < 1e-3 and "w4_inadimplencia" not in d["pesos"], f"{cod}: pesos renormalizados, sem w4")
    txt = " ".join(i["diagnostico"] + i["motivo_principal"] for i in itens).lower()
    ok("boleto" not in txt and "financ" not in txt, f"{cod}: nenhum texto menciona financeiro")
    ok(c.get("/api/agrupado", query_string={"modo": "professor"}).get_json()["total"] == 1, f"{cod}: agrupado por professor = só ele")
ok("e-mail" not in str(itens[0]) and "telefone" not in str(itens[0]), "payload não traz contato do aluno")

print("\n[6] Conta desativada perde acesso na hora")
c, _ = entrar("prof_0001")
ok(c.get("/api/risco").status_code == 200, "prof_0001 logado")
acesso.execute("UPDATE usuario_sistema SET ativo=0 WHERE login='prof_0001'")
acesso.commit()
ok(c.get("/api/risco").status_code == 401, "após ativo=0, a sessão aberta deixa de valer")
c2, r = entrar("prof_0001")
ok(r.status_code == 401, "e não consegue entrar de novo")
acesso.execute("UPDATE usuario_sistema SET ativo=1 WHERE login='prof_0001'")
acesso.execute("DELETE FROM log_acesso WHERE login_tentado='prof_0001'")
acesso.commit()

print("\n[7] Falha fechada")
acesso.execute("DELETE FROM coordenacao_curso WHERE id_usuario=(SELECT id_usuario FROM usuario_sistema WHERE login='coord_direito')")
acesso.commit()
c, _ = entrar("coord_direito")
ok(todos_os_alunos(c)[0]["total"] == 0, "coordenador sem curso vinculado não vê ninguém")
acesso.execute("INSERT INTO coordenacao_curso (id_usuario, codigo_curso) "
               "SELECT id_usuario, 'DIREITO' FROM usuario_sistema WHERE login='coord_direito'")
acesso.commit()

print("\n[8] CSV respeita o escopo")
c, _ = entrar("coord_direito")
linhas = c.get("/api/risco.csv").get_data(as_text=True).strip().splitlines()
ok(len(linhas) - 1 == len(alunos_sql({"DIREITO"})), f"CSV do coordenador: {len(linhas)-1} linhas = alunos de Direito")

print("\n[9] Latência (após cache aquecido)")
c, _ = entrar("dev")
c.get("/api/risco")
t0 = time.perf_counter()
for _ in range(5):
    c.get("/api/risco", query_string={"classificacao": "risco critico", "pagina": 2})
admin_ms = (time.perf_counter() - t0) / 5 * 1000
ok(admin_ms < 500, f"admin (13.000 alunos): {admin_ms:.0f} ms por requisição")
c, _ = entrar("prof_0200")
t0 = time.perf_counter()
c.get("/api/risco")
prof_ms = (time.perf_counter() - t0) * 1000
ok(prof_ms < 3000, f"professor, 1ª requisição (calcula a visão dele): {prof_ms:.0f} ms")

shutil.rmtree(_tmp, ignore_errors=True)
print("\n" + ("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S):\n  - " + "\n  - ".join(falhas)))
sys.exit(1 if falhas else 0)
