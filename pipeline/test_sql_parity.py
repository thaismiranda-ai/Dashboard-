"""Paridade entre a classificação em Python e a em SQL.

Existem duas implementações da mesma regra — pipeline/scoring.py e
sql/07_udf_classify.sql — porque cada uma resolve um problema que a outra não
resolve (o Python classifica no pipeline, o SQL reclassifica em backfill e
audita a tabela). Duas implementações da mesma regra divergem silenciosamente:
alguém move o corte de 90 para 120 dias num arquivo, o outro fica para trás, e
o gráfico de evolução ganha um degrau que ninguém consegue explicar.

Este teste extrai o corpo das UDFs direto do .sql, roda no DuckDB (cuja sintaxe
de CASE é a mesma do BigQuery) e compara com o Python ponto a ponto. Não
substitui rodar no BigQuery, mas pega divergência de lógica, que é o erro
provável.

Rodar: pip install duckdb && python3 pipeline/test_sql_parity.py
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scoring import ARCHETYPE_RANK, classify, value_tier  # noqa: E402

SQL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sql",
    "07_udf_classify.sql",
)


def extract_body(sql: str, fn_name: str) -> str:
    """Pega o corpo entre `AS (` e `);` da UDF pedida."""
    pattern = (
        r"FUNCTION `\$\{PROJECT_ID\}\.\$\{DATASET\}\." + fn_name + r"`\((.*?)\)"
        r"\s*RETURNS\s+\w+\s*AS \((.*?)\n\);"
    )
    match = re.search(pattern, sql, re.S)
    if not match:
        raise AssertionError(f"não encontrei a UDF {fn_name} em {SQL_PATH}")
    return match.group(2).strip()


def main() -> int:
    try:
        import duckdb
    except ImportError:
        print("SKIP: duckdb não instalado (pip install duckdb)")
        return 0

    sql = open(SQL_PATH).read()
    con = duckdb.connect()
    falhas: list[str] = []

    # --- classificação: varre a grade recência x frequência, incluindo NULL ---
    body = (
        extract_body(sql, "rfm_classify")
        .replace("days_since_last_deposit", "d")
        .replace("deposits_30d", "f")
    )
    dias = [None] + list(range(0, 200)) + [365, 3650]
    freqs = [0, 1, 2, 3, 4, 5, 10, 99]
    valores = ", ".join(
        f"({'NULL' if d is None else d}, {f})" for d in dias for f in freqs
    )
    rows = con.execute(
        f"SELECT d, f, ({body}) FROM (VALUES {valores}) AS t(d, f)"
    ).fetchall()
    for d, f, got in rows:
        esperado = classify(d, f)
        if got != esperado:
            falhas.append(f"classify(dias={d}, freq={f}): SQL={got!r} Python={esperado!r}")
    print(f"rfm_classify           {len(rows)} combinações verificadas")

    # --- rank ---
    body = extract_body(sql, "rfm_archetype_rank").replace("archetype", "a")
    nomes = ", ".join(f"('{n}')" for n in ARCHETYPE_RANK)
    rows = con.execute(f"SELECT a, ({body}) FROM (VALUES {nomes}) AS t(a)").fetchall()
    for nome, got in rows:
        if got != ARCHETYPE_RANK[nome]:
            falhas.append(f"rank({nome}): SQL={got} Python={ARCHETYPE_RANK[nome]}")
    print(f"rfm_archetype_rank     {len(rows)} arquétipos verificados")

    # --- faixa de valor ---
    body = extract_body(sql, "rfm_value_tier").replace("deposit_value_90d", "v")
    vals = [None, 0, 49.99, 50, 499.99, 500, 1999.99, 2000, 99999]
    for v in vals:
        literal = "NULL" if v is None else repr(v)
        got = con.execute(f"SELECT ({body.replace('v', literal)})").fetchone()[0]
        if got != value_tier(v):
            falhas.append(f"value_tier({v}): SQL={got!r} Python={value_tier(v)!r}")
    print(f"rfm_value_tier         {len(vals)} valores verificados")

    if falhas:
        print(f"\n{len(falhas)} DIVERGÊNCIA(S):")
        for f in falhas[:20]:
            print(f"  - {f}")
        if len(falhas) > 20:
            print(f"  ... e mais {len(falhas) - 20}")
        return 1

    print("\nSQL e Python concordam em todos os pontos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
