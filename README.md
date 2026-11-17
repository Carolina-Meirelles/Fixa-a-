# Fixa Aí! 📌

Espaço da turma para **tirar dúvidas, compartilhar resumos e criar quizzes**, com **pontos por participação**.
Python 3.10+ · Flask · SQLite.

Demonstração sem instalar nada: abra o `index.html` no navegador.

## Como rodar
```bash
pip install -r requirements.txt
python seed.py        # opcional: dados de exemplo (usuários 1001/1002/1003, senha demo1234, sala DEMO01)
python app.py         # abre em http://127.0.0.1:5000
```

## Testes
```bash
python -m unittest discover -s tests -t . -v
```
(também rodam com `pytest`, se instalado)

## O que o protótipo faz
- **Cadastro e login** (senha guardada com hash) e **apagar conta** (LGPD: anonimiza).
- **Salas** com código de convite: criar e entrar pelo código.
- **Dúvidas**: postar, buscar por matéria/palavra, responder e marcar a melhor resposta.
- **Resumos** (texto ou link), **quizzes** de múltipla escolha com nota na hora.
- **Comentários, curtidas e salvar** (resumos e quizzes) + aba "Meus salvos".
- **Pontos e ranking** por sala, com níveis.

## Pontuação (em `pontos.py`)
| Ação | Pontos |
|---|---|
| Postar dúvida | +2 |
| Comentar/responder | +2 (+5 se for a melhor resposta) |
| Publicar resumo | +5 |
| Criar quiz | +8 |
| Receber curtida | +1 (máx. 10 por conteúdo) |
| Alguém salvar seu resumo/quiz | +2 (máx. 10 por conteúdo) |
| Acertar pergunta de quiz | +1 |

Sem pontos no próprio conteúdo; teto de 50 pontos por dia. Níveis: Novato (0–49), Colaborador (50–149), Mentor (150+).

## Publicar no Render
- Build: `pip install -r requirements.txt` · Start: `gunicorn wsgi:app`
- Variáveis: `SECRET_KEY` (valor aleatório) e `DATABASE` (caminho do .db).
- **Atenção:** no plano gratuito o disco é apagado a cada deploy, então o SQLite zera. Para a demonstração, rode o `seed.py` no start, ou use um PostgreSQL externo depois.

## Limitações do protótipo
- Sem proteção CSRF e sem limite de tentativas de login (usar Flask-WTF/Flask-Limiter numa versão real).
- Resumos só em texto/link (sem upload de arquivo).
- Quiz com até 3 perguntas por criação e 1 tentativa por pessoa.
