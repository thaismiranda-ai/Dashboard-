#!/usr/bin/env bash
# Roda tudo que dá para verificar sem credencial do BigQuery nem do Customer.io.
#
#   ./run_tests.sh
#
# Dependências opcionais: sqlglot e duckdb. Os testes que precisam delas
# imprimem SKIP em vez de falhar quando não estão instaladas.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
falhas=0

for t in test_scoring test_sql_parse test_view_columns test_sql_parity; do
  echo "=== ${t} ==="
  python3 "${HERE}/pipeline/${t}.py" || falhas=$((falhas + 1))
  echo
done

if [[ ${falhas} -gt 0 ]]; then
  echo "${falhas} suíte(s) falharam"
  exit 1
fi
echo "tudo passou"
