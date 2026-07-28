"""Testes da classificação RFM.

Rodar: python3 -m pytest pipeline/test_scoring.py -q
(ou `python3 pipeline/test_scoring.py` para um resumo sem pytest)
"""

from __future__ import annotations

import itertools

from scoring import (
    ARCHETYPE_RANK,
    ARCHETYPES,
    classify,
    combine_fm,
    score_frequency,
    score_monetary,
    score_player,
    score_recency,
)


# -----------------------------------------------------------------------------
# A grade precisa ser total e determinística. Uma célula sem dono vira jogador
# sumido do dashboard sem ninguém perceber.
# -----------------------------------------------------------------------------

def test_grade_cobre_as_25_celulas():
    for r, fm in itertools.product(range(1, 6), repeat=2):
        archetype = classify(r, fm)
        assert archetype in ARCHETYPES, f"R={r} FM={fm} devolveu {archetype!r}"


def test_grade_bate_com_a_tabela_do_docstring():
    esperado = {
        # (r, fm): arquétipo
        **{(5, fm): a for fm, a in zip(range(1, 6), ["Promising", "Promising", "Loyal", "Champions", "Champions"])},
        **{(4, fm): a for fm, a in zip(range(1, 6), ["Promising", "Promising", "Loyal", "Champions", "Champions"])},
        **{(3, fm): a for fm, a in zip(range(1, 6), ["Need Attention", "Need Attention", "Need Attention", "Loyal", "Loyal"])},
        **{(2, fm): a for fm, a in zip(range(1, 6), ["Hibernating", "Hibernating", "At Risk", "At Risk", "At Risk"])},
        **{(1, fm): "Lost" for fm in range(1, 6)},
    }
    for (r, fm), archetype in esperado.items():
        assert classify(r, fm) == archetype, f"R={r} FM={fm}"


def test_ranks_sao_unicos_e_ordenados():
    assert list(ARCHETYPE_RANK.values()) == list(range(1, 8))
    assert ARCHETYPE_RANK["Champions"] < ARCHETYPE_RANK["Lost"]


# -----------------------------------------------------------------------------
# Monotonicidade: melhorar uma métrica nunca pode piorar o arquétipo. Sem isso,
# a matriz de migração acusaria "piorou" para quem melhorou.
# -----------------------------------------------------------------------------

def test_melhorar_r_nunca_piora_o_arquetipo():
    for fm in range(1, 6):
        ranks = [ARCHETYPE_RANK[classify(r, fm)] for r in range(1, 6)]
        assert ranks == sorted(ranks, reverse=True), f"FM={fm}: {ranks}"


def test_melhorar_fm_nunca_piora_o_arquetipo():
    for r in range(1, 6):
        ranks = [ARCHETYPE_RANK[classify(r, fm)] for fm in range(1, 6)]
        assert ranks == sorted(ranks, reverse=True), f"R={r}: {ranks}"


# -----------------------------------------------------------------------------
# Cortes
# -----------------------------------------------------------------------------

def test_recencia_nas_bordas():
    assert score_recency(0) == 5
    assert score_recency(7) == 5
    assert score_recency(8) == 4
    assert score_recency(14) == 4
    assert score_recency(15) == 3
    assert score_recency(30) == 3
    assert score_recency(31) == 2
    assert score_recency(60) == 2
    assert score_recency(61) == 1
    assert score_recency(9999) == 1


def test_quem_nunca_apostou_e_o_pior_caso_nao_um_buraco():
    assert score_recency(None) == 1
    assert score_frequency(None) == 1
    assert score_monetary(None) == 1
    assert score_player(None, None, None).archetype == "Lost"


def test_frequencia_e_monetario_nas_bordas():
    assert score_frequency(60) == 5
    assert score_frequency(59) == 4
    assert score_frequency(3) == 2
    assert score_frequency(2) == 1
    assert score_frequency(0) == 1

    assert score_monetary(2000.0) == 5
    assert score_monetary(1999.99) == 4
    assert score_monetary(50.0) == 2
    assert score_monetary(49.99) == 1


def test_combine_fm_arredonda_para_cima_no_meio():
    # O .5 tem que subir. round() puro do Python usaria arredondamento
    # bancário e mandaria (2,3) para baixo.
    assert combine_fm(2, 3) == 3
    assert combine_fm(3, 4) == 4
    assert combine_fm(4, 5) == 5
    assert combine_fm(1, 2) == 2
    assert combine_fm(3, 3) == 3
    assert combine_fm(5, 5) == 5
    assert combine_fm(1, 1) == 1


def test_combine_fm_fica_sempre_na_faixa_1_a_5():
    for f, m in itertools.product(range(1, 6), repeat=2):
        assert 1 <= combine_fm(f, m) <= 5


# -----------------------------------------------------------------------------
# Casos concretos, do jeito que o time de CRM descreveria
# -----------------------------------------------------------------------------

def test_perfis_reconheciveis():
    # Apostou ontem, 80 apostas em 90 dias, R$ 5 mil depositados.
    assert score_player(1, 80, 5000.0).archetype == "Champions"

    # Cadastrou essa semana, apostou 2 vezes, R$ 30.
    assert score_player(2, 2, 30.0).archetype == "Promising"

    # Era bom, sumiu há 45 dias, mas gastava alto.
    assert score_player(45, 40, 3000.0).archetype == "At Risk"

    # Sumiu há 6 meses.
    assert score_player(180, 0, 0.0).archetype == "Lost"

    # Nunca foi grande coisa e está frio há 40 dias.
    assert score_player(40, 1, 20.0).archetype == "Hibernating"

    # Está esfriando: última aposta há 20 dias, volume médio.
    assert score_player(20, 10, 300.0).archetype == "Need Attention"


def test_score_player_e_internamente_coerente():
    r = score_player(10, 25, 900.0)
    assert r.fm_score == combine_fm(r.f_score, r.m_score)
    assert r.archetype == classify(r.r_score, r.fm_score)
    assert r.archetype_rank == ARCHETYPE_RANK[r.archetype]


if __name__ == "__main__":
    import sys

    falhas = []
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas.append((t.__name__, e))
    for nome, e in falhas:
        print(f"FALHOU {nome}: {e}")
    print(f"{len(testes) - len(falhas)}/{len(testes)} testes passaram")
    sys.exit(1 if falhas else 0)
