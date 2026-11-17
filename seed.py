"""Cria dados de exemplo para a demonstração:  python seed.py
Usuários: 1001 (Ana), 1002 (Beto), 1003 (Caio) — senha de todos: demo1234"""
from werkzeug.security import generate_password_hash
from app import create_app
import db as banco
import pontos

app = create_app()
with app.app_context():
    d = banco.get_db()
    if d.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]:
        raise SystemExit("O banco já tem dados; apague mural.db para recriar.")
    for mat, nome in (("1001", "Ana Souza"), ("1002", "Beto Lima"), ("1003", "Caio Rocha")):
        d.execute("INSERT INTO usuarios (nome, matricula, senha_hash) VALUES (?,?,?)",
                  (nome, mat, generate_password_hash("demo1234")))
    d.execute("INSERT INTO salas (nome, codigo, dono_id) VALUES ('Métodos Ágeis 4ºC', 'DEMO01', 1)")
    for u in (1, 2, 3):
        d.execute("INSERT INTO membros VALUES (1, ?)", (u,))
    d.execute("INSERT INTO duvidas (sala_id, autor_id, titulo, materia, descricao) VALUES "
              "(1, 2, 'Qual a diferença entre Lead Time e Cycle Time?', 'Kanban', 'Não entendi quando cada um começa a contar.')")
    pontos.conceder(d, 1, 2, "duvida", "duvida:1")
    d.execute("INSERT INTO comentarios (alvo_tipo, alvo_id, sala_id, autor_id, texto) VALUES "
              "('duvida', 1, 1, 1, 'Lead Time começa quando o pedido entra; Cycle Time, quando alguém começa a trabalhar.')")
    pontos.conceder(d, 1, 1, "comentario", "comentario:1")
    d.execute("INSERT INTO resumos (sala_id, autor_id, titulo, materia, conteudo) VALUES "
              "(1, 3, 'Resumo de Scrum', 'Métodos Ágeis', 'Papéis: PO, Scrum Master, Time.\nEventos: Planning, Daily, Review, Retrospectiva.')")
    pontos.conceder(d, 1, 3, "resumo", "resumo:1")
    d.commit()
    print("Pronto! Entre com matrícula 1001, 1002 ou 1003 e senha demo1234. Código da sala: DEMO01")
