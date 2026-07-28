#!/usr/bin/env bash
# =============================================================================
# Coloca o pipeline RFM para rodar sozinho, todo dia, no GCP.
#
#   PROJECT_ID=meu-projeto DATASET=crm_rfm ALERT_EMAIL=voce@aposta1.bet.br \
#     ./deploy/setup_scheduler.sh
#
# É idempotente: rodar de novo atualiza o que existe em vez de duplicar.
#
# O que ele cria:
#   · service account própria, com o mínimo de permissão
#   · segredo com o token do Customer.io (pedido interativamente, nunca em arquivo)
#   · imagem no Artifact Registry
#   · Cloud Run Job com timeout de 6h
#   · Cloud Scheduler disparando às 05:10 (America/Sao_Paulo)
#   · alerta por e-mail quando o job falha
#
# POR QUE CLOUD RUN E NÃO GITHUB ACTIONS
# A credencial do BigQuery fica sendo a service account anexada ao job — não
# existe chave JSON para exportar, guardar em secret e vazar. E o job lê 95
# dias de eventos a 50 por página, o que pode passar do teto de 6h do Actions.
# =============================================================================
set -euo pipefail

: "${PROJECT_ID:?defina PROJECT_ID}"
: "${DATASET:?defina DATASET}"
: "${ALERT_EMAIL:?defina ALERT_EMAIL — sem alerta, 'rodar sozinho' vira 'quebrar sozinho'}"

REGION="${REGION:-southamerica-east1}"      # São Paulo, perto do BigQuery
JOB_NAME="${JOB_NAME:-rfm-pipeline}"
REPO="${REPO:-crm}"
SA_NAME="${SA_NAME:-rfm-pipeline}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SECRET_NAME="${SECRET_NAME:-cio-api-token}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${JOB_NAME}:latest"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> projeto ${PROJECT_ID} · região ${REGION}"
gcloud config set project "${PROJECT_ID}" --quiet

# ---------------------------------------------------------------------------
echo "==> 1/7 APIs"
gcloud services enable \
  run.googleapis.com cloudscheduler.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com monitoring.googleapis.com \
  bigquery.googleapis.com --quiet

# ---------------------------------------------------------------------------
echo "==> 2/7 service account"
if ! gcloud iam service-accounts describe "${SA_EMAIL}" &>/dev/null; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Pipeline RFM" --quiet
fi

# Escopo mínimo: escrever no dataset e rodar query. Nada de admin de projeto.
for role in roles/bigquery.dataEditor roles/bigquery.jobUser; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" --role="${role}" \
    --condition=None --quiet >/dev/null
done

# ---------------------------------------------------------------------------
echo "==> 3/7 token do Customer.io"
if gcloud secrets describe "${SECRET_NAME}" &>/dev/null; then
  echo "    segredo ${SECRET_NAME} já existe (para trocar: gcloud secrets versions add)"
else
  echo "    cole o token do Customer.io e tecle Enter (não fica no histórico do shell):"
  read -rs CIO_TOKEN
  printf '%s' "${CIO_TOKEN}" | gcloud secrets create "${SECRET_NAME}" --data-file=- --quiet
  unset CIO_TOKEN
fi
gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" --quiet >/dev/null

# ---------------------------------------------------------------------------
echo "==> 4/7 imagem"
gcloud artifacts repositories describe "${REPO}" --location="${REGION}" &>/dev/null || \
  gcloud artifacts repositories create "${REPO}" \
    --repository-format=docker --location="${REGION}" \
    --description="Imagens do CRM" --quiet

gcloud builds submit "${HERE}" \
  --config=- --quiet <<EOF
steps:
  - name: gcr.io/cloud-builders/docker
    args: ['build', '-f', 'deploy/Dockerfile', '-t', '${IMAGE}', '.']
images: ['${IMAGE}']
EOF

# ---------------------------------------------------------------------------
echo "==> 5/7 Cloud Run Job"
JOB_ARGS=(
  --image="${IMAGE}"
  --region="${REGION}"
  --service-account="${SA_EMAIL}"
  --set-env-vars="BQ_PROJECT=${PROJECT_ID},BQ_DATASET=${DATASET}"
  --set-secrets="CIO_API_TOKEN=${SECRET_NAME}:latest"
  --task-timeout=6h
  --max-retries=1          # o pipeline substitui a partição, então repetir é seguro
  --memory=2Gi
  --cpu=1
  --args="--dataset,${DATASET},--project,${PROJECT_ID},-v"
)
if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" &>/dev/null; then
  gcloud run jobs update "${JOB_NAME}" "${JOB_ARGS[@]}" --quiet
else
  gcloud run jobs create "${JOB_NAME}" "${JOB_ARGS[@]}" --quiet
fi

# ---------------------------------------------------------------------------
echo "==> 6/7 agendamento"
# 05:10 e não 05:00: horário redondo é quando todo mundo agenda, e a Logs API
# do Customer.io não precisa de mais uma carga no mesmo minuto.
SCHEDULER_SA="${SA_EMAIL}"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SCHEDULER_SA}" --role="roles/run.invoker" \
  --condition=None --quiet >/dev/null

SCHED_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run"
SCHED_ARGS=(
  --location="${REGION}"
  --schedule="10 5 * * *"
  --time-zone="America/Sao_Paulo"
  --uri="${SCHED_URI}"
  --http-method=POST
  --oauth-service-account-email="${SCHEDULER_SA}"
  --attempt-deadline=1800s
)
if gcloud scheduler jobs describe "${JOB_NAME}-diario" --location="${REGION}" &>/dev/null; then
  gcloud scheduler jobs update http "${JOB_NAME}-diario" "${SCHED_ARGS[@]}" --quiet
else
  gcloud scheduler jobs create http "${JOB_NAME}-diario" "${SCHED_ARGS[@]}" --quiet
fi

# ---------------------------------------------------------------------------
echo "==> 7/7 alerta de falha"
CHANNEL=$(gcloud alpha monitoring channels list \
  --filter="labels.email_address='${ALERT_EMAIL}'" --format='value(name)' 2>/dev/null | head -1)
if [[ -z "${CHANNEL}" ]]; then
  CHANNEL=$(gcloud alpha monitoring channels create \
    --display-name="RFM — ${ALERT_EMAIL}" --type=email \
    --channel-labels="email_address=${ALERT_EMAIL}" \
    --format='value(name)' --quiet)
fi

# Dispara quando uma execução do job termina com falha. É o alerta de
# "quebrou"; o de "rodou e gravou lixo" vive na consulta agendada do deploy.md,
# porque esse o Cloud Monitoring não tem como enxergar.
POLICY=$(cat <<EOF
{
  "displayName": "RFM — job diário falhou",
  "combiner": "OR",
  "conditions": [{
    "displayName": "execução com falha",
    "conditionThreshold": {
      "filter": "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${JOB_NAME}\" AND metric.type=\"run.googleapis.com/job/completed_task_attempt_count\" AND metric.labels.result=\"failed\"",
      "comparison": "COMPARISON_GT",
      "thresholdValue": 0,
      "duration": "0s",
      "aggregations": [{"alignmentPeriod": "3600s", "perSeriesAligner": "ALIGN_SUM"}]
    }
  }],
  "notificationChannels": ["${CHANNEL}"],
  "alertStrategy": {"autoClose": "86400s"}
}
EOF
)
EXISTING=$(gcloud alpha monitoring policies list \
  --filter="displayName='RFM — job diário falhou'" --format='value(name)' 2>/dev/null | head -1)
if [[ -n "${EXISTING}" ]]; then
  printf '%s' "${POLICY}" | gcloud alpha monitoring policies update "${EXISTING}" \
    --policy-from-file=/dev/stdin --quiet
else
  printf '%s' "${POLICY}" | gcloud alpha monitoring policies create \
    --policy-from-file=/dev/stdin --quiet
fi

# ---------------------------------------------------------------------------
cat <<EOF

Pronto.

  job         ${JOB_NAME}  (${REGION})
  agenda      todo dia às 05:10, horário de São Paulo
  alerta      ${ALERT_EMAIL}, quando a execução falha

Antes de confiar nele, rode uma vez à mão e olhe o log:

  gcloud run jobs execute ${JOB_NAME} --region=${REGION} --wait
  gcloud run jobs executions list --job=${JOB_NAME} --region=${REGION} --limit=1

Falta ainda a consulta agendada que avisa quando o job "dá certo" e grava
dado ruim — ela lê a view vw_pipeline_alerts. Está no passo 6 do
docs/automacao.md, e é a que pega o caso perigoso: o silêncio de um job
verde com número errado.
EOF
