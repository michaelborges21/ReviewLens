"""Testa as rotas com TestClient — e, principalmente, que texto de review não vira marcação."""

import json
from collections.abc import Iterator
from pathlib import Path
from urllib.error import URLError

import duckdb
import pytest
from fastapi.testclient import TestClient

from app.base import obter_conexao
from app.main import app
from bri.agent import conversa, exportar, narrador

SCRIPT = "<script>alert('xss')</script>"


@pytest.fixture
def cliente() -> Iterator[TestClient]:
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE reviews AS SELECT * FROM (VALUES
            (1, 'Dune', 5.0, TIMESTAMP '2010-05-01', 'otimo', ?, 'h1'),
            (2, 'Dune', 3.0, TIMESTAMP '2011-05-01', 'meh', 'texto comum', 'h2')
        ) t(review_id, title, rating, reviewed_at, review_title, review_text, user_hash)
        """,
        [SCRIPT],
    )
    con.execute("""
        CREATE TABLE books AS
        SELECT * FROM (VALUES ('Dune', ['Ficção'])) t(title, categories)
    """)
    con.execute("""
        CREATE TABLE book_authors AS
        SELECT * FROM (VALUES ('Dune', 'Frank Herbert')) t(title, author)
    """)
    con.execute("""
        CREATE TABLE author_stats AS
        SELECT * FROM (VALUES ('Frank Herbert', 1, 2, 4.0, 3.9))
            t(author, n_livros, n_reviews, nota_media, nota_bayesiana)
    """)
    con.execute("""
        CREATE TABLE genre_stats AS
        SELECT * FROM (VALUES ('Ficção', 1, 2, 4.0, 500.0))
            t(categoria, n_livros, n_reviews, nota_media, comprimento_mediano)
    """)
    con.execute("""
        CREATE TABLE users_agg AS
        SELECT * FROM (VALUES ('h1abcdef012345', 5, 3.0, 800.0))
            t(user_hash, n_reviews, nota_media, comprimento_mediano)
    """)
    con.execute(
        """
        CREATE TABLE enrichment_sample AS SELECT * FROM (VALUES
            (1, 'Dune', 5.0, TIMESTAMP '2010-05-01', 'otimo', ?, 'h1')
        ) t(review_id, title, rating, reviewed_at, review_title, review_text, user_hash)
        """,
        [SCRIPT],
    )
    con.execute(
        """
        CREATE TABLE review_enriched AS SELECT * FROM (VALUES
            ('1', [{'aspect': 'enredo', 'sentiment': 'negativo', 'evidence': ?}], true)
        ) t(review_id, aspects, is_recommendation)
        """,
        [SCRIPT],
    )

    con.execute(
        """
        CREATE TABLE entity_summaries AS SELECT * FROM (VALUES
            ('Ritmo domina as críticas.', ['Enredo elogiado'], ['Ritmo lento'],
             [{'review_id': '1', 'quote': ?}], 'autor', 'Frank Herbert', 7, '0.2.1')
        ) t(headline, strengths, weaknesses, notable_quotes, entity_type, entity_id,
            n_reviews_considered, prompt_version)
        """,
        [SCRIPT],
    )

    app.dependency_overrides[obter_conexao] = lambda: con
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def sem_modelo_por_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum teste de rota chama o modelo real (AGENTS.md); quem quer narração põe seu fake."""

    def indisponivel(*_a: object, **_k: object) -> str:
        raise URLError("modelo desligado nos testes")

    monkeypatch.setattr(narrador.ollama, "gerar_json", indisponivel)


@pytest.fixture(autouse=True)
def resetar_estado_conversa() -> None:
    """Sessão em memória é dict módulo-level: sem isto, um teste vazaria estado para o seguinte."""
    conversa.SESSOES.clear()


@pytest.mark.parametrize(
    "caminho",
    ["/", "/autores", "/generos", "/reviews", "/entrevistas", "/chat", "/autores/Frank%20Herbert"],
)
def test_paginas_respondem(cliente: TestClient, caminho: str) -> None:
    assert cliente.get(caminho).status_code == 200


def test_texto_de_review_e_escapado(cliente: TestClient) -> None:
    """Review é dado de terceiro (spec 05). Se o autoescape cair, isto tem que ficar vermelho."""
    corpo = cliente.get("/reviews").text

    assert SCRIPT not in corpo
    assert "&lt;script&gt;" in corpo


def test_pagina_de_autor_mostra_aspectos_quando_ha_dado(cliente: TestClient) -> None:
    corpo = cliente.get("/autores/Frank%20Herbert").text

    assert "enredo" in corpo
    assert "analisadas por IA" in corpo
    assert "Pendente da F1" not in corpo


def test_pagina_de_autor_sem_aspectos_nao_quebra(cliente: TestClient) -> None:
    resposta = cliente.get("/autores/Autor%20Inexistente")

    assert resposta.status_code == 200
    assert "nenhuma avaliação" in resposta.text.lower()
    assert "Pendente da F1" not in resposta.text


def test_pagina_de_genero_mostra_aspectos_quando_ha_dado(cliente: TestClient) -> None:
    corpo = cliente.get("/generos/Ficção").text

    assert "enredo" in corpo
    assert "Pendente da F1" not in corpo


def test_evidencia_de_aspecto_e_escapada(cliente: TestClient) -> None:
    """evidence vem de texto de terceiro — mesma exigência de escape de review_text (spec 05)."""
    corpo = cliente.get("/autores/Frank%20Herbert").text

    assert SCRIPT not in corpo
    assert "&lt;script&gt;" in corpo


def test_pagina_de_autor_mostra_resumo_quando_existe(cliente: TestClient) -> None:
    corpo = cliente.get("/autores/Frank%20Herbert").text

    assert "Ritmo domina as críticas." in corpo
    assert "redigido por IA local" in corpo


def test_quote_do_resumo_e_escapada(cliente: TestClient) -> None:
    """A parcial nova reintroduz texto de terceiro na tela — o escape tem que valer aqui também."""
    corpo = cliente.get("/autores/Frank%20Herbert").text

    assert SCRIPT not in corpo
    assert "&lt;script&gt;" in corpo


def test_pagina_de_autor_sem_resumo_nao_quebra(cliente: TestClient) -> None:
    """Entidade abaixo do piso simplesmente não mostra o bloco — não é página vazia nem erro."""
    resposta = cliente.get("/autores/Autor%20Inexistente")

    assert resposta.status_code == 200
    assert "redigido por IA local" not in resposta.text


def test_chat_responde_e_mostra_sql(cliente: TestClient) -> None:
    resposta = cliente.post("/chat", data={"pergunta": "desempenho do autor Herbert"})

    assert resposta.status_code == 200
    assert "Frank Herbert" in resposta.text


def test_chat_narrado_mostra_prosa_e_citacao(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    narracao = json.dumps(
        {
            "resposta": "Os leitores elogiam o enredo.",
            "citacoes": [{"review_id": "1", "trecho": SCRIPT}],
            "confianca": "alta",
            "proximas_perguntas": ["E o ritmo?"],
        }
    )
    monkeypatch.setattr(narrador.ollama, "gerar_json", lambda *a, **k: narracao)

    corpo = cliente.post("/chat", data={"pergunta": "desempenho do autor Herbert"}).text

    assert "Os leitores elogiam o enredo." in corpo
    assert "review 1" in corpo
    assert SCRIPT not in corpo  # trecho é texto de terceiro: escapado como review_text (spec 05)
    assert "&lt;script&gt;" in corpo


def test_chat_sem_modelo_responde_com_texto_deterministico(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ollama fora do ar não pode virar 500 — é a regressão mais importante desta mudança."""

    def cai(*_a: object, **_k: object) -> str:
        raise URLError("connection refused")

    monkeypatch.setattr(narrador.ollama, "gerar_json", cai)

    resposta = cliente.post("/chat", data={"pergunta": "desempenho do autor Herbert"})

    assert resposta.status_code == 200
    assert "Frank Herbert" in resposta.text


def test_chat_recusa_fora_de_escopo(cliente: TestClient) -> None:
    resposta = cliente.post("/chat", data={"pergunta": "me indica um livro para viajar"})

    assert "Não consigo responder isso ainda" in resposta.text


def test_chat_segunda_pergunta_herda_filtro_de_autor(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bri.agent import roteador

    monkeypatch.setattr(
        roteador.buscar,
        "buscar",
        lambda *a, **k: [{"review_id": "1", "trecho": "texto", "score": 0.9}],
    )

    cliente.post("/chat", data={"pergunta": "desempenho do autor Herbert"})
    resposta = cliente.post("/chat", data={"pergunta": "o que os leitores criticam?"})

    assert "filtro herdado" in resposta.text.lower()
    assert "Frank Herbert" in resposta.text


def test_chat_duas_sessoes_nao_compartilham_estado(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import app
    from bri.agent import roteador

    monkeypatch.setattr(
        roteador.buscar,
        "buscar",
        lambda *a, **k: [{"review_id": "1", "trecho": "texto", "score": 0.9}],
    )

    c1, c2 = TestClient(app), TestClient(app)
    c1.post("/chat", data={"pergunta": "desempenho do autor Herbert"})
    resposta = c2.post("/chat", data={"pergunta": "o que os leitores criticam?"})

    assert "filtro herdado" not in resposta.text.lower()


def test_chat_cookie_criado_na_primeira_visita_e_mantido(cliente: TestClient) -> None:
    primeira = cliente.get("/chat")
    assert "sessao_id" in primeira.cookies

    segunda = cliente.get("/chat")
    assert segunda.cookies.get("sessao_id") is None  # não reescreve o mesmo id


def test_chat_limpar_filtro_remove_entidade_herdada(cliente: TestClient) -> None:
    cliente.post("/chat", data={"pergunta": "desempenho do autor Herbert"})
    assert "filtro herdado" in cliente.get("/chat").text.lower()

    cliente.post("/chat/limpar-filtro")

    assert "filtro herdado" not in cliente.get("/chat").text.lower()


def test_api_autores_com_ordenacao_invalida_devolve_400(cliente: TestClient) -> None:
    """Regressão: o ValueError da allowlist escapava da rota e virava 500 (erro do servidor)."""
    resposta = cliente.get("/api/autores", params={"ordenar_por": "'; DROP TABLE reviews; --"})

    assert resposta.status_code == 400
    assert "ordenação desconhecida" in resposta.json()["detail"]


def test_api_devolve_json(cliente: TestClient) -> None:
    dados = cliente.get("/api/autores").json()

    assert dados[0]["author"] == "Frank Herbert"
    assert cliente.get("/api/numeros").json()["reviews"] == 2


def test_entrevistas_mostra_pseudonimo_truncado(cliente: TestClient) -> None:
    """PII: a tela nunca mostra identificador inteiro (spec 05)."""
    corpo = cliente.get("/entrevistas").text

    assert "h1abcdef0123" in corpo
    assert "h1abcdef012345" not in corpo


def test_api_entrevistas_nao_vaza_hash_completo(cliente: TestClient) -> None:
    """Regressão: a API devolvia o user_hash inteiro, contornando o gate de PII que a tela aplica.

    A spec 04 exige confirmação humana para revelar o identificador — revelar em JSON sem gate
    nenhum é o mesmo vazamento, por outra porta.
    """
    linhas = cliente.get("/api/entrevistas").json()

    assert linhas
    corpo = str(linhas)
    assert "h1abcdef0123" in corpo
    assert "h1abcdef012345" not in corpo
    assert all("user_hash" not in linha for linha in linhas)


def test_aprovar_exporta_o_candidato(
    cliente: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(exportar, "RAIZ_EXPORTS", tmp_path)

    resposta = cliente.post("/entrevistas/aprovar", data={"prefixo": "h1abcdef0123"})

    assert resposta.status_code == 200
    assert "exportado" in resposta.text.lower()
    arquivos = list(tmp_path.glob("candidatos_entrevista_*.csv"))
    assert len(arquivos) == 1
    assert "h1abcdef012345" in arquivos[0].read_text(encoding="utf-8")


def test_aprovar_prefixo_inexistente_nao_exporta(
    cliente: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(exportar, "RAIZ_EXPORTS", tmp_path)

    resposta = cliente.post("/entrevistas/aprovar", data={"prefixo": "zzz"})

    assert resposta.status_code == 200
    assert "não encontrado" in resposta.text.lower()
    assert list(tmp_path.glob("*.csv")) == []
