"""Testa checkpoint, retry e descarte de aspecto — nenhuma chamada real a LLM (fake no lugar)."""

import json
import re
from pathlib import Path

import duckdb
import pytest

from bri.nlp import extract


@pytest.fixture(autouse=True)
def isola_log_de_descarte(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nunca escrever no reports/ real: um bug no fake de teste já vazou pra lá uma vez."""
    monkeypatch.setattr(extract, "LOG_DESCARTES", tmp_path / "descartados-autouse.jsonl")


def _fake_valido(sistema: str, prompt: str, schema: dict) -> str:
    """Devolve um aspecto cuja evidência é sempre substring real do texto enviado."""
    review_id = re.search(r'id="([^"]+)"', prompt)
    # ancorado em <review ...>, não em qualquer ">\n" — <examples> também termina em ">\n".
    texto = re.search(r"<review[^>]*>\n(.*?)\n</review>", prompt, re.DOTALL)
    assert review_id and texto
    primeira_palavra = texto.group(1).split()[0]
    aspecto = {"aspect": "enredo", "sentiment": "positivo", "evidence": primeira_palavra}
    return json.dumps(
        {"review_id": review_id.group(1), "aspects": [aspecto], "is_recommendation": True}
    )


def _fake_evidencia_inventada(sistema: str, prompt: str, schema: dict) -> str:
    review_id = re.search(r'id="([^"]+)"', prompt)
    assert review_id
    return json.dumps(
        {
            "review_id": review_id.group(1),
            "aspects": [
                {"aspect": "enredo", "sentiment": "positivo", "evidence": "isto não está no texto"}
            ],
            "is_recommendation": True,
        }
    )


def _fake_json_invalido(sistema: str, prompt: str, schema: dict) -> str:
    return "isto não é um json válido"


@pytest.fixture
def banco_temp(tmp_path: Path) -> Path:
    caminho = tmp_path / "reviewlens.duckdb"
    con = duckdb.connect(str(caminho))
    con.execute("""
        CREATE TABLE enrichment_sample AS SELECT * FROM (VALUES
            ('1', 5.0, 'Adorei o livro, ritmo envolvente e personagens profundos.'),
            ('2', 2.0, 'A tradução é ruim e o final decepciona.'),
            ('3', 4.0, 'Boa leitura, recomendo sem ressalvas.'),
            ('4', 1.0, 'Capa amassada e edição descuidada, uma pena.')
        ) t(review_id, rating, review_text)
    """)
    con.close()
    return caminho


def test_already_done_le_jsonl_parcial(tmp_path: Path) -> None:
    caminho = tmp_path / "aspectos.jsonl"
    caminho.write_text('{"review_id": "1", "aspects": []}\n{"review_id": "2", "aspects": []}\n')

    assert extract.already_done(caminho) == {"1", "2"}


def test_already_done_sem_arquivo_devolve_vazio(tmp_path: Path) -> None:
    assert extract.already_done(tmp_path / "nao-existe.jsonl") == set()


def test_extrair_aceita_evidencia_literal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extract.ollama, "gerar_json", _fake_valido)

    resultado = extract.extrair(
        {"review_id": "1", "rating": 5.0, "texto": "Adorei o ritmo deste livro."}
    )

    assert resultado is not None
    assert len(resultado.aspects) == 1


def test_evidencia_nao_literal_descarta_so_o_aspecto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A review não é jogada fora inteira por causa de um aspecto com evidência inventada."""
    log = tmp_path / "descartados.jsonl"
    monkeypatch.setattr(extract, "LOG_DESCARTES", log)
    monkeypatch.setattr(extract.ollama, "gerar_json", _fake_evidencia_inventada)

    resultado = extract.extrair(
        {"review_id": "42", "rating": 3.0, "texto": "Um texto qualquer sobre o livro."}
    )

    assert resultado is not None
    assert resultado.aspects == []  # o único aspecto proposto foi descartado
    registros = [json.loads(linha) for linha in log.read_text().splitlines()]
    assert registros[0]["review_id"] == "42"
    assert registros[0]["motivo"] == "evidencia_nao_literal"


def test_schema_invalido_apos_retry_descarta_review_inteira(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "descartados.jsonl"
    monkeypatch.setattr(extract, "LOG_DESCARTES", log)
    monkeypatch.setattr(extract.ollama, "gerar_json", _fake_json_invalido)

    resultado = extract.extrair({"review_id": "9", "rating": 1.0, "texto": "texto qualquer"})

    assert resultado is None
    registros = [json.loads(linha) for linha in log.read_text().splitlines()]
    assert registros[0]["motivo"] == "schema_invalido_apos_retry"


def test_main_respeita_limite_e_retoma_de_onde_parou(
    banco_temp: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saida = tmp_path / "aspectos.jsonl"
    monkeypatch.setattr(extract, "BANCO", banco_temp)
    monkeypatch.setattr(extract, "SAIDA", saida)
    monkeypatch.setattr(extract.ollama, "gerar_json", _fake_valido)

    extract.main(limite=2)
    primeira_rodada = extract.already_done(saida)
    assert len(primeira_rodada) == 2

    extract.main(limite=2)
    segunda_rodada = extract.already_done(saida)
    assert len(segunda_rodada) == 4  # as 4 disponíveis: não reprocessou as 2 primeiras
    assert primeira_rodada < segunda_rodada


def test_carregar_no_banco_cria_tabela(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    saida = tmp_path / "aspectos.jsonl"
    saida.write_text(
        '{"review_id": "1", "aspects": [{"aspect": "enredo", "sentiment": "positivo", '
        '"evidence": "ótimo"}], "is_recommendation": true}\n'
    )
    banco = tmp_path / "reviewlens.duckdb"
    monkeypatch.setattr(extract, "SAIDA", saida)
    monkeypatch.setattr(extract, "BANCO", banco)

    extract.carregar_no_banco()

    con = duckdb.connect(str(banco), read_only=True)
    linhas = con.execute("SELECT review_id FROM review_enriched").fetchall()
    con.close()
    assert linhas == [("1",)]
