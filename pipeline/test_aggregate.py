"""Testes da agregação de eventos.

O foco é onde este tipo de código erra de verdade: conversão de tipo (a API
devolve tudo como string), fronteiras de janela (7/30/90 dias) e fuso — não a
aritmética óbvia.

Rodar: python3 pipeline/test_aggregate.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aggregate import (  # noqa: E402
    aggregate_events,
    epoch_to_local_date,
    merge_profile,
    to_float,
    to_int,
)

REF = date(2026, 7, 28)


def epoch_em(dia: date, hora: int = 12) -> str:
    """Epoch (string, como a API devolve) para uma hora local daquele dia."""
    dt = datetime(dia.year, dia.month, dia.day, hora, tzinfo=timezone(timedelta(hours=-3)))
    return str(int(dt.timestamp()))


def deposito(dia: date, valor: str, pid: str = "p1", hora: int = 12, **attrs) -> dict:
    return {
        "customer_id": pid,
        "timestamp": epoch_em(dia, hora),
        "attrs": {"Amount": valor, **attrs},
    }


def aposta(dia: date, stake: str, winnings: str, pid: str = "p1") -> dict:
    return {
        "customer_id": pid,
        "timestamp": epoch_em(dia),
        "attrs": {"TotalStake": stake, "TotalWinnings": winnings},
    }


def cassino(dia: date, pid: str = "p1") -> dict:
    return {"customer_id": pid, "timestamp": epoch_em(dia), "attrs": {"Slug": "aviator"}}


# -----------------------------------------------------------------------------
# Conversão de tipo — a API manda tudo como string
# -----------------------------------------------------------------------------

def test_conversao_aguenta_o_que_a_api_manda():
    assert to_float("100") == 100.0
    assert to_float("12215.96") == 12215.96
    assert to_float("1.234,50".replace(".", "")) == 1234.50   # vírgula decimal
    assert to_float("") == 0.0
    assert to_float(None) == 0.0
    assert to_float("abc") == 0.0        # lixo não pode derrubar o pipeline
    assert to_float(7) == 7.0
    assert to_int("102") == 102


def test_somar_strings_nao_concatena():
    # O bug clássico: "100" + "300" = "100300". Se a conversão sumir, este
    # teste é o que grita.
    m = aggregate_events(
        [deposito(REF, "100"), deposito(REF, "300")], [], [], REF
    )["p1"]
    assert m.deposit_value_total == 400.0


# -----------------------------------------------------------------------------
# Fuso — um depósito às 22h de Brasília é 01h UTC do dia seguinte
# -----------------------------------------------------------------------------

def test_deposito_da_noite_conta_no_dia_certo():
    # 22h local de 27/07 = 01h UTC de 28/07. Em UTC cru viraria dia 28.
    tarde_da_noite = epoch_em(date(2026, 7, 27), hora=22)
    assert epoch_to_local_date(tarde_da_noite) == date(2026, 7, 27)


def test_epoch_invalido_vira_none():
    assert epoch_to_local_date(None) is None
    assert epoch_to_local_date("0") is None
    assert epoch_to_local_date("") is None


# -----------------------------------------------------------------------------
# Fronteiras de janela
# -----------------------------------------------------------------------------

def test_fronteiras_das_janelas_de_deposito():
    eventos = [
        deposito(REF - timedelta(days=0), "10"),
        deposito(REF - timedelta(days=7), "10"),    # último dia dentro de 7d
        deposito(REF - timedelta(days=8), "10"),    # primeiro fora de 7d
        deposito(REF - timedelta(days=30), "10"),   # último dentro de 30d
        deposito(REF - timedelta(days=31), "10"),   # fora de 30d
        deposito(REF - timedelta(days=90), "10"),   # último dentro de 90d
        deposito(REF - timedelta(days=91), "10"),   # fora de 90d
    ]
    m = aggregate_events(eventos, [], [], REF)["p1"]
    assert m.deposits_7d == 2
    assert m.deposits_30d == 4
    assert m.deposits_90d == 6
    assert m.deposits_total == 7
    assert m.deposit_value_30d == 40.0
    assert m.deposit_value_90d == 60.0
    assert m.deposit_value_total == 70.0


def test_evento_no_futuro_e_ignorado():
    # Reprocessar um dia antigo não pode enxergar o que veio depois dele,
    # senão o snapshot de ontem muda toda vez que rodar de novo.
    m = aggregate_events(
        [deposito(REF, "10"), deposito(REF + timedelta(days=1), "999")], [], [], REF
    )["p1"]
    assert m.deposits_total == 1
    assert m.deposit_value_total == 10.0


def test_recencia_usa_o_deposito_mais_recente():
    eventos = [
        deposito(REF - timedelta(days=40), "10"),
        deposito(REF - timedelta(days=3), "10"),
        deposito(REF - timedelta(days=90), "10"),
    ]
    m = aggregate_events(eventos, [], [], REF)["p1"]
    assert m.days_since_last_deposit(REF) == 3


def test_quem_nunca_depositou_tem_recencia_none():
    m = aggregate_events([], [cassino(REF)], [], REF)
    # cassino entra como `bets` aqui só para criar o jogador sem depósito
    assert m["p1"].days_since_last_deposit(REF) is None


# -----------------------------------------------------------------------------
# Esportes, cassino e produto
# -----------------------------------------------------------------------------

def test_ggr_de_esportes():
    m = aggregate_events([], [aposta(REF, "100", "60"), aposta(REF, "50", "10")], [], REF)["p1"]
    assert m.sports_stake_90d == 150.0
    assert m.sports_winnings_90d == 70.0
    assert m.sports_ggr_90d == 80.0


def test_ggr_negativo_e_preservado():
    # Semana em que os jogadores ganharam mais do que apostaram. É real —
    # zerar aqui inflaria a receita do arquétipo.
    m = aggregate_events([], [aposta(REF, "100", "500")], [], REF)["p1"]
    assert m.sports_ggr_90d == -400.0


def test_cassino_nao_gera_receita():
    m = aggregate_events([], [], [cassino(REF), cassino(REF)], REF)["p1"]
    assert m.casino_sessions_90d == 2
    assert m.sports_ggr_90d == 0.0
    assert m.sports_stake_90d == 0.0


def test_produto_preferido():
    so_cassino = aggregate_events([], [], [cassino(REF)], REF)["p1"]
    assert so_cassino.product_pref == "cassino"

    so_esporte = aggregate_events([], [aposta(REF, "10", "0")], [], REF)["p1"]
    assert so_esporte.product_pref == "esportes"

    os_dois = aggregate_events([], [aposta(REF, "10", "0")], [cassino(REF)], REF)["p1"]
    assert os_dois.product_pref == "ambos"

    so_deposito = aggregate_events([deposito(REF, "10")], [], [], REF)["p1"]
    assert so_deposito.product_pref == "nenhum"


def test_dias_ativos_contam_dias_distintos_nao_eventos():
    dia = REF - timedelta(days=2)
    eventos = [cassino(dia), cassino(dia), cassino(dia), cassino(REF)]
    m = aggregate_events([], [], eventos, REF)["p1"]
    assert m.casino_sessions_90d == 4
    assert len(m.active_dates_30d) == 2


def test_atividade_e_deposito_sao_independentes():
    # Jogou ontem, depositou há 40 dias: a classificação (só depósito) o
    # coloca em At Risk, mas ele está ativo. É o sinal que o drill-down usa.
    m = aggregate_events(
        [deposito(REF - timedelta(days=40), "100")],
        [],
        [cassino(REF - timedelta(days=1))],
        REF,
    )["p1"]
    assert m.days_since_last_deposit(REF) == 40
    assert m.days_since_last_activity(REF) == 1


# -----------------------------------------------------------------------------
# Múltiplos jogadores e atributos de perfil
# -----------------------------------------------------------------------------

def test_separa_jogadores():
    eventos = [deposito(REF, "100", pid="a"), deposito(REF, "250", pid="b")]
    m = aggregate_events(eventos, [], [], REF)
    assert m["a"].deposit_value_total == 100.0
    assert m["b"].deposit_value_total == 250.0


def test_plataforma_vem_do_deposito_mais_recente():
    eventos = [
        deposito(REF - timedelta(days=10), "10", Platform="web", DeviceOS="unknown"),
        deposito(REF - timedelta(days=1), "10", Platform="mobile_app", DeviceOS="android"),
    ]
    m = aggregate_events(eventos, [], [], REF)["p1"]
    assert m.platform == "mobile_app"
    assert m.device_os == "android"


def test_merge_de_perfil_com_fallback_de_caixa():
    m = aggregate_events([deposito(REF, "10")], [], [], REF)["p1"]
    perfil = {
        "CreatedOn": epoch_em(date(2025, 3, 10)),
        "FirstDepositTimestamp": epoch_em(date(2025, 3, 12)),
        "PlayerStatusString": "Active",
        "UtmSource": "google",
    }
    out = merge_profile(m, perfil)
    assert out["signup_date"] == date(2025, 3, 10)
    assert out["first_deposit_date"] == date(2025, 3, 12)
    assert out["player_status"] == "Active"
    assert out["utm_source"] == "google"


def test_merge_prefere_utm_do_deposito():
    eventos = [deposito(REF, "10", UtmSource="meta")]
    m = aggregate_events(eventos, [], [], REF)["p1"]
    out = merge_profile(m, {"UtmSource": "google"})
    assert out["utm_source"] == "meta"


def test_merge_aguenta_perfil_vazio():
    m = aggregate_events([deposito(REF, "10")], [], [], REF)["p1"]
    out = merge_profile(m, {})
    assert out["signup_date"] is None
    assert out["player_status"] is None


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
