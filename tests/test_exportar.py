"""Testa o export de candidato: CSV com cabeçalho, sem duplicata — sempre em tmp_path."""

from pathlib import Path

from bri.agent.exportar import CAMPOS, exportar_candidato

CANDIDATO_A = {
    "user_hash": "h1abcdef012345",
    "n_reviews": 5,
    "nota_media": 3.4,
    "comprimento_mediano": 823.0,
    "distancia_do_meio": 0.4,
}
CANDIDATO_B = {
    "user_hash": "h2ffffff999999",
    "n_reviews": 8,
    "nota_media": 2.9,
    "comprimento_mediano": 611.0,
    "distancia_do_meio": 0.1,
}


def test_primeira_chamada_cria_arquivo_com_cabecalho_e_uma_linha(tmp_path: Path) -> None:
    caminho = exportar_candidato(CANDIDATO_A, raiz=tmp_path)

    linhas = caminho.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == ",".join(CAMPOS)
    assert len(linhas) == 2


def test_segunda_chamada_acrescenta_sem_duplicar_cabecalho(tmp_path: Path) -> None:
    exportar_candidato(CANDIDATO_A, raiz=tmp_path)
    caminho = exportar_candidato(CANDIDATO_B, raiz=tmp_path)

    linhas = caminho.read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 3
    assert linhas.count(",".join(CAMPOS)) == 1


def test_mesmo_user_hash_no_mesmo_dia_nao_duplica(tmp_path: Path) -> None:
    exportar_candidato(CANDIDATO_A, raiz=tmp_path)
    caminho = exportar_candidato(CANDIDATO_A, raiz=tmp_path)

    linhas = caminho.read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 2  # cabeçalho + 1, não 2 linhas de dado


def test_justificativa_contem_os_numeros_certos(tmp_path: Path) -> None:
    caminho = exportar_candidato(CANDIDATO_A, raiz=tmp_path)

    conteudo = caminho.read_text(encoding="utf-8")
    assert "5 avaliações" in conteudo
    assert "823 caracteres" in conteudo
    assert "0.40 do meio" in conteudo


def test_cria_a_raiz_se_nao_existir(tmp_path: Path) -> None:
    raiz = tmp_path / "ainda" / "nao" / "existe"

    caminho = exportar_candidato(CANDIDATO_A, raiz=raiz)

    assert caminho.exists()
