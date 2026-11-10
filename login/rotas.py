"""Rotas de login/logout, proteção CSRF e os decoradores que protegem o resto do app."""
import secrets
from functools import wraps

from flask import (Blueprint, abort, current_app, g, jsonify, make_response,
                   redirect, render_template, request, session, url_for)

from login.auth import abrir_acesso, autenticar, carregar_usuario
from login.escopo import resolver_escopo
from login import termo

bp = Blueprint("login", __name__)


@bp.record_once
def _preparar_aceite(state):
    conn = abrir_acesso(state.app.config["DB_ACESSO_PATH"])
    try:
        termo.garantir_tabela(conn)
    finally:
        conn.close()


# CSRF (o login e o logout são POST; as APIs de dados são só GET) 
def csrf_token():
    if not session.get("csrf"):
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_ok():
    enviado = request.headers.get("X-CSRF-Token") or request.form.get("csrf", "")
    esperado = session.get("csrf", "")
    return bool(esperado) and secrets.compare_digest(enviado.encode(), esperado.encode())


# sessão 
def carregar_sessao():
    """Preenche g.usuario e g.escopo a partir do cookie de sessão (ou deixa None)."""
    g.usuario, g.escopo, g.aceite_em = None, None, None
    uid = session.get("uid")
    if uid is None:
        return
    conn = abrir_acesso(current_app.config["DB_ACESSO_PATH"])
    try:
        usuario = carregar_usuario(conn, uid)
        if usuario is None:               # conta removida/desativada
            session.clear()
            return
        g.usuario, g.escopo = usuario, resolver_escopo(conn, usuario)
        g.aceite_em = termo.aceite_em(conn, usuario.id_usuario)
    finally:
        conn.close()


def login_obrigatorio(api=False, exige_termo=True):
    """api=True responde 401 em JSON; api=False redireciona para /login.
    exige_termo=True: sem o termo de privacidade aceito, API responde 403 e página vai para /privacidade."""
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            carregar_sessao()
            if g.usuario is None:
                if api:
                    return jsonify(erro="nao_autenticado"), 401
                return redirect(url_for("login.entrar"))
            if exige_termo and g.aceite_em is None:
                if api:
                    return jsonify(erro="termo_pendente"), 403
                return redirect(url_for("login.privacidade"))
            return f(*args, **kwargs)
        return wrapper
    return decorador


#páginas 
def _pagina_login(erro=None, login="", status=200):
    resp = make_response(render_template("login.html", erro=erro, login=login, csrf=csrf_token()), status)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.route("/login", methods=["GET", "POST"])
def entrar():
    if request.method == "GET":
        carregar_sessao()
        if g.usuario:
            return redirect("/")
        return _pagina_login()

    if not csrf_ok():
        return _pagina_login("Sua sessão expirou. Tente entrar de novo.", status=400)

    login = request.form.get("login", "").strip()[:100]
    senha = request.form.get("senha", "")[:256]
    usuario, motivo = autenticar(current_app.config["DB_ACESSO_PATH"], login, senha)

    if usuario is None:
        if motivo == "bloqueado":
            return _pagina_login(
                "Muitas tentativas sem sucesso. Aguarde alguns minutos e tente novamente.", login, 429)
        return _pagina_login("Login ou senha inválidos.", login, 401)

    session.clear()                       # sessão nova a cada login (evita fixação de sessão)
    session.permanent = True
    session["uid"] = usuario.id_usuario
    csrf_token()
    return redirect("/")


def _pagina_termo(erro=None, status=200):
    u = g.usuario
    resp = make_response(render_template(
        "privacidade.html", erro=erro, csrf=csrf_token(), nome=u.nome.split()[0],
        versao=termo.TERMO_VERSAO, ja_aceitou=g.aceite_em is not None, aceite_em=g.aceite_em,
        demo=termo.AMBIENTE_DEMO, controlador=termo.CONTROLADOR,
        contato=termo.CONTATO_ENCARREGADO), status)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.route("/privacidade", methods=["GET", "POST"])
@login_obrigatorio(exige_termo=False)
def privacidade():
    if request.method == "GET":
        return _pagina_termo()
    if not csrf_ok():
        abort(400)
    if g.aceite_em is None:
        if request.form.get("aceite") != "sim":
            return _pagina_termo("Marque a caixa de confirmação para continuar.", 400)
        conn = abrir_acesso(current_app.config["DB_ACESSO_PATH"])
        try:
            termo.registrar_aceite(conn, g.usuario.id_usuario)
        finally:
            conn.close()
    return redirect("/")


@bp.post("/logout")
def sair():
    if not csrf_ok():
        abort(400)
    session.clear()
    if request.headers.get("X-CSRF-Token"):      # chamado pelo JS do front
        return "", 204
    return redirect(url_for("login.entrar"))
