import sqlite3
from flask import g, current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY, nome TEXT NOT NULL, matricula TEXT NOT NULL UNIQUE, senha_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS salas (
  id INTEGER PRIMARY KEY, nome TEXT NOT NULL, codigo TEXT NOT NULL UNIQUE, dono_id INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS membros (
  sala_id INTEGER, usuario_id INTEGER, PRIMARY KEY (sala_id, usuario_id));
CREATE TABLE IF NOT EXISTS duvidas (
  id INTEGER PRIMARY KEY, sala_id INTEGER NOT NULL, autor_id INTEGER NOT NULL, titulo TEXT NOT NULL,
  materia TEXT NOT NULL, descricao TEXT NOT NULL, resolvida INTEGER DEFAULT 0,
  criado_em TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS resumos (
  id INTEGER PRIMARY KEY, sala_id INTEGER NOT NULL, autor_id INTEGER NOT NULL, titulo TEXT NOT NULL,
  materia TEXT NOT NULL, conteudo TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS quizzes (
  id INTEGER PRIMARY KEY, sala_id INTEGER NOT NULL, autor_id INTEGER NOT NULL, titulo TEXT NOT NULL,
  materia TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS perguntas (
  id INTEGER PRIMARY KEY, quiz_id INTEGER NOT NULL, enunciado TEXT NOT NULL,
  op1 TEXT NOT NULL, op2 TEXT NOT NULL, op3 TEXT NOT NULL, op4 TEXT NOT NULL,
  correta INTEGER NOT NULL CHECK (correta BETWEEN 1 AND 4), explicacao TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS tentativas (
  id INTEGER PRIMARY KEY, quiz_id INTEGER NOT NULL, usuario_id INTEGER NOT NULL,
  acertos INTEGER NOT NULL, total INTEGER NOT NULL, UNIQUE (quiz_id, usuario_id));
CREATE TABLE IF NOT EXISTS comentarios (
  id INTEGER PRIMARY KEY, alvo_tipo TEXT NOT NULL, alvo_id INTEGER NOT NULL, sala_id INTEGER NOT NULL,
  autor_id INTEGER NOT NULL, texto TEXT NOT NULL, melhor INTEGER DEFAULT 0,
  criado_em TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS curtidas (
  usuario_id INTEGER, alvo_tipo TEXT, alvo_id INTEGER, PRIMARY KEY (usuario_id, alvo_tipo, alvo_id));
CREATE TABLE IF NOT EXISTS salvos (
  usuario_id INTEGER, alvo_tipo TEXT, alvo_id INTEGER, PRIMARY KEY (usuario_id, alvo_tipo, alvo_id));
CREATE TABLE IF NOT EXISTS pontos (
  id INTEGER PRIMARY KEY, sala_id INTEGER NOT NULL, usuario_id INTEGER NOT NULL, motivo TEXT NOT NULL,
  valor INTEGER NOT NULL, ref TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now')));
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    get_db().executescript(SCHEMA)
    get_db().commit()
