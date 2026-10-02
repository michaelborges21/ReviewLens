"""Compara um gabarito de aspectos com a extração que está no DuckDB (spec 06).

A predição não vem de CSV: vem do `review_enriched`, que é onde a extração de verdade mora —
assim não há risco de comparar contra um arquivo desatualizado.

Três níveis de métrica, porque os erros têm causas diferentes:
  1. DETECÇÃO  — achou o aspecto, ignorando o sentimento
  2. ESTRITO   — achou o par (aspecto, sentimento)
  3. SENTIMENTO condicional — dado que os dois viram o aspecto, concordaram no sentimento?

Duas armadilhas que o relatório trata explicitamente, porque ignorá-las infla o resultado:
  - **viés de seleção**: metade do golden foi escolhida onde a IA já dizia `ritmo`, então acerto
    nessa metade é garantido por construção. As métricas saem separadas por metade.
  - **qualidade do gabarito**: um gabarito que usa uma categoria como curinga desloca todas as
    métricas. A seção de diagnóstico compara a taxa de cada rótulo no gabarito com a taxa da IA no
    corpus inteiro, para esse tipo de viés aparecer como número, não como suposição.

Uso:
    uv run python evals/comparar_aspectos.py
    uv run python evals/comparar_aspectos.py --gabarito reports/evals/outro.csv
"""

import argparse
import csv
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, get_args

import duckdb

from bri.data.process import BANCO
from bri.schemas.aspectos import Aspecto, Sentimento
from bri.texto import sem_acento

# Derivados do schema, não copiados: aspectos.py se declara a fonte única das categorias, e uma
# segunda lista à mão aqui compararia contra a taxonomia velha em silêncio se ela mudar.
ASPECTOS = list(get_args(Aspecto))
SENTIMENTOS = list(get_args(Sentimento))
SEED = 42  # mesma do gerar_golden_aspectos.py: reconstrói qual metade foi dirigida a ritmo
N_DIRIGIDO = 100

# review_id -> aspecto -> sentimento. Dicionário, não conjunto de pares: um aspecto tem UM
# sentimento por review, e guardar assim elimina a escolha ambígua quando a extração repete o
# mesmo aspecto (ver `_sentimento_efetivo`) — com conjunto, a métrica variava entre execuções.
Rotulos = dict[str, dict[str, str]]


# aceita o rótulo sem acento e com variação de caixa/espaço: o CSV é preenchido à mão em planilha,
# e recusar "traducao" ou "Edição Física" por causa de acento seria rejeitar anotação correta.
_CANONICO = {}
for _rotulo in [*ASPECTOS, *SENTIMENTOS]:
    _CANONICO[_rotulo] = _rotulo
    _CANONICO[sem_acento(_rotulo)] = _rotulo


def _normalizar(valor: str) -> str:
    """Forma canônica do rótulo. Devolve o valor cru quando não reconhece — para virar anomalia."""
    limpo = valor.strip().lower().replace(" ", "_").replace("-", "_")
    return _CANONICO.get(limpo, limpo)


def rotulos_do_gabarito(caminho: Path) -> tuple[Rotulos, dict[str, str], list[dict[str, str]]]:
    """Lê o CSV anotado, normaliza os rótulos e registra o que não couber no schema.

    Anomalia não é descartada em silêncio: aspecto sem sentimento, rótulo inválido ou aspecto
    repetido na mesma linha viram relatório, porque em CSV preenchido à mão é erro de digitação
    que some no meio de 200 linhas.
    """
    with caminho.open(encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    rotulos: Rotulos = {}
    textos: dict[str, str] = {}
    anomalias: list[dict[str, str]] = []
    for linha in linhas:
        review_id = str(linha["review_id"])
        textos[review_id] = linha.get("texto", "")
        por_aspecto: dict[str, str] = {}
        for k in range(1, 5):
            aspecto = _normalizar(linha.get(f"aspecto_{k}", ""))
            sentimento = _normalizar(linha.get(f"sentimento_{k}", ""))
            if not aspecto and not sentimento:
                continue
            problema = ""
            if not aspecto:
                problema = f"sentimento_{k}=`{sentimento}` sem aspecto"
            elif aspecto not in ASPECTOS:
                problema = f"aspecto_{k} fora do schema: `{aspecto}`"
            elif not sentimento:
                problema = f"aspecto_{k}=`{aspecto}` sem sentimento"
            elif sentimento not in SENTIMENTOS:
                problema = f"sentimento_{k} fora do schema: `{sentimento}`"
            elif aspecto in por_aspecto:
                problema = f"aspecto_{k} repetido na linha: `{aspecto}`"
            if problema:
                anomalias.append({"review_id": review_id, "problema": problema})
                continue
            por_aspecto[aspecto] = sentimento
        rotulos[review_id] = por_aspecto
    return rotulos, textos, anomalias


def _sentimento_efetivo(sentimentos: set[str]) -> str:
    """Um sentimento por aspecto. Quando a extração emitiu mais de um para o mesmo aspecto, isso
    é ambivalência escrita em duas linhas — que é o que `misto` significa."""
    return sentimentos.pop() if len(sentimentos) == 1 else "misto"


def rotulos_da_extracao(
    con: duckdb.DuckDBPyConnection, ids: list[str]
) -> tuple[Rotulos, dict[str, Counter[str]]]:
    """A extração da IA, do review_enriched. Devolve também a contagem por aspecto, para relatar
    aspecto repetido — que o colapso em um sentimento por aspecto esconderia."""
    linhas = con.execute(
        """
        SELECT re.review_id, (a).aspect, (a).sentiment
        FROM review_enriched re, UNNEST(re.aspects) AS t(a)
        WHERE re.review_id IN (SELECT unnest(?))
        """,
        [ids],
    ).fetchall()
    bruto: dict[str, dict[str, set[str]]] = {i: defaultdict(set) for i in ids}
    repeticoes: dict[str, Counter[str]] = {i: Counter() for i in ids}
    for review_id, aspecto, sentimento in linhas:
        bruto[str(review_id)][aspecto].add(sentimento)
        repeticoes[str(review_id)][aspecto] += 1
    rotulos: Rotulos = {
        review_id: {a: _sentimento_efetivo(set(s)) for a, s in por_aspecto.items()}
        for review_id, por_aspecto in bruto.items()
    }
    return rotulos, repeticoes


def dirigidos_a_ritmo(con: duckdb.DuckDBPyConnection) -> set[str]:
    """Reconstrói a metade escolhida pelo critério `ritmo` — mesma query e seed da geração."""
    return {
        str(linha[0])
        for linha in con.execute(
            """
            SELECT re.review_id FROM review_enriched re
            JOIN enrichment_sample es ON es.review_id = re.review_id
            WHERE EXISTS (SELECT 1 FROM UNNEST(re.aspects) AS t(a) WHERE (a).aspect = 'ritmo')
            ORDER BY hash(re.review_id || CAST(? AS VARCHAR)) LIMIT ?
            """,
            [SEED, N_DIRIGIDO],
        ).fetchall()
    }


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def kappa_cohen(pares: list[tuple[str, str]]) -> float:
    """Concordância de sentimento descontando o acerto que o acaso explicaria."""
    if not pares:
        return float("nan")
    n = len(pares)
    observada = sum(1 for g, p in pares if g == p) / n
    cg, cp = Counter(g for g, _ in pares), Counter(p for _, p in pares)
    esperada = sum((cg[c] / n) * (cp[c] / n) for c in set(cg) | set(cp))
    return (observada - esperada) / (1 - esperada) if esperada < 1 else 1.0


def contar(gabarito: Rotulos, predito: Rotulos, ids: list[str]) -> dict[str, Any]:
    """Conta TP/FP/FN por aspecto nos dois níveis, mais sentimento e confusões."""
    deteccao: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    estrito: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    sentimentos: list[tuple[str, str]] = []
    trocas: Counter[tuple[str, str]] = Counter()
    confusoes: Counter[tuple[str, str]] = Counter()
    exatas = 0

    for review_id in ids:
        rg, rp = gabarito[review_id], predito.get(review_id, {})
        ag, ap = set(rg), set(rp)

        for aspecto in ag & ap:
            deteccao[aspecto]["tp"] += 1
            sentimentos.append((rg[aspecto], rp[aspecto]))
            trocas[(rg[aspecto], rp[aspecto])] += 1
            if rg[aspecto] == rp[aspecto]:
                estrito[aspecto]["tp"] += 1
            else:
                estrito[aspecto]["fp"] += 1
                estrito[aspecto]["fn"] += 1
        for aspecto in ap - ag:
            deteccao[aspecto]["fp"] += 1
            estrito[aspecto]["fp"] += 1
        for aspecto in ag - ap:
            deteccao[aspecto]["fn"] += 1
            estrito[aspecto]["fn"] += 1
        for perdido in ag - ap:
            for posto in ap - ag:
                confusoes[(perdido, posto)] += 1

        exatas += rg == rp

    return {
        "deteccao": deteccao,
        "estrito": estrito,
        "sentimentos": sentimentos,
        "trocas": trocas,
        "confusoes": confusoes,
        "exatas": exatas,
        "n": len(ids),
    }


def micro_macro(tabela: dict[str, dict[str, int]]) -> tuple[tuple[float, float, float], float]:
    tp = sum(v["tp"] for v in tabela.values())
    fp = sum(v["fp"] for v in tabela.values())
    fn = sum(v["fn"] for v in tabela.values())
    f1s = [prf(v["tp"], v["fp"], v["fn"])[2] for v in tabela.values() if v["tp"] + v["fn"]]
    return prf(tp, fp, fn), (sum(f1s) / len(f1s) if f1s else 0.0)


def tabela_md(cabecalho: list[str], linhas: list[list[Any]]) -> str:
    topo = "| " + " | ".join(cabecalho) + " |"
    sep = "|" + "|".join("---" for _ in cabecalho) + "|"
    corpo = ["| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas]
    return "\n".join([topo, sep, *corpo])


def _tabela_por_aspecto(deteccao: dict[str, dict[str, int]]) -> str:
    linhas = []
    for aspecto in ASPECTOS:
        v = deteccao[aspecto]
        if not (v["tp"] or v["fp"] or v["fn"]):
            continue
        p, r, f = prf(v["tp"], v["fp"], v["fn"])
        linhas.append(
            [
                aspecto,
                v["tp"] + v["fn"],
                v["tp"],
                v["fp"],
                v["fn"],
                f"{p:.3f}",
                f"{r:.3f}",
                f"{f:.3f}",
            ]
        )
    return tabela_md(["aspecto", "suporte", "TP", "FP", "FN", "P", "R", "F1"], linhas)


def _tipo_de_erro(gabarito_linha: dict[str, str], predito_linha: dict[str, str]) -> str:
    ag, ap = set(gabarito_linha), set(predito_linha)
    tipos = []
    if ag - ap:
        tipos.append("aspecto_nao_detectado")
    if ap - ag:
        tipos.append("aspecto_alucinado")
    if any(gabarito_linha[a] != predito_linha[a] for a in ag & ap):
        tipos.append("sentimento_divergente")
    return "+".join(tipos)


def dump_discordancias(
    gabarito: Rotulos,
    predito: Rotulos,
    textos: dict[str, str],
    destino: Path,
    chars_texto: int,
) -> int:
    """Grava uma linha por discordância, com o texto ao lado — é o material de trabalho para uma
    pessoa adjudicar caso a caso, que nenhuma métrica agregada substitui."""
    campos = [
        "review_id",
        "tipo_erro",
        "gabarito",
        "ia",
        "faltou",
        "sobrou",
        "sentimento_trocado",
        "texto",
    ]
    linhas = []
    for review_id, rg in gabarito.items():
        rp = predito.get(review_id, {})
        if rg == rp:
            continue
        ag, ap = set(rg), set(rp)
        trocados = sorted(f"{a}: {rg[a]}→{rp[a]}" for a in ag & ap if rg[a] != rp[a])
        texto = str(textos.get(review_id, "")).replace("\n", " ")
        linhas.append(
            {
                "review_id": review_id,
                "tipo_erro": _tipo_de_erro(rg, rp),
                "gabarito": " ; ".join(sorted(f"{a}/{s}" for a, s in rg.items())) or "(vazio)",
                "ia": " ; ".join(sorted(f"{a}/{s}" for a, s in rp.items())) or "(vazio)",
                "faltou": " ; ".join(sorted(f"{a}/{rg[a]}" for a in ag - ap)),
                "sobrou": " ; ".join(sorted(f"{a}/{rp[a]}" for a in ap - ag)),
                "sentimento_trocado": " ; ".join(trocados),
                "texto": texto[:chars_texto] + ("..." if len(texto) > chars_texto else ""),
            }
        )
    linhas.sort(key=lambda linha: (linha["tipo_erro"], linha["review_id"]))
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)
    return len(linhas)


def _cabecalho(caminho_gabarito: Path, n_linhas: int) -> list[str]:
    return [
        "# Gabarito de aspectos vs extração da IA",
        "",
        f"- gabarito: `{caminho_gabarito}`",
        "- predição: tabela `review_enriched` do DuckDB",
        f"- linhas comparadas: **{n_linhas}**",
        f"- gerado em {date.today().isoformat()}",
        "",
    ]


def _secao_visao_geral(todos: dict[str, Any], n_linhas: int) -> list[str]:
    (mp, mr, mf), macro = micro_macro(todos["deteccao"])
    (ep, er, ef), macro_e = micro_macro(todos["estrito"])
    return [
        "## 1. Visão geral (todas as linhas)",
        "",
        f"- conjunto idêntico: **{todos['exatas']}/{n_linhas}** ({todos['exatas'] / n_linhas:.1%})",
        f"- detecção: micro P {mp:.3f} / R {mr:.3f} / **F1 {mf:.3f}** | macro F1 {macro:.3f}",
        f"- par estrito: micro P {ep:.3f} / R {er:.3f} / **F1 {ef:.3f}** | macro F1 {macro_e:.3f}",
        "",
        "> Estes números somam as duas metades do golden e **não** estimam o corpus: metade foi",
        "> escolhida onde a IA já dizia `ritmo`. Use a seção 2.",
        "",
    ]


def _secao_metades(
    aleatoria: dict[str, Any],
    dirigida: dict[str, Any],
    n_aleatoria: int,
    n_dirigida: int,
) -> list[str]:
    """A metade dirigida a `ritmo` acerta por construção; só a aleatória estima o corpus."""
    (ap_, ar, af), _ = micro_macro(aleatoria["deteccao"])
    (dp_, dr, df_), _ = micro_macro(dirigida["deteccao"])
    return [
        "## 2. Metade aleatória vs metade dirigida",
        "",
        tabela_md(
            ["metade", "n", "P", "R", "F1", "conjunto idêntico"],
            [
                [
                    "aleatória (estima o corpus)",
                    n_aleatoria,
                    f"{ap_:.3f}",
                    f"{ar:.3f}",
                    f"**{af:.3f}**",
                    f"{aleatoria['exatas']}/{n_aleatoria}",
                ],
                [
                    "dirigida a `ritmo` (enviesada)",
                    n_dirigida,
                    f"{dp_:.3f}",
                    f"{dr:.3f}",
                    f"{df_:.3f}",
                    f"{dirigida['exatas']}/{n_dirigida}",
                ],
            ],
        ),
        "",
        "### Detecção por aspecto — só a metade aleatória",
        "",
        _tabela_por_aspecto(aleatoria["deteccao"]),
        "",
        "Um aspecto com recall 0 aqui e recall alto na seção 1 é subdetectado de verdade: o número",
        "bom vem da metade que foi selecionada pela própria resposta da IA.",
        "",
    ]


def _secao_sentimento(todos: dict[str, Any]) -> list[str]:
    pares_sent = todos["sentimentos"]
    acerto = sum(1 for g, p in pares_sent if g == p) / len(pares_sent) if pares_sent else 0.0
    com_misto = [(g, p) for g, p in pares_sent if g == "misto"]
    sem_misto = [(g, p) for g, p in pares_sent if g != "misto"]
    acerto_sem = sum(1 for g, p in sem_misto if g == p) / len(sem_misto) if sem_misto else 0.0
    acerto_com = sum(1 for g, p in com_misto if g == p) / len(com_misto) if com_misto else 0.0
    secao = [
        "## 3. Sentimento (só aspectos que os dois detectaram)",
        "",
        f"n = {len(pares_sent)} | accuracy **{acerto:.3f}** | kappa de Cohen "
        f"**{kappa_cohen(pares_sent):.3f}**",
        "",
        tabela_md(
            ["gabarito \\ predito", *SENTIMENTOS, "total"],
            [
                [
                    f"**{sg}**",
                    *[todos["trocas"][(sg, sp)] for sp in SENTIMENTOS],
                    sum(todos["trocas"][(sg, sp)] for sp in SENTIMENTOS),
                ]
                for sg in SENTIMENTOS
            ],
        ),
        "",
        f"- casos em que o gabarito disse `misto`: **{len(com_misto)}**, "
        f"acerto **{acerto_com:.1%}**",
        f"- casos não-`misto`: {len(sem_misto)}, acerto **{acerto_sem:.1%}**",
        "",
    ]
    if com_misto and acerto_com < 0.2:
        secao += [
            "> O eixo de sentimento só é fraco onde o gabarito pede `misto`. Fora disso a",
            "> concordância é alta — o defeito é o modelo colapsar ambivalência em positivo ou",
            "> negativo, não errar polaridade.",
            "",
        ]
    return secao


def _secao_anomalias_da_extracao(
    repeticoes: dict[str, Counter[str]], predito: Rotulos, ids: list[str]
) -> list[str]:
    """Independe do gabarito: o que a extração fez de estranho por conta própria."""
    duplicados = {i: c for i, c in repeticoes.items() if any(n > 1 for n in c.values())}
    vazios = [i for i in ids if not predito.get(i)]
    secao = [
        "## 4. Anomalias na extração (independem do gabarito)",
        "",
        f"- linhas em que a IA repetiu o mesmo aspecto: **{len(duplicados)}/{len(ids)}** "
        f"({len(duplicados) / len(ids):.1%})",
        f"- linhas em que a IA não extraiu aspecto nenhum: **{len(vazios)}**",
        "",
    ]
    if duplicados:
        exemplos = []
        for review_id, contagem in list(duplicados.items())[:5]:
            repetido = ", ".join(f"`{a}`×{n}" for a, n in contagem.items() if n > 1)
            exemplos.append(
                [
                    review_id,
                    repetido,
                    " ; ".join(sorted(f"{a}/{s}" for a, s in predito[review_id].items())),
                ]
            )
        secao += [tabela_md(["review_id", "repetido", "extração completa"], exemplos), ""]
        secao += [
            "Aspecto repetido com sentimentos opostos é ambivalência escrita como duas linhas —",
            "exatamente o caso que o rótulo `misto` existe para cobrir.",
            "",
        ]
    return secao


def _secao_diagnostico_do_gabarito(
    con: duckdb.DuckDBPyConnection, gabarito: Rotulos, ids: list[str]
) -> list[str]:
    """Compara a taxa de cada rótulo no gabarito com a taxa da IA no corpus inteiro.

    É o que faz um gabarito-curinga aparecer como número em vez de suposição.
    """
    taxa_corpus = dict(
        con.execute(
            """
            SELECT (a).aspect,
                   count(DISTINCT re.review_id) * 100.0 / (SELECT count(*) FROM review_enriched)
            FROM review_enriched re, UNNEST(re.aspects) AS t(a)
            GROUP BY 1
            """
        ).fetchall()
    )
    diag = []
    for aspecto in ASPECTOS:
        no_gabarito = sum(1 for i in ids if aspecto in gabarito[i])
        if not no_gabarito and aspecto not in taxa_corpus:
            continue
        pct_gab = no_gabarito * 100.0 / len(ids)
        pct_corpus = float(taxa_corpus.get(aspecto, 0.0))
        diag.append(
            [
                aspecto,
                no_gabarito,
                f"{pct_gab:.1f}%",
                f"{pct_corpus:.1f}%",
                f"{pct_gab - pct_corpus:+.1f} pp",
            ]
        )
    return [
        "## 5. Diagnóstico do gabarito",
        "",
        "Se o gabarito usa um rótulo muito acima da taxa da IA no corpus inteiro, ele pode estar",
        "servindo de curinga — e aí o F1 daquela categoria mede critério divergente, não erro.",
        "",
        tabela_md(
            ["aspecto", "linhas no gabarito", "% gabarito", "% corpus (IA)", "diferença"], diag
        ),
        "",
    ]


def _secao_confusoes(todos: dict[str, Any]) -> list[str]:
    if not todos["confusoes"]:
        return []
    return [
        "## 6. Confusões mais comuns (gabarito perdeu → IA pôs no lugar)",
        "",
        tabela_md(
            ["gabarito", "IA", "n"],
            [[g, p, n] for (g, p), n in todos["confusoes"].most_common(8)],
        ),
        "",
    ]


def _secao_rotulos_fora_do_schema(anomalias_gabarito: list[dict[str, str]]) -> list[str]:
    secao = ["## 7. Rótulos do gabarito fora do schema", ""]
    if not anomalias_gabarito:
        return [*secao, "Nenhum: todos os rótulos caem nas 9 categorias e nos 4 sentimentos.", ""]
    por_problema = Counter(a["problema"].split(":")[0] for a in anomalias_gabarito)
    return [
        *secao,
        f"**{len(anomalias_gabarito)}** rótulo(s) recusado(s) na leitura do CSV:",
        "",
        tabela_md(["problema", "n"], [[p, n] for p, n in por_problema.most_common()]),
        "",
        "Detalhe: "
        + "; ".join(f"`{a['review_id']}` {a['problema']}" for a in anomalias_gabarito[:10]),
        "",
    ]


def _secao_adjudicacao(caminho_dump: Path, n_dump: int) -> list[str]:
    return [
        "## 8. Material para adjudicação humana",
        "",
        f"As **{n_dump}** linhas em que gabarito e IA divergem estão em `{caminho_dump}`, com o",
        "texto da avaliação ao lado das duas propostas. Adjudicar (escolher entre duas opções) é",
        "bem mais rápido que rotular em branco — caminho mais curto para um gabarito confiável.",
        "",
    ]


def relatorio(
    con: duckdb.DuckDBPyConnection,
    caminho_gabarito: Path,
    gabarito: Rotulos,
    predito: Rotulos,
    repeticoes: dict[str, Counter[str]],
    anomalias_gabarito: list[dict[str, str]],
    caminho_dump: Path,
    n_dump: int,
) -> str:
    """Monta o relatório inteiro: cada seção é uma função, nesta ordem."""
    ids = list(gabarito)
    dirigidos = dirigidos_a_ritmo(con)
    metade_dirigida = [i for i in ids if i in dirigidos]
    metade_aleatoria = [i for i in ids if i not in dirigidos]

    todos = contar(gabarito, predito, ids)
    aleatoria = contar(gabarito, predito, metade_aleatoria)
    dirigida = contar(gabarito, predito, metade_dirigida)

    return "\n".join(
        [
            *_cabecalho(caminho_gabarito, len(ids)),
            *_secao_visao_geral(todos, len(ids)),
            *_secao_metades(aleatoria, dirigida, len(metade_aleatoria), len(metade_dirigida)),
            *_secao_sentimento(todos),
            *_secao_anomalias_da_extracao(repeticoes, predito, ids),
            *_secao_diagnostico_do_gabarito(con, gabarito, ids),
            *_secao_confusoes(todos),
            *_secao_rotulos_fora_do_schema(anomalias_gabarito),
            *_secao_adjudicacao(caminho_dump, n_dump),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gabarito",
        type=Path,
        default=Path("reports/evals/golden_aspectos_anotado_claude.csv"),
    )
    parser.add_argument("--saida", type=Path, default=None)
    parser.add_argument("--dump", type=Path, default=None)
    parser.add_argument(
        "--chars-texto",
        type=int,
        default=260,
        help="quanto do texto da avaliação vai no dump de discordâncias (0 = nenhum)",
    )
    args = parser.parse_args()

    hoje = date.today().isoformat()
    saida = args.saida or Path(f"reports/evals/relatorio_golden_{hoje}.md")
    dump = args.dump or Path(f"reports/evals/discordancias_{hoje}.csv")

    gabarito, textos, anomalias = rotulos_do_gabarito(args.gabarito)
    with duckdb.connect(str(BANCO), read_only=True) as con:
        predito, repeticoes = rotulos_da_extracao(con, list(gabarito))
        n_dump = dump_discordancias(gabarito, predito, textos, dump, args.chars_texto)
        texto = relatorio(
            con, args.gabarito, gabarito, predito, repeticoes, anomalias, dump, n_dump
        )

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"\n[ok] relatório: {saida}")
    print(f"[ok] discordâncias ({n_dump} linhas): {dump}")


if __name__ == "__main__":
    main()
