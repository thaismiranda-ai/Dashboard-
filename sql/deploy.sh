#!/usr/bin/env bash
# =============================================================================
# Aplica o schema e as views no BigQuery, na ordem certa.
#
#   PROJECT_ID=aposta1-analytics DATASET=crm_rfm ./sql/deploy.sh
#   PROJECT_ID=... DATASET=... ./sql/deploy.sh --dry-run   # só imprime o SQL
#
# Requer o `bq` CLI autenticado (gcloud auth login).
# =============================================================================
set -euo pipefail

: "${PROJECT_ID:?defina PROJECT_ID}"
: "${DATASET:?defina DATASET}"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ordem importa: as views 02–06 dependem da 01, que depende das tabelas do 00.
FILES=(
  "00_schema.sql"
  "07_udf_classify.sql"   # antes das views: backfill e auditoria dependem das UDFs
  "01_vw_rfm_daily.sql"
  "02_vw_archetype_daily.sql"
  "03_vw_migration_matrix.sql"
  "04_vw_value_by_archetype.sql"
  "05_vw_campaign_effect.sql"
  "06_vw_player_drilldown.sql"
)

for f in "${FILES[@]}"; do
  echo "==> ${f}"
  sql="$(sed -e "s/\${PROJECT_ID}/${PROJECT_ID}/g" -e "s/\${DATASET}/${DATASET}/g" "${HERE}/${f}")"

  if [[ "${DRY_RUN}" == true ]]; then
    printf '%s\n\n' "${sql}"
  else
    bq query --project_id="${PROJECT_ID}" --use_legacy_sql=false --format=none <<< "${sql}"
  fi
done

echo "==> pronto: ${PROJECT_ID}.${DATASET}"
