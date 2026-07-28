"""Teste ponta a ponta do build_rows com um cliente falso.

Verifica que as peças encaixam — agregação, classificação, formato de linha —
sem tocar na rede. O que este teste NÃO cobre é o contrato real com a API do
Customer.io: se um campo mudar de nome lá, aqui continua passando. Essa parte
só a primeira execução com credencial verifica.

Rodar: python3 pipeline/test_pipeline.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cio_client import EVENT_BET, EVENT_CASINO, EVENT_DEPOSIT  # noqa: E402
from rfm_pipeline import build_rows  # noqa: E402

REF = date(2026, 7, 28)


def epoch_em(dia: date) -> str:
    dt = datetime(dia.year, dia.month, dia.day, 12, tzinfo=timezone(timedelta(hours=-3)))
    return str(int(dt.timestamp()))


class FakeClient:
    """Devolve eventos fixos por nome, no formato que a Logs API devolve."""

    def __init__(self, por_evento: dict[str, list[dict]]):
        self.por_evento = por_evento
        self.chamadas: list[str] = []

    def iter_events(self, event_name, since, until, page_size=50):
        self.chamadas.append(event_name)
        return iter(self.por_evento.get(event_name, []))


def ev(pid: str, dia: date, **attrs) -> dict:
    return {"customer_id": pid, "internal_id": f"cio_{pid}",
            "timestamp": epoch_em(dia), "attrs": attrs}


def test_gera_linha_por_jogador_classificado():
    client = FakeClient({
        EVENT_DEPOSIT: [
            # champion: 5 depósitos na última semana
            *[ev("champ", REF - timedelta(days=i), Amount="500") for i in range(5)],
            # promising: um depósito recente
            ev("prom", REF - timedelta(days=2), Amount="80"),
            # at risk: último depósito há 45 dias
            ev("risco", REF - timedelta(days=45), Amount="3000"),
            # lost: último depósito há 300 dias
            ev("perdido", REF - timedelta(days=300), Amount="100"),
        ],
        EVENT_BET: [ev("champ", REF, TotalStake="200", TotalWinnings="120")],
        EVENT_CASINO: [ev("prom", REF - timedelta(days=1), Slug="aviator")],
    })

    rows = build_rows(client, REF)
    por_id = {r["player_id"]: r for r in rows}

    assert client.chamadas == [EVENT_DEPOSIT, EVENT_BET, EVENT_CASINO]

    assert por_id["champ"]["archetype"] == "Champions"
    assert por_id["champ"]["deposits_7d"] == 5
    assert por_id["champ"]["sports_ggr_90d"] == 80.0
    assert por_id["champ"]["product_pref"] == "esportes"
    assert por_id["champ"]["value_tier"] == "Alto"

    assert por_id["prom"]["archetype"] == "Promising"
    assert por_id["prom"]["product_pref"] == "cassino"
    assert por_id["prom"]["value_tier"] == "Baixo"

    assert por_id["risco"]["archetype"] == "At Risk"
    assert por_id["risco"]["days_since_last_deposit"] == 45

    assert por_id["perdido"]["archetype"] == "Lost"


def test_quem_so_joga_e_nunca_depositou_fica_fora():
    # É o ponto do segmento 1941: a base classificada é de depositantes.
    client = FakeClient({EVENT_CASINO: [ev("visitante", REF, Slug="aviator")]})
    assert build_rows(client, REF) == []


def test_toda_linha_tem_as_colunas_da_tabela():
    from_schema = {
        "snapshot_date", "player_id", "internal_id", "days_since_last_deposit",
        "last_deposit_at", "deposits_7d", "deposits_30d", "deposits_90d",
        "deposits_total", "deposit_value_30d", "deposit_value_90d",
        "deposit_value_total", "days_since_last_activity", "last_activity_at",
        "active_days_30d", "sports_bets_90d", "sports_stake_90d",
        "sports_winnings_90d", "sports_ggr_90d", "casino_sessions_90d",
        "archetype", "value_tier", "signup_date", "first_deposit_date",
        "product_pref", "platform", "device_os", "utm_source", "utm_medium",
        "utm_campaign", "player_status", "ingested_at",
    }
    client = FakeClient({EVENT_DEPOSIT: [ev("p", REF, Amount="100")]})
    row = build_rows(client, REF)[0]
    faltando = from_schema - set(row)
    sobrando = set(row) - from_schema
    assert not faltando, f"faltam colunas: {sorted(faltando)}"
    assert not sobrando, f"colunas que a tabela não tem: {sorted(sobrando)}"


def test_colunas_batem_com_o_ddl():
    """Compara as chaves da linha com o CREATE TABLE de verdade.

    É esta checagem que pega o caso de alguém adicionar uma coluna no SQL e
    esquecer do Python (ou o contrário) — que só apareceria como erro do
    BigQuery em produção, no meio da noite.
    """
    import re

    ddl_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "sql", "00_schema.sql",
    )
    ddl = open(ddl_path).read()
    bloco = ddl.split("rfm_snapshots`", 1)[1].split(")\nPARTITION BY", 1)[0]
    colunas_ddl = set(
        re.findall(r"^\s{2}(\w+)\s+(?:DATE|STRING|INT64|NUMERIC|TIMESTAMP|BOOL)", bloco, re.M)
    )

    client = FakeClient({EVENT_DEPOSIT: [ev("p", REF, Amount="100")]})
    colunas_py = set(build_rows(client, REF)[0])

    assert colunas_ddl == colunas_py, (
        f"só no DDL: {sorted(colunas_ddl - colunas_py)} · "
        f"só no Python: {sorted(colunas_py - colunas_ddl)}"
    )


def test_reprocessar_o_mesmo_dia_da_o_mesmo_resultado():
    client = FakeClient({
        EVENT_DEPOSIT: [ev("p", REF - timedelta(days=3), Amount="100")]
    })
    a = build_rows(client, REF)
    client.por_evento[EVENT_DEPOSIT] = [ev("p", REF - timedelta(days=3), Amount="100")]
    b = build_rows(client, REF)
    # ingested_at muda a cada execução; o resto tem que ser idêntico.
    for linha in (a[0], b[0]):
        linha.pop("ingested_at")
    assert a[0] == b[0]


# -----------------------------------------------------------------------------
# Carry-forward: o histórico que a janela de eventos não alcança
# -----------------------------------------------------------------------------

def test_lost_antigo_sobrevive_via_carry_forward():
    """O bug que o carry-forward conserta.

    Um jogador cujo último depósito foi há 300 dias não gera NENHUM evento na
    janela lida. Sem o snapshot anterior ele desaparece do dashboard — e ele é
    'Lost', que é ~60% da base. O dashboard perderia a maioria dos jogadores e
    ainda pareceria correto, porque as porcentagens continuariam somando 100%.
    """
    client = FakeClient({EVENT_DEPOSIT: [ev("ativo", REF, Amount="100")]})

    sem_historico = build_rows(client, REF)
    assert {r["player_id"] for r in sem_historico} == {"ativo"}

    anterior = [{
        "player_id": "sumido",
        "internal_id": "cio_sumido",
        "snapshot_date": REF - timedelta(days=1),
        "last_deposit_date": REF - timedelta(days=300),
        "deposits_total": 12,
        "deposit_value_total": 4500.0,
        "platform": "web",
    }]
    com_historico = build_rows(client, REF, previous_rows=anterior)
    por_id = {r["player_id"]: r for r in com_historico}

    assert set(por_id) == {"ativo", "sumido"}
    assert por_id["sumido"]["archetype"] == "Lost"
    assert por_id["sumido"]["days_since_last_deposit"] == 300
    # O histórico de valor sobrevive, senão o LTV do arquétipo Lost seria zero.
    assert por_id["sumido"]["deposit_value_total"] == 4500.0
    assert por_id["sumido"]["deposits_total"] == 12


def test_carry_forward_nao_conta_deposito_duas_vezes():
    """O erro oposto: somar de novo o que a janela já contou.

    O jogador tem 10 depósitos históricos e fez 1 novo depois do snapshot
    anterior. O total tem que ser 11 — não 10 + (todos os da janela).
    """
    client = FakeClient({EVENT_DEPOSIT: [
        ev("p", REF - timedelta(days=30), Amount="100"),   # já estava no total
        ev("p", REF - timedelta(days=10), Amount="100"),   # já estava no total
        ev("p", REF, Amount="50"),                          # novo
    ]})
    anterior = [{
        "player_id": "p",
        "snapshot_date": REF - timedelta(days=1),
        "last_deposit_date": REF - timedelta(days=10),
        "deposits_total": 10,
        "deposit_value_total": 1000.0,
    }]
    row = build_rows(client, REF, previous_rows=anterior)[0]

    assert row["deposits_total"] == 11
    assert row["deposit_value_total"] == 1050.0
    # As janelas móveis continuam vindo dos eventos, completas.
    assert row["deposits_90d"] == 3
    assert row["deposit_value_90d"] == 250.0


def test_carry_forward_respeita_deposito_mais_recente():
    # O evento novo é mais recente que o histórico: a recência vem do evento.
    client = FakeClient({EVENT_DEPOSIT: [ev("p", REF - timedelta(days=2), Amount="100")]})
    anterior = [{
        "player_id": "p",
        "snapshot_date": REF - timedelta(days=1),
        "last_deposit_date": REF - timedelta(days=300),
        "deposits_total": 5,
        "deposit_value_total": 500.0,
    }]
    row = build_rows(client, REF, previous_rows=anterior)[0]
    assert row["days_since_last_deposit"] == 2
    assert row["archetype"] == "Promising"


def test_carry_forward_aceita_data_como_string():
    # O BigQuery pode devolver DATE como str dependendo do driver.
    client = FakeClient({})
    anterior = [{
        "player_id": "p",
        "snapshot_date": "2026-07-27",
        "last_deposit_date": "2026-01-01T00:00:00Z",
        "deposits_total": 3,
        "deposit_value_total": 300.0,
    }]
    row = build_rows(client, REF, previous_rows=anterior)[0]
    assert row["archetype"] == "Lost"
    assert row["days_since_last_deposit"] == (REF - date(2026, 1, 1)).days


if __name__ == "__main__":
    falhas = []
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas.append((t.__name__, e or "assert falhou"))
        except Exception as e:  # noqa: BLE001
            falhas.append((t.__name__, f"{type(e).__name__}: {e}"))
    for nome, e in falhas:
        print(f"FALHOU {nome}: {e}")
    print(f"{len(testes) - len(falhas)}/{len(testes)} testes passaram")
    sys.exit(1 if falhas else 0)
