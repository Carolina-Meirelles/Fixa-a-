"""Mural da Turma - protótipo (Flask + SQLite)."""
import os
import secrets
import sqlite3
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db as banco
import pontos

TIPOS_COMENTAVEIS = {"duvida", "resumo", "quiz"}
TIPOS_CURTIVEIS = {"comentario", "resumo", "quiz"}
TIPOS_SALVAVEIS = {"resumo", "quiz"}
TABELAS = {"duvida": "duvidas", "resumo": "resumos", "quiz": "quizzes"}


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-troque-em-producao"),
        DATABASE=os.environ.get("DATABASE", "mural.db"),
    )
    if config:
        app.config.update(config)
    app.teardown_appcontext(banco.close_db)
    with app.app_context():
        banco.init_db()

    # ---------------- helpers ----------------
    def login_required(f):
        @wraps(f)
        def wrapper(*a, **k):
            if "uid" not in session:
                return redirect(url_for("login"))
            return f(*a, **k)
        return wrapper

    @app.before_request
    def carregar_usuario():
        g.user = None
        if "uid" in session:
            g.user = banco.get_db().execute(
                "SELECT * FROM usuarios WHERE id=?", (session["uid"],)).fetchone()
            if g.user is None:
                session.clear()

    def sala_do_membro(sala_id):
        d = banco.get_db()
        sala = d.execute("SELECT * FROM salas WHERE id=?", (sala_id,)).fetchone()
        if sala is None:
            abort(404)
        membro = d.execute("SELECT 1 FROM membros WHERE sala_id=? AND usuario_id=?",
                           (sala_id, g.user["id"])).fetchone()
        if membro is None:
            abort(403)
        return sala

    def alvo_da_sala(tipo, alvo_id):
        """Busca o conteúdo e garante que o usuário é membro da sala dele."""
        if tipo == "comentario":
            row = banco.get_db().execute("SELECT * FROM comentarios WHERE id=?", (alvo_id,)).fetchone()
        else:
            row = banco.get_db().execute(f"SELECT * FROM {TABELAS[tipo]} WHERE id=?", (alvo_id,)).fetchone()
        if row is None:
            abort(404)
        sala_do_membro(row["sala_id"])
        return row

    def pontuar(sala_id, usuario_id, motivo, ref):
        return pontos.conceder(banco.get_db(), sala_id, usuario_id, motivo, ref)

    def total_pontos(sala_id, usuario_id):
        return banco.get_db().execute(
            "SELECT COALESCE(SUM(valor),0) FROM pontos WHERE sala_id=? AND usuario_id=?",
            (sala_id, usuario_id)).fetchone()[0]

    app.jinja_env.globals.update(nivel=pontos.nivel)

    # ---------------- conta ----------------
    @app.route("/")
    def inicio():
        return redirect(url_for("salas" if "uid" in session else "login"))

    @app.route("/cadastro", methods=["GET", "POST"])
    def cadastro():
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            matricula = request.form.get("matricula", "").strip()
            senha = request.form.get("senha", "")
            if not nome or not matricula or len(senha) < 6:
                flash("Preencha nome e matrícula e use senha com 6+ caracteres.")
            else:
                try:
                    banco.get_db().execute(
                        "INSERT INTO usuarios (nome, matricula, senha_hash) VALUES (?,?,?)",
                        (nome, matricula, generate_password_hash(senha)))
                    banco.get_db().commit()
                    flash("Cadastro feito! Entre com sua matrícula.")
                    return redirect(url_for("login"))
                except sqlite3.IntegrityError:
                    flash("Essa matrícula já está cadastrada.")
        return render_template("cadastro.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            u = banco.get_db().execute("SELECT * FROM usuarios WHERE matricula=?",
                                       (request.form.get("matricula", "").strip(),)).fetchone()
            if u and check_password_hash(u["senha_hash"], request.form.get("senha", "")):
                session.clear()
                session["uid"] = u["id"]
                return redirect(url_for("salas"))
            flash("Matrícula ou senha incorretas.")
        return render_template("login.html")

    @app.route("/sair")
    def sair():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/conta/excluir", methods=["POST"])
    @login_required
    def excluir_conta():
        """LGPD: anonimiza a conta e tira o acesso; o conteúdo da turma permanece sem nome."""
        d = banco.get_db()
        uid = g.user["id"]
        d.execute("UPDATE usuarios SET nome='Usuário removido', matricula=?, senha_hash='' WHERE id=?",
                  (f"removido-{uid}", uid))
        d.execute("DELETE FROM membros WHERE usuario_id=?", (uid,))
        d.execute("DELETE FROM salvos WHERE usuario_id=?", (uid,))
        d.execute("DELETE FROM curtidas WHERE usuario_id=?", (uid,))
        d.commit()
        session.clear()
        flash("Sua conta foi removida.")
        return redirect(url_for("login"))

    # ---------------- salas ----------------
    @app.route("/salas")
    @login_required
    def salas():
        minhas = banco.get_db().execute(
            "SELECT s.* FROM salas s JOIN membros m ON m.sala_id=s.id WHERE m.usuario_id=? ORDER BY s.nome",
            (g.user["id"],)).fetchall()
        return render_template("salas.html", salas=minhas)

    @app.route("/salas/criar", methods=["POST"])
    @login_required
    def criar_sala():
        nome = request.form.get("nome", "").strip()
        if not nome:
            flash("Dê um nome para a sala.")
            return redirect(url_for("salas"))
        d = banco.get_db()
        codigo = secrets.token_hex(3).upper()
        cur = d.execute("INSERT INTO salas (nome, codigo, dono_id) VALUES (?,?,?)",
                        (nome, codigo, g.user["id"]))
        d.execute("INSERT INTO membros VALUES (?,?)", (cur.lastrowid, g.user["id"]))
        d.commit()
        flash(f"Sala criada! Código de convite: {codigo}")
        return redirect(url_for("duvidas", sala_id=cur.lastrowid))

    @app.route("/salas/entrar", methods=["POST"])
    @login_required
    def entrar_sala():
        codigo = request.form.get("codigo", "").strip().upper()
        d = banco.get_db()
        sala = d.execute("SELECT * FROM salas WHERE codigo=?", (codigo,)).fetchone()
        if sala is None:
            flash("Código de sala não encontrado.")
            return redirect(url_for("salas"))
        d.execute("INSERT OR IGNORE INTO membros VALUES (?,?)", (sala["id"], g.user["id"]))
        d.commit()
        return redirect(url_for("duvidas", sala_id=sala["id"]))

    # ---------------- dúvidas ----------------
    @app.route("/sala/<int:sala_id>/duvidas", methods=["GET", "POST"])
    @login_required
    def duvidas(sala_id):
        sala = sala_do_membro(sala_id)
        d = banco.get_db()
        if request.method == "POST":
            titulo, materia, desc = (request.form.get(k, "").strip() for k in ("titulo", "materia", "descricao"))
            if titulo and materia and desc:
                cur = d.execute("INSERT INTO duvidas (sala_id, autor_id, titulo, materia, descricao) VALUES (?,?,?,?,?)",
                                (sala_id, g.user["id"], titulo, materia, desc))
                pontuar(sala_id, g.user["id"], "duvida", f"duvida:{cur.lastrowid}")
                d.commit()
                return redirect(url_for("ver_duvida", sala_id=sala_id, duvida_id=cur.lastrowid))
            flash("Preencha título, matéria e descrição.")
        q = request.args.get("q", "").strip()
        sql = ("SELECT d.*, u.nome AS autor FROM duvidas d JOIN usuarios u ON u.id=d.autor_id "
               "WHERE d.sala_id=?")
        args = [sala_id]
        if q:
            sql += " AND (d.titulo LIKE ? OR d.materia LIKE ? OR d.descricao LIKE ?)"
            args += [f"%{q}%"] * 3
        lista = d.execute(sql + " ORDER BY d.id DESC", args).fetchall()
        return render_template("duvidas.html", sala=sala, lista=lista, q=q, aba="duvidas")

    @app.route("/sala/<int:sala_id>/duvidas/<int:duvida_id>")
    @login_required
    def ver_duvida(sala_id, duvida_id):
        sala = sala_do_membro(sala_id)
        d = banco.get_db()
        duv = d.execute("SELECT d.*, u.nome AS autor FROM duvidas d JOIN usuarios u ON u.id=d.autor_id "
                        "WHERE d.id=? AND d.sala_id=?", (duvida_id, sala_id)).fetchone()
        if duv is None:
            abort(404)
        return render_template("duvida.html", sala=sala, item=duv, comentarios=lista_comentarios("duvida", duvida_id), aba="duvidas")

    @app.route("/duvidas/<int:duvida_id>/melhor/<int:comentario_id>", methods=["POST"])
    @login_required
    def melhor_resposta(duvida_id, comentario_id):
        duv = alvo_da_sala("duvida", duvida_id)
        if duv["autor_id"] != g.user["id"]:
            abort(403)
        d = banco.get_db()
        c = d.execute("SELECT * FROM comentarios WHERE id=? AND alvo_tipo='duvida' AND alvo_id=?",
                      (comentario_id, duvida_id)).fetchone()
        if c is None:
            abort(404)
        if not duv["resolvida"]:
            d.execute("UPDATE comentarios SET melhor=1 WHERE id=?", (comentario_id,))
            d.execute("UPDATE duvidas SET resolvida=1 WHERE id=?", (duvida_id,))
            if c["autor_id"] != g.user["id"]:
                pontuar(duv["sala_id"], c["autor_id"], "melhor_resposta", f"comentario:{comentario_id}")
            d.commit()
        return redirect(url_for("ver_duvida", sala_id=duv["sala_id"], duvida_id=duvida_id))

    # ---------------- comentários ----------------
    def lista_comentarios(tipo, alvo_id):
        return banco.get_db().execute(
            "SELECT c.*, u.nome AS autor, "
            "(SELECT COUNT(*) FROM curtidas WHERE alvo_tipo='comentario' AND alvo_id=c.id) AS curtidas "
            "FROM comentarios c JOIN usuarios u ON u.id=c.autor_id "
            "WHERE c.alvo_tipo=? AND c.alvo_id=? ORDER BY c.melhor DESC, c.id", (tipo, alvo_id)).fetchall()

    @app.route("/comentar/<tipo>/<int:alvo_id>", methods=["POST"])
    @login_required
    def comentar(tipo, alvo_id):
        if tipo not in TIPOS_COMENTAVEIS:
            abort(404)
        alvo = alvo_da_sala(tipo, alvo_id)
        texto = request.form.get("texto", "").strip()
        if texto:
            d = banco.get_db()
            cur = d.execute("INSERT INTO comentarios (alvo_tipo, alvo_id, sala_id, autor_id, texto) VALUES (?,?,?,?,?)",
                            (tipo, alvo_id, alvo["sala_id"], g.user["id"], texto))
            pontuar(alvo["sala_id"], g.user["id"], "comentario", f"comentario:{cur.lastrowid}")
            d.commit()
        return redirect(request.referrer or url_for("salas"))

    # ---------------- curtir / salvar ----------------
    @app.route("/curtir/<tipo>/<int:alvo_id>", methods=["POST"])
    @login_required
    def curtir(tipo, alvo_id):
        if tipo not in TIPOS_CURTIVEIS:
            abort(404)
        alvo = alvo_da_sala(tipo, alvo_id)
        d = banco.get_db()
        ja = d.execute("SELECT 1 FROM curtidas WHERE usuario_id=? AND alvo_tipo=? AND alvo_id=?",
                       (g.user["id"], tipo, alvo_id)).fetchone()
        if ja:
            d.execute("DELETE FROM curtidas WHERE usuario_id=? AND alvo_tipo=? AND alvo_id=?",
                      (g.user["id"], tipo, alvo_id))
        else:
            d.execute("INSERT INTO curtidas VALUES (?,?,?)", (g.user["id"], tipo, alvo_id))
            if alvo["autor_id"] != g.user["id"]:  # não ganha ponto no próprio conteúdo
                pontuar(alvo["sala_id"], alvo["autor_id"], "curtida_recebida", f"{tipo}:{alvo_id}")
        d.commit()
        return redirect(request.referrer or url_for("salas"))

    @app.route("/salvar/<tipo>/<int:alvo_id>", methods=["POST"])
    @login_required
    def salvar(tipo, alvo_id):
        if tipo not in TIPOS_SALVAVEIS:
            abort(404)
        alvo = alvo_da_sala(tipo, alvo_id)
        d = banco.get_db()
        ja = d.execute("SELECT 1 FROM salvos WHERE usuario_id=? AND alvo_tipo=? AND alvo_id=?",
                       (g.user["id"], tipo, alvo_id)).fetchone()
        if ja:
            d.execute("DELETE FROM salvos WHERE usuario_id=? AND alvo_tipo=? AND alvo_id=?",
                      (g.user["id"], tipo, alvo_id))
        else:
            d.execute("INSERT INTO salvos VALUES (?,?,?)", (g.user["id"], tipo, alvo_id))
            if alvo["autor_id"] != g.user["id"]:
                pontuar(alvo["sala_id"], alvo["autor_id"], "salvo_recebido", f"{tipo}:{alvo_id}")
        d.commit()
        return redirect(request.referrer or url_for("salas"))

    @app.route("/salvos")
    @login_required
    def salvos():
        d = banco.get_db()
        resumos = d.execute(
            "SELECT r.*, s.nome AS sala FROM salvos v JOIN resumos r ON r.id=v.alvo_id "
            "JOIN salas s ON s.id=r.sala_id WHERE v.usuario_id=? AND v.alvo_tipo='resumo'", (g.user["id"],)).fetchall()
        quizzes = d.execute(
            "SELECT q.*, s.nome AS sala FROM salvos v JOIN quizzes q ON q.id=v.alvo_id "
            "JOIN salas s ON s.id=q.sala_id WHERE v.usuario_id=? AND v.alvo_tipo='quiz'", (g.user["id"],)).fetchall()
        return render_template("salvos.html", resumos=resumos, quizzes=quizzes)

    # ---------------- resumos ----------------
    def contagens(tipo, ids):
        d = banco.get_db()
        out = {}
        for i in ids:
            out[i] = {
                "curtidas": d.execute("SELECT COUNT(*) FROM curtidas WHERE alvo_tipo=? AND alvo_id=?", (tipo, i)).fetchone()[0],
                "salvos": d.execute("SELECT COUNT(*) FROM salvos WHERE alvo_tipo=? AND alvo_id=?", (tipo, i)).fetchone()[0],
            }
        return out

    @app.route("/sala/<int:sala_id>/resumos", methods=["GET", "POST"])
    @login_required
    def resumos(sala_id):
        sala = sala_do_membro(sala_id)
        d = banco.get_db()
        if request.method == "POST":
            titulo, materia, conteudo = (request.form.get(k, "").strip() for k in ("titulo", "materia", "conteudo"))
            if titulo and materia and conteudo:
                cur = d.execute("INSERT INTO resumos (sala_id, autor_id, titulo, materia, conteudo) VALUES (?,?,?,?,?)",
                                (sala_id, g.user["id"], titulo, materia, conteudo))
                pontuar(sala_id, g.user["id"], "resumo", f"resumo:{cur.lastrowid}")
                d.commit()
                return redirect(url_for("ver_resumo", sala_id=sala_id, resumo_id=cur.lastrowid))
            flash("Preencha título, matéria e conteúdo (texto ou link).")
        q = request.args.get("q", "").strip()
        sql = "SELECT r.*, u.nome AS autor FROM resumos r JOIN usuarios u ON u.id=r.autor_id WHERE r.sala_id=?"
        args = [sala_id]
        if q:
            sql += " AND (r.titulo LIKE ? OR r.materia LIKE ? OR r.conteudo LIKE ?)"
            args += [f"%{q}%"] * 3
        lista = d.execute(sql + " ORDER BY r.id DESC", args).fetchall()
        return render_template("resumos.html", sala=sala, lista=lista, q=q, cont=contagens("resumo", [r["id"] for r in lista]), aba="resumos")

    @app.route("/sala/<int:sala_id>/resumos/<int:resumo_id>")
    @login_required
    def ver_resumo(sala_id, resumo_id):
        sala = sala_do_membro(sala_id)
        d = banco.get_db()
        r = d.execute("SELECT r.*, u.nome AS autor FROM resumos r JOIN usuarios u ON u.id=r.autor_id "
                      "WHERE r.id=? AND r.sala_id=?", (resumo_id, sala_id)).fetchone()
        if r is None:
            abort(404)
        salvo = d.execute("SELECT 1 FROM salvos WHERE usuario_id=? AND alvo_tipo='resumo' AND alvo_id=?",
                          (g.user["id"], resumo_id)).fetchone() is not None
        return render_template("resumo.html", sala=sala, item=r, salvo=salvo, cont=contagens("resumo", [resumo_id])[resumo_id],
                               comentarios=lista_comentarios("resumo", resumo_id), aba="resumos")

    # ---------------- quizzes ----------------
    @app.route("/sala/<int:sala_id>/quizzes", methods=["GET", "POST"])
    @login_required
    def quizzes(sala_id):
        sala = sala_do_membro(sala_id)
        d = banco.get_db()
        if request.method == "POST":
            titulo = request.form.get("titulo", "").strip()
            materia = request.form.get("materia", "").strip()
            perguntas = []
            for n in range(1, 4):
                enun = request.form.get(f"p{n}", "").strip()
                ops = [request.form.get(f"p{n}o{k}", "").strip() for k in range(1, 5)]
                cor = request.form.get(f"p{n}c", "")
                if enun and all(ops) and cor in {"1", "2", "3", "4"}:
                    perguntas.append((enun, *ops, int(cor), request.form.get(f"p{n}e", "").strip()))
            if titulo and materia and perguntas:
                cur = d.execute("INSERT INTO quizzes (sala_id, autor_id, titulo, materia) VALUES (?,?,?,?)",
                                (sala_id, g.user["id"], titulo, materia))
                for p in perguntas:
                    d.execute("INSERT INTO perguntas (quiz_id, enunciado, op1, op2, op3, op4, correta, explicacao) "
                              "VALUES (?,?,?,?,?,?,?,?)", (cur.lastrowid, *p))
                pontuar(sala_id, g.user["id"], "quiz", f"quiz:{cur.lastrowid}")
                d.commit()
                return redirect(url_for("ver_quiz", sala_id=sala_id, quiz_id=cur.lastrowid))
            flash("Preencha título, matéria e pelo menos 1 pergunta completa (4 opções e a correta).")
        lista = d.execute(
            "SELECT q.*, u.nome AS autor, (SELECT COUNT(*) FROM perguntas WHERE quiz_id=q.id) AS n_perguntas, "
            "(SELECT COUNT(*) FROM tentativas WHERE quiz_id=q.id) AS respostas, "
            "(SELECT COALESCE(ROUND(100.0*SUM(acertos)/SUM(total)),0) FROM tentativas WHERE quiz_id=q.id) AS taxa "
            "FROM quizzes q JOIN usuarios u ON u.id=q.autor_id WHERE q.sala_id=? ORDER BY q.id DESC", (sala_id,)).fetchall()
        return render_template("quizzes.html", sala=sala, lista=lista, cont=contagens("quiz", [q["id"] for q in lista]), aba="quizzes")

    @app.route("/sala/<int:sala_id>/quizzes/<int:quiz_id>", methods=["GET", "POST"])
    @login_required
    def ver_quiz(sala_id, quiz_id):
        sala = sala_do_membro(sala_id)
        d = banco.get_db()
        quiz = d.execute("SELECT q.*, u.nome AS autor FROM quizzes q JOIN usuarios u ON u.id=q.autor_id "
                         "WHERE q.id=? AND q.sala_id=?", (quiz_id, sala_id)).fetchone()
        if quiz is None:
            abort(404)
        perguntas = d.execute("SELECT * FROM perguntas WHERE quiz_id=? ORDER BY id", (quiz_id,)).fetchall()
        tentativa = d.execute("SELECT * FROM tentativas WHERE quiz_id=? AND usuario_id=?",
                              (quiz_id, g.user["id"])).fetchone()
        respostas = None
        if request.method == "POST" and tentativa is None:
            respostas = []
            for p in perguntas:
                v = request.form.get(f"r{p['id']}", "")
                respostas.append(int(v) if v in {"1", "2", "3", "4"} else None)
            acertos = pontos.corrigir([p["correta"] for p in perguntas], respostas)
            d.execute("INSERT INTO tentativas (quiz_id, usuario_id, acertos, total) VALUES (?,?,?,?)",
                      (quiz_id, g.user["id"], acertos, len(perguntas)))
            for i in range(acertos):  # cada acerto = 1 ponto, com teto diário
                pontuar(sala_id, g.user["id"], "acerto_quiz", f"quiz:{quiz_id}:{i}")
            d.commit()
            tentativa = d.execute("SELECT * FROM tentativas WHERE quiz_id=? AND usuario_id=?",
                                  (quiz_id, g.user["id"])).fetchone()
        salvo = d.execute("SELECT 1 FROM salvos WHERE usuario_id=? AND alvo_tipo='quiz' AND alvo_id=?",
                          (g.user["id"], quiz_id)).fetchone() is not None
        return render_template("quiz.html", sala=sala, item=quiz, perguntas=perguntas, tentativa=tentativa,
                               respostas=respostas, salvo=salvo, cont=contagens("quiz", [quiz_id])[quiz_id],
                               comentarios=lista_comentarios("quiz", quiz_id), aba="quizzes")

    # ---------------- ranking ----------------
    @app.route("/sala/<int:sala_id>/ranking")
    @login_required
    def ranking(sala_id):
        sala = sala_do_membro(sala_id)
        linhas = banco.get_db().execute(
            "SELECT u.nome, COALESCE(SUM(p.valor),0) AS total FROM membros m "
            "JOIN usuarios u ON u.id=m.usuario_id LEFT JOIN pontos p ON p.usuario_id=u.id AND p.sala_id=m.sala_id "
            "WHERE m.sala_id=? GROUP BY u.id ORDER BY total DESC, u.nome", (sala_id,)).fetchall()
        return render_template("ranking.html", sala=sala, linhas=linhas, meus=total_pontos(sala_id, g.user["id"]), aba="ranking")

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
