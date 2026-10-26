"""
SIMPA - servidor Flask (login + API de predição por perfil).

    python app.py                      -> http://127.0.0.1:5000

Antes, uma vez:  python -m dados_prototipo.gerar_simpa_db   (gera dados.db e acesso.db)

Variáveis de ambiente:
    SIMPA_SECRET_KEY      chave que assina o cookie de sessão. Em produção, defina uma fixa e secreta;
                          sem ela uma chave aleatória é criada a cada start (todo mundo é deslogado).
    SIMPA_COOKIE_SECURE=1 marca o cookie como Secure (use quando servir por HTTPS).
    SIMPA_PORT            porta (padrão 5000).

Toda a validação de permissão é feita AQUI, no servidor: o front só esconde/mostra coisas por
conveniência. Os dados chegam já filtrados pelo escopo do usuário logado (login/escopo.py).
"""
import io
import os
import secrets
import threading
from datetime import timedelta

from flask import Flask, Response, g, jsonify, request, send_from_directory

from dados_prototipo.config import DB_ACESSO_PATH, DB_DADOS_PATH
from ia import relatorio_ia
from login.escopo import ROTULO_PERFIL
from login.rotas import bp as login_bp, csrf_ok, csrf_token, login_obrigatorio
from predicao import simpa_predicao as predicao

POR_PAGINA = 10 #paginação, na minha cabeça 50 era um numero bom, professor disse 10... Então é 10 o Senior e ele é eu não kkkk
_ia_ocupada = threading.Lock()   # uma geração de relatório por vez (o Ollama local é lento)


def criar_app():
    app = Flask(__name__, static_folder=None)

    chave = os.environ.get("SIMPA_SECRET_KEY")
    if not chave:
        chave = secrets.token_hex(32)
        print("[aviso] SIMPA_SECRET_KEY não definida: usando chave temporária "
              "(as sessões são perdidas quando o servidor reinicia).")
    app.config.update(
        SECRET_KEY=chave,
        DB_ACESSO_PATH=DB_ACESSO_PATH,
        DB_DADOS_PATH=DB_DADOS_PATH,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SIMPA_COOKIE_SECURE") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    app.register_blueprint(login_bp)

    @app.after_request
    def sem_cache(resp):
        # Dado de aluno não deve ficar no cache do navegador (nem voltar no botão "voltar" após o logout).
        if request.path == "/" or request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        return resp

    # ---- seleção de dados já dentro do escopo do usuário ------------------------------------
    def ciclo_pedido():
        """Ciclo do semestre que o usuário quer ver (1 a 3). Valor inválido cai no padrão."""
        return predicao.ciclo_valido(request.args.get("ciclo"))

    def visao(pesos):
        """(resultados do escopo, financeiro?) para o usuário logado, no ciclo pedido."""
        e = g.escopo
        return predicao.resultados_visiveis(DB_DADOS_PATH, pesos, e.cursos_ou_none, e.codigo_docente,
                                            ciclo_pedido())

    def selecionar():
        pesos = predicao.ler_pesos(request.args.get("pesos"))
        q = request.args.get("q", "").strip().lower()
        curso = request.args.get("curso", "")
        cls = request.args.get("classificacao", "")
        mat = request.args.get("mat", type=int)
        todos, financeiro = visao(pesos)
        base = [r for r in todos
                if (not q or q in r["nome"].lower())
                and (not curso or r["curso"] == curso)
                and (mat is None or any(m[0] == mat for m in r["materias"]))]
        itens = [r for r in base if not cls or r["classificacao"] == cls]
        return pesos, financeiro, base, itens

    # páginas e API 
    @app.get("/")
    @login_obrigatorio()
    def index():
        return send_from_directory(os.path.join(app.root_path, "templates"), "index.html")

    @app.get("/api/me")
    @login_obrigatorio(api=True)
    def api_me():
        u, e = g.usuario, g.escopo
        return jsonify(nome=u.nome, login=u.login, perfil=u.perfil,
                       perfil_rotulo=ROTULO_PERFIL.get(u.perfil, u.perfil),
                       escopo=e.descricao, professor=e.e_professor,
                       financeiro=e.ve_financeiro, csrf=csrf_token(),
                       ciclos=predicao.N_CICLOS, ciclo_padrao=predicao.CICLO_PADRAO)

    @app.get("/api/filtros")
    @login_obrigatorio(api=True)
    def api_filtros():
        e = g.escopo
        cursos, materias = predicao.filtros_visiveis(DB_DADOS_PATH, e.cursos_ou_none, e.codigo_docente)
        return jsonify(cursos=cursos, materias=materias)

    @app.get("/api/risco")
    @login_obrigatorio(api=True)
    def api_risco():
        pesos, financeiro, base, itens = selecionar()
        pagina_pedida = request.args.get("pagina", 1, type=int)
        paginas = max(-(-len(itens) // POR_PAGINA), 1)
        pagina = min(max(pagina_pedida, 1), paginas)
        ini = (pagina - 1) * POR_PAGINA
        contagem = {rot: 0 for _, rot, _ in predicao.FAIXAS}
        for r in base:
            contagem[r["classificacao"]] += 1
        turmas = predicao.obter_dados(DB_DADOS_PATH).turmas
        return jsonify(
            total=len(base), contagem=contagem, ciclo=ciclo_pedido(),
            pesos=predicao.pesos_efetivos(pesos, financeiro),
            visao={"financeiro": financeiro},
            pagina=pagina, paginas=paginas, inicio=ini,
            itens=[predicao.serializar(r, turmas) for r in itens[ini:ini + POR_PAGINA]],
            kpis=predicao.calcular_kpis(base, financeiro),
        )

    @app.get("/api/agrupado")
    @login_obrigatorio(api=True)
    def api_agrupado():
        modo = "professor" if request.args.get("modo") == "professor" else "materia"
        curso = request.args.get("curso", "")
        pesos = predicao.ler_pesos(request.args.get("pesos"))
        todos, _ = visao(pesos)
        base = [r for r in todos if not curso or r["curso"] == curso]
        total, linhas = predicao.agrupar(DB_DADOS_PATH, base, modo)
        return jsonify(modo=modo, total=total, itens=linhas)

    @app.get("/api/indicadores")
    @login_obrigatorio(api=True)
    def api_indicadores():
        """Estatística descritiva, histograma e dispersão frequência x nota da MESMA seleção da tabela
        (já dentro do escopo do usuário; o filtro de classificação não entra, para o gráfico mostrar o todo)."""
        return jsonify(predicao.calcular_indicadores(selecionar()[2]))

    @app.get("/api/risco.csv")
    @login_obrigatorio(api=True)
    def api_csv():
        buf = io.StringIO()
        predicao.escrever_csv(selecionar()[3], buf)
        return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=simpa_risco.csv"})

    @app.post("/api/relatorio")
    @login_obrigatorio(api=True)
    def api_relatorio():
        """Gera o relatório conversacional (Ollama) sobre a MESMA seleção do CSV: já filtrada pelo
        escopo do usuário. O front manda os filtros na query string e o token CSRF no header."""
        if not csrf_ok():
            return jsonify(erro="csrf"), 400
        pesos, financeiro, base, itens = selecionar()
        if not itens:
            return jsonify(erro="Não há alunos nessa seleção para gerar o relatório."), 400
        if not _ia_ocupada.acquire(blocking=False):
            return jsonify(erro="Já há um relatório sendo gerado. Aguarde alguns segundos."), 429
        try:
            _, grupos = predicao.agrupar(DB_DADOS_PATH, itens, "materia", limite=relatorio_ia.TOP_MATERIAS)
            filtros = [f"ciclo {ciclo_pedido()} de {predicao.N_CICLOS} do semestre (dados até o fim desse ciclo)"]
            if request.args.get("curso"):
                filtros.append("curso " + request.args["curso"].replace("_", " "))
            if request.args.get("classificacao"):
                filtros.append("classificação " + request.args["classificacao"])
            if request.args.get("q"):
                filtros.append("busca por nome")
            resumo = relatorio_ia.montar_resumo(
                itens, predicao.calcular_kpis(itens, financeiro), financeiro, grupos,
                g.escopo.descricao, filtros)
            try:
                texto = relatorio_ia.gerar_relatorio(resumo)
            except relatorio_ia.IAIndisponivel as e:
                return jsonify(erro=str(e)), 503
            return jsonify(relatorio=texto, modelo=relatorio_ia.OLLAMA_MODELO, total=len(itens))
        finally:
            _ia_ocupada.release()

    return app


def main():
    for rotulo, caminho in (("dados.db", DB_DADOS_PATH), ("acesso.db", DB_ACESSO_PATH)):
        if not os.path.exists(caminho):
            raise SystemExit(f"{rotulo} não encontrado em '{caminho}'. "
                             f"Rode antes: python -m dados_prototipo.gerar_simpa_db")
    app = criar_app()
    print("Carregando dados (só na primeira vez)...")
    predicao.obter_resultados(DB_DADOS_PATH, dict(predicao.PESOS_PADRAO), predicao.CICLO_PADRAO)   # aquece o cache
    port = int(os.environ.get("SIMPA_PORT", 5000))
    print(f"SIMPA em http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
