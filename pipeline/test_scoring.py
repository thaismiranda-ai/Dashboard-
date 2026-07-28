"""Testes da classificação RFM.

O objetivo destes testes não é provar que o código faz o que eu quis — é provar
que ele faz o que os segmentos 1952–1958 do Customer.io fazem. Cada caso cita a
regra de produção que está verificando.

Rodar: python3 pipeline/test_scoring.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scoring import (  # noqa: E402
    ARCHETYPE_RANK,
    ARCHETYPES,
    classify,
    score_player,
    value_tier,
)


# -----------------------------------------------------------------------------
# Fronteiras de recência — transcritas dos `description` dos segmentos
# -----------------------------------------------------------------------------

def test_fronteiras_de_recencia():
    # 1954: "depositou <=7d E 1x/30d"
    assert classify(0, 1) == "Promising"
    assert classify(7, 1) == "Promising"
    # 1955: "depositou 8-30d atras"
    assert classify(8, 1) == "Need Attention"
    assert classify(30, 9) == "Need Attention"
    # 1956: "ultimo deposito 31-90d atras"
    assert classify(31, 9) == "At Risk"
    assert classify(90, 9) == "At Risk"
    # 1957: "ultimo deposito 91-180d atras"
    assert classify(91, 0) == "Hibernating"
    assert classify(180, 0) == "Hibernating"
    # 1958: "ultimo deposito >180d"
    assert classify(181, 0) == "Lost"
    assert classify(3650, 0) == "Lost"


def test_fronteiras_de_frequencia_na_faixa_quente():
    # 1952 Champions: ">=4x/30d" · 1953 Loyal: "2-3x/30d" · 1954: "1x/30d"
    assert classify(3, 1) == "Promising"
    assert classify(3, 2) == "Loyal"
    assert classify(3, 3) == "Loyal"
    assert classify(3, 4) == "Champions"
    assert classify(3, 40) == "Champions"


def test_frequencia_so_vale_na_faixa_quente():
    # Depositar muito não salva quem sumiu: a partir de 8 dias, só a recência
    # decide. É assim que os segmentos funcionam — Need Attention/At Risk/
    # Hibernating/Lost não olham contagem.
    assert classify(45, 30) == "At Risk"
    assert classify(200, 99) == "Lost"


# -----------------------------------------------------------------------------
# A base classificada é só quem já depositou (segmento 1941)
# -----------------------------------------------------------------------------

def test_quem_nunca_depositou_fica_fora_da_base():
    # None (nunca depositou) não é "Lost" — é fora da classificação. Chamar de
    # Lost inflaria o pior balde com ~250 mil perfis que nunca foram clientes.
    assert classify(None, 0) is None
    assert score_player(None).archetype is None
    assert score_player(None).archetype_rank is None


# -----------------------------------------------------------------------------
# Propriedades estruturais
# -----------------------------------------------------------------------------

def test_toda_recencia_possivel_tem_arquetipo():
    for dias in range(0, 400):
        for freq in (0, 1, 2, 3, 4, 10):
            a = classify(dias, freq)
            assert a in ARCHETYPES, f"dias={dias} freq={freq} -> {a!r}"


def test_recencia_maior_nunca_melhora_o_arquetipo():
    # Sumir por mais tempo não pode promover ninguém. Sem esta propriedade, a
    # matriz de migração acusaria "recuperou" para quem só ficou parado.
    for freq in (0, 1, 2, 3, 4, 10):
        ranks = [ARCHETYPE_RANK[classify(d, freq)] for d in range(0, 400)]
        assert ranks == sorted(ranks), f"freq={freq}: ordem quebrada"


def test_mais_depositos_nunca_piora_o_arquetipo():
    for dias in range(0, 400):
        ranks = [ARCHETYPE_RANK[classify(dias, f)] for f in range(0, 12)]
        assert ranks == sorted(ranks, reverse=True), f"dias={dias}: ordem quebrada"


def test_ranks_sao_unicos_e_ordenados():
    assert list(ARCHETYPE_RANK.values()) == list(range(1, 8))
    assert ARCHETYPE_RANK["Champions"] < ARCHETYPE_RANK["Lost"]


# -----------------------------------------------------------------------------
# Eixo de valor — separado da classificação, de propósito
# -----------------------------------------------------------------------------

def test_faixas_de_valor():
    assert value_tier(5000) == "Alto"
    assert value_tier(2000) == "Alto"
    assert value_tier(1999.99) == "Médio"
    assert value_tier(500) == "Médio"
    assert value_tier(499.99) == "Baixo"
    assert value_tier(50) == "Baixo"
    assert value_tier(49.99) == "Mínimo"
    assert value_tier(0) == "Mínimo"
    assert value_tier(None) == "Mínimo"


def test_valor_nao_influencia_o_arquetipo():
    # O ponto central do módulo: quem depositou R$ 20 e quem depositou R$ 8.000
    # na mesma semana caem no mesmo arquétipo. É a regra de produção, e é o
    # buraco que a análise de LTV existe para cobrir.
    magro = score_player(3, 1, 20.0)
    gordo = score_player(3, 1, 8000.0)
    assert magro.archetype == gordo.archetype == "Promising"
    assert magro.value_tier == "Mínimo"
    assert gordo.value_tier == "Alto"


# -----------------------------------------------------------------------------
# Casos do jeito que o time de CRM descreveria
# -----------------------------------------------------------------------------

def test_perfis_reconheciveis():
    assert score_player(1, 6, 5000.0).archetype == "Champions"   # deposita toda semana
    assert score_player(2, 2, 400.0).archetype == "Loyal"        # regular, valor médio
    assert score_player(5, 1, 100.0).archetype == "Promising"    # depositou uma vez
    assert score_player(20, 3, 800.0).archetype == "Need Attention"  # esfriando
    assert score_player(60, 8, 3000.0).archetype == "At Risk"    # bom e sumindo
    assert score_player(120, 0, 0.0).archetype == "Hibernating"
    assert score_player(400, 0, 0.0).archetype == "Lost"


if __name__ == "__main__":
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
