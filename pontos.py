"""Regras de pontuação e correção de quiz. Funções simples, fáceis de testar (TDD)."""

TABELA = {
    "duvida": 2,
    "comentario": 2,
    "melhor_resposta": 5,
    "resumo": 5,
    "quiz": 8,
    "curtida_recebida": 1,
    "salvo_recebido": 2,
    "acerto_quiz": 1,
}
TETO_DIARIO = 50
TETO_POR_CONTEUDO = 10
COM_TETO_POR_CONTEUDO = {"curtida_recebida", "salvo_recebido"}

NIVEIS = [(150, "Mentor"), (50, "Colaborador"), (0, "Novato")]


def valor_com_teto(motivo, pontos_hoje=0, pontos_no_conteudo=0):
    """Quantos pontos realmente entram, respeitando os tetos."""
    valor = TABELA[motivo]
    if motivo in COM_TETO_POR_CONTEUDO:
        valor = min(valor, max(0, TETO_POR_CONTEUDO - pontos_no_conteudo))
    return min(valor, max(0, TETO_DIARIO - pontos_hoje))


def nivel(total):
    for minimo, nome in NIVEIS:
        if total >= minimo:
            return nome


def corrigir(corretas, respostas):
    """corretas: lista de 1-4; respostas: lista de 1-4 ou None. Retorna nº de acertos."""
    return sum(1 for c, r in zip(corretas, respostas) if r is not None and c == r)


def conceder(db, sala_id, usuario_id, motivo, ref):
    """Grava pontos já aplicando os tetos. Retorna o valor concedido (0 se bateu no teto)."""
    hoje = db.execute(
        "SELECT COALESCE(SUM(valor),0) FROM pontos WHERE usuario_id=? AND date(criado_em)=date('now')",
        (usuario_id,)).fetchone()[0]
    no_conteudo = db.execute(
        "SELECT COALESCE(SUM(valor),0) FROM pontos WHERE usuario_id=? AND motivo=? AND ref=?",
        (usuario_id, motivo, ref)).fetchone()[0]
    valor = valor_com_teto(motivo, hoje, no_conteudo)
    if valor > 0:
        db.execute("INSERT INTO pontos (sala_id, usuario_id, motivo, valor, ref) VALUES (?,?,?,?,?)",
                   (sala_id, usuario_id, motivo, valor, ref))
    return valor
