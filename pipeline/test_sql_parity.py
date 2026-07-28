"""Paridade entre a classificação em Python e a em SQL.

Existem duas implementações da mesma regra — pipeline/scoring.py e
sql/07_udf_classify.sql — porque cada uma resolve um problema que a outra não
resolve (o Python classifica no pipeline, o SQL reclassifica em backfill). Duas
implementações da mesma regra divergem silenciosamente: alguém ajusta um corte
de recência no Python, o backfill continua com o corte velho, e o gráfico de
evolução ganha um degrau que ninguém consegue explicar.

Este teste extrai o corpo das UDFs direto do arquivo .sql, roda no DuckDB
(cuja sintaxe de CASE é a mesma do BigQuery) e compara com o Python célula a
célula. Não substitui rodar no BigQuery de verdade, mas pega divergência de
lógica, que é o erro provável.

Rodar: pip install duckdb && python3 pipeline/test_sql_parity.py
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scoring import (  # noqa: E402
    classify,
    combine_fm,
    score_frequency,
    score_monetary,
    score_recency,
)

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

    # --- grade 5x5 de classificação ---
    body = extract_body(sql, "rfm_classify").replace("r_score", "r").replace("fm_score", "fm")
    rows = con.execute(
        f"SELECT r, fm, ({body}) FROM (SELECT UNNEST(range(1,6)) AS r) "
        f"CROSS JOIN (SELECT UNNEST(range(1,6)) AS fm)"
    ).fetchall()
    for r, fm, got in rows:
        if got != classify(r, fm):
            falhas.append(f"classify(R={r}, FM={fm}): SQL={got!r} Python={classify(r, fm)!r}")
    print(f"classify        {len(rows)} células verificadas")

    # --- fusão F+M ---
    body = extract_body(sql, "rfm_combine_fm").replace("f_score", "f").replace("m_score", "m")
    rows = con.execute(
        f"SELECT f, m, ({body}) FROM (SELECT UNNEST(range(1,6)) AS f) "
        f"CROSS JOIN (SELECT UNNEST(range(1,6)) AS m)"
    ).fetchall()
    for f, m, got in rows:
        if got != combine_fm(f, m):
            falhas.append(f"combine_fm({f}, {m}): SQL={got} Python={combine_fm(f, m)}")
    print(f"combine_fm      {len(rows)} células verificadas")

    # --- cortes de R, F e M, com foco nas bordas e no NULL ---
    casos = [
        ("rfm_score_recency", score_recency, "recency_days",
         [None, 0, 7, 8, 14, 15, 30, 31, 60, 61, 9999]),
        ("rfm_score_frequency", score_frequency, "frequency_90d",
         [None, 0, 2, 3, 7, 8, 19, 20, 59, 60, 500]),
        ("rfm_score_monetary", score_monetary, "monetary_90d",
         [None, 0, 49.99, 50, 249, 250, 749, 750, 1999, 2000, 99999]),
    ]
    for fn_name, py_fn, col, valores in casos:
        body = extract_body(sql, fn_name)
        for v in valores:
            literal = "NULL" if v is None else repr(v)
            got = con.execute(f"SELECT ({body.replace(col, literal)})").fetchone()[0]
            if got != py_fn(v):
                falhas.append(f"{fn_name}({v}): SQL={got} Python={py_fn(v)}")
        print(f"{fn_name:22} {len(valores)} valores verificados")

    if falhas:
        print(f"\n{len(falhas)} DIVERGÊNCIA(S):")
        for f in falhas:
            print(f"  - {f}")
        return 1

    print("\nSQL e Python concordam em todos os pontos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
