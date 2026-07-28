"""Confere que todo arquivo .sql parseia no dialeto BigQuery.

Pega erro de sintaxe sem precisar de credencial nem de rodar `bq`. Não valida
semântica (isso é o test_view_columns.py); valida que o SQL é SQL.

Rodar: pip install sqlglot && python3 pipeline/test_sql_parse.py
"""

from __future__ import annotations

import glob
import os
import sys

SQL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql"
)


def main() -> int:
    try:
        import sqlglot
    except ImportError:
        print("SKIP: sqlglot não instalado (pip install sqlglot)")
        return 0

    falhou = False
    for path in sorted(glob.glob(os.path.join(SQL_DIR, "*.sql"))):
        nome = os.path.basename(path)
        # Os placeholders não são SQL válido; troca por nomes reais para parsear.
        sql = open(path).read().replace("${PROJECT_ID}", "proj").replace("${DATASET}", "ds")
        try:
            stmts = [s for s in sqlglot.parse(sql, read="bigquery") if s]
            print(f"OK   {nome:34} {len(stmts)} statements")
        except Exception as e:  # noqa: BLE001 — queremos o tipo do erro no output
            falhou = True
            print(f"FAIL {nome:34} {type(e).__name__}: {str(e)[:300]}")

    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
