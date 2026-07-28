# Imagem do job diário do RFM.
#
# Roda como Cloud Run Job. A credencial do BigQuery é a service account
# anexada ao job — nenhuma chave é gerada nem exportada. O token do
# Customer.io vem do Secret Manager, injetado como variável de ambiente na
# hora da execução.

FROM python:3.12-slim

# Roda sem privilégio. O job não escreve em disco, só lê API e grava no BQ.
RUN useradd --create-home --uid 1001 rfm
WORKDIR /app

COPY pipeline/requirements.txt .
# Só o cliente do BigQuery é necessário em produção; sqlglot e duckdb são
# dependências de teste e ficam de fora da imagem.
RUN pip install --no-cache-dir "google-cloud-bigquery>=3.20"

COPY pipeline/ ./pipeline/

USER rfm
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python3", "pipeline/rfm_pipeline.py"]
