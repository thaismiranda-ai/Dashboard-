"""Confere que as views só referenciam colunas que existem.

Por que isso é um teste e não "cuidado ao editar": as views 02–06 leem de
`vw_rfm_daily`, e o BigQuery só reclama de uma coluna inexistente na hora do
deploy — depois de você já ter esperado o `bq query` de sete arquivos. Pior:
renomear uma coluna na 01 quebra as cinco views de baixo em silêncio até
alguém rodar o deploy.

O teste monta o conjunto de colunas que a 01 expõe, depois varre as demais
views procurando referência a coluna que a 01 não tem. Não é um type-checker
de SQL; é a rede que pega renomeação e erro de digitação, que é o que de fato
acontece.

Rodar: pip install sqlglot && python3 pipeline/test_view_columns.py
"""

from __future__ import annotations

import glob
import os
import re
import sys

SQL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql"
)

# Colunas que vêm de outras tabelas, não de vw_rfm_daily. Referenciá-las é
# legítimo, então elas não contam como erro.
FROM_OTHER_SOURCES = {
    # campaign_touches
    "touch_date", "campaign_id", "campaign_name", "channel", "delivered",
    "opened", "clicked", "converted", "ingested_at",
    # colunas criadas dentro das próprias CTEs das views 02-06
    "players", "base_players", "share", "lag_days", "counterpart", "ltv",
    "archetype_from", "archetype_to", "rank_from", "rank_to", "movement",
    "steps_gained", "value_moved", "deposits_90d_moved", "players_in",
    "players_out", "net_players", "ltv_in", "ltv_out", "net_ltv",
    "players_entered", "players_left", "max_date", "d", "w", "window_days",
    "archetype_before", "archetype_after", "rank_before", "rank_after",
    "health_before", "health_after", "recovered", "degraded", "ref_date",
    "players_touched", "recovery_rate", "avg_delta_deposits", "players_control",
    "recovery_rate_control", "avg_delta_deposits_control", "delta_deposits_90d",
    "ltv_before", "open_rate", "click_to_open_rate", "has_min_sample",
    "recovered_control", "total_players", "total_ggr_90d", "total_deposits_90d",
    "total_ltv", "value_median", "value_p90", "ggr_90d_median", "cohort_month",
    "players_with_ftd", "ftd_rate", "avg_account_age_days", "healthy_players",
    "at_risk_players", "cold_players", "healthy_share", "healthy_target",
    "gap_to_target", "ltv_healthy", "ltv_share_healthy", "arpu_90d",
    "deposit_per_player_90d", "ltv_per_player", "ggr_per_bet",
    "ltv_mean_to_median", "share_of_players", "share_of_ggr", "share_of_ltv",
    "value_index", "delta_abs_1d", "delta_abs_7d", "delta_abs_28d",
    "delta_pct_1d", "delta_pct_7d", "delta_pct_28d", "signed_move_7d",
    "players_d1", "players_d7", "players_d28", "avg_days_since_deposit",
    "avg_deposits_30d", "archetype_7d_ago", "rank_7d_ago", "movement_7d",
    "last_touch_date", "last_campaign_name", "touches_30d", "clicks_30d",
    "is_fatigued", "action_priority", "audience", "snapshot_date", "player_id",
}


def columns_of_base_view() -> set[str]:
    """Aliases de saída da vw_rfm_daily, lidos do texto da 01."""
    sql = open(os.path.join(SQL_DIR, "01_vw_rfm_daily.sql")).read()
    cols: set[str] = set()
    # `s.coluna,` (repasse direto) e `... AS alias` (derivadas)
    cols.update(re.findall(r"^\s+s\.(\w+),?\s*$", sql, re.M))
    cols.update(re.findall(r"\bAS (\w+)\s*,?\s*$", sql, re.M))
    cols.update(re.findall(r"COALESCE\(s\.\w+,[^)]*\)\s+AS (\w+)", sql))
    return {c for c in cols if c not in {"max_date", "latest"}}


def main() -> int:
    base_cols = columns_of_base_view()
    print(f"vw_rfm_daily expõe {len(base_cols)} colunas")

    known = base_cols | FROM_OTHER_SOURCES
    problemas: list[str] = []

    for path in sorted(glob.glob(os.path.join(SQL_DIR, "0[2-6]_*.sql"))):
        nome = os.path.basename(path)
        sql = open(path).read()
        # Referências qualificadas por alias de tabela: cur.x, pre.x, b.x, c.x…
        refs = set(re.findall(r"\b(?:cur|prv|pre|post|b|c|p|s|d|t|i|o|u|m)\.(\w+)\b", sql))
        desconhecidas = sorted(r for r in refs if r not in known)
        if desconhecidas:
            problemas.append(f"{nome}: {', '.join(desconhecidas)}")
        print(f"  {nome:34} {len(refs)} referências, {len(desconhecidas)} desconhecidas")

    if problemas:
        print("\nCOLUNAS QUE NÃO EXISTEM NA VIEW BASE:")
        for p in problemas:
            print(f"  - {p}")
        return 1

    print("\nToda coluna referenciada existe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
