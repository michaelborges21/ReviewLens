"""Testa a matemática do comparador de gabarito (spec 06) contra valores conferidos à mão.

O script roda sem teste desde que foi escrito: ele produz os números que a apresentação cita, e
uma métrica errada passaria como resultado ruim do modelo, não como bug. Nada aqui toca banco nem
LLM — são funções puras.
"""

import math

from evals.comparar_aspectos import (
    _normalizar,
    contar,
    kappa_cohen,
    micro_macro,
    prf,
    tabela_md,
)


def test_prf_com_metade_certa() -> None:
    """3 acertos, 1 falso positivo, 1 falso negativo: P=3/4, R=3/4, F1=P=R."""
    p, r, f1 = prf(tp=3, fp=1, fn=1)

    assert p == 0.75
    assert r == 0.75
    assert f1 == 0.75


def test_prf_sem_nenhuma_predicao_nao_divide_por_zero() -> None:
    assert prf(tp=0, fp=0, fn=5) == (0.0, 0.0, 0.0)
    assert prf(tp=0, fp=0, fn=0) == (0.0, 0.0, 0.0)


def test_prf_f1_e_media_harmonica() -> None:
    """P=1,0 e R=0,5 dão F1 0,667 — a média harmônica pune o desequilíbrio, a aritmética não."""
    p, r, f1 = prf(tp=1, fp=0, fn=1)

    assert (p, r) == (1.0, 0.5)
    assert round(f1, 3) == 0.667


def test_kappa_um_quando_so_existe_uma_classe() -> None:
    """Os dois dizem "positivo" sempre: o acaso explicaria todo o acerto, e kappa vale 1 por
    convenção, porque esperada == 1 e a fórmula dividiria por zero."""
    assert kappa_cohen([("positivo", "positivo")] * 10) == 1.0


def test_kappa_negativo_quando_discordam_mais_que_o_acaso() -> None:
    pares = [("positivo", "negativo"), ("negativo", "positivo")] * 5

    assert kappa_cohen(pares) < 0


def test_kappa_sem_par_nenhum_e_nan() -> None:
    assert math.isnan(kappa_cohen([]))


def test_contar_separa_deteccao_de_par_estrito() -> None:
    """Mesmo aspecto, sentimento diferente: detecção acerta, par estrito erra nos dois lados."""
    gabarito = {"r1": {"enredo": "positivo"}}
    predito = {"r1": {"enredo": "negativo"}}

    medido = contar(gabarito, predito, ["r1"])

    assert medido["deteccao"]["enredo"] == {"tp": 1, "fp": 0, "fn": 0}
    assert medido["estrito"]["enredo"] == {"tp": 0, "fp": 1, "fn": 1}
    assert medido["sentimentos"] == [("positivo", "negativo")]
    assert medido["exatas"] == 0


def test_contar_conta_linha_identica_como_exata() -> None:
    gabarito = {"r1": {"enredo": "positivo", "ritmo": "negativo"}}

    medido = contar(gabarito, gabarito, ["r1"])

    assert medido["exatas"] == 1
    assert medido["deteccao"]["enredo"]["tp"] == 1
    assert medido["estrito"]["ritmo"]["tp"] == 1


def test_contar_registra_confusao_de_aspecto_trocado() -> None:
    """Gabarito diz `ritmo`, IA diz `enredo`: é um par perdido/posto, não dois erros soltos."""
    gabarito = {"r1": {"ritmo": "negativo"}}
    predito = {"r1": {"enredo": "negativo"}}

    medido = contar(gabarito, predito, ["r1"])

    assert medido["confusoes"][("ritmo", "enredo")] == 1
    assert medido["deteccao"]["ritmo"] == {"tp": 0, "fp": 0, "fn": 1}
    assert medido["deteccao"]["enredo"] == {"tp": 0, "fp": 1, "fn": 0}


def test_micro_pondera_por_volume_e_macro_nao() -> None:
    """Aspecto raro perfeito e aspecto comum ruim: macro favorece o raro, micro não.

    enredo 1/100 certo (F1 ~0,02), preço 1/1 certo (F1 1,0). Macro é a média dos dois (~0,51);
    micro soma tudo antes de dividir, então o volume de enredo domina.
    """
    tabela = {
        "enredo": {"tp": 1, "fp": 99, "fn": 99},
        "preço": {"tp": 1, "fp": 0, "fn": 0},
    }

    (micro_p, micro_r, micro_f1), macro_f1 = micro_macro(tabela)

    assert round(micro_p, 3) == 0.02
    assert round(micro_r, 3) == 0.02
    assert round(macro_f1, 2) == 0.51
    assert micro_f1 < macro_f1


def test_micro_macro_ignora_aspecto_sem_suporte_no_macro() -> None:
    """Aspecto que só tem falso positivo não entra na média macro: não havia o que detectar."""
    tabela = {
        "enredo": {"tp": 1, "fp": 0, "fn": 0},
        "preço": {"tp": 0, "fp": 5, "fn": 0},
    }

    _, macro_f1 = micro_macro(tabela)

    assert macro_f1 == 1.0


def test_tabela_md_monta_cabecalho_separador_e_corpo() -> None:
    saida = tabela_md(["aspecto", "F1"], [["enredo", 0.9]])

    assert saida.splitlines() == [
        "| aspecto | F1 |",
        "|---|---|",
        "| enredo | 0.9 |",
    ]


def test_normalizar_aceita_planilha_preenchida_a_mao() -> None:
    """O CSV é anotado em planilha: acento, caixa e espaço variam e não deviam reprovar."""
    assert _normalizar("Edição Física") == "edição_física"
    assert _normalizar("edicao fisica") == "edição_física"
    assert _normalizar("traducao") == "tradução"
    assert _normalizar("  PREÇO  ") == "preço"


def test_normalizar_devolve_o_cru_quando_nao_reconhece() -> None:
    """Rótulo desconhecido vira anomalia visível no relatório, não erro silencioso."""
    assert _normalizar("capa dura") == "capa_dura"
