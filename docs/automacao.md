# Deixar o pipeline rodando sozinho

O objetivo aqui não é só "agendar". É que o dashboard só possa estar em dois
estados: **atualizado** ou **visivelmente quebrado**. O terceiro estado — dado
velho com cara de novo — é o que faz alguém decidir errado sem saber.

---

## O desenho

```
Cloud Scheduler ──05:10──▶ Cloud Run Job ──▶ Customer.io Logs API
  (America/Sao_Paulo)          │                        │
                               ▼                        ▼
                          BigQuery  ◀────────  snapshot do dia
                               │
                               ├──▶ Looker Studio (extracts, 07:00)
                               └──▶ vw_pipeline_alerts ──▶ e-mail
```

Duas escolhas que valem explicar:

**Cloud Run e não GitHub Actions.** A credencial do BigQuery passa a ser a
service account anexada ao job — não existe chave JSON para exportar, guardar
num secret e um dia vazar. E o job lê ~95 dias de eventos a 50 por página, o
que pode passar do teto de 6h do Actions.

**05:10 e não 05:00.** Horário redondo é quando todo mundo agenda. Não custa
nada evitar somar mais uma carga no mesmo minuto na API do Customer.io.

---

## 1. Subir tudo

```bash
export PROJECT_ID="seu-projeto"
export DATASET="crm_rfm"
export ALERT_EMAIL="voce@aposta1.bet.br"

./deploy/setup_scheduler.sh
```

Ele pede o token do Customer.io de forma interativa e guarda no Secret Manager
— o token não passa por arquivo nem pelo histórico do shell.

Cria: service account com permissão mínima (`bigquery.dataEditor` e
`bigquery.jobUser`, nada de admin), segredo, imagem, Cloud Run Job com timeout
de 6h, agendamento diário e alerta de falha por e-mail.

É idempotente — rodar de novo atualiza em vez de duplicar.

---

## 2. Primeira execução, à mão

Não confie no agendamento antes de ver o job passar uma vez:

```bash
gcloud run jobs execute rfm-pipeline --region=southamerica-east1 --wait
```

A primeira carga usa janela de 200 dias (sem snapshot anterior, a janela é a
única fonte de histórico) e vai demorar bem mais que as seguintes, que usam 95.

**Espere ver menos gente do que o esperado nesta primeira vez.** Os "Lost" mais
antigos não geram evento nenhum na janela e ficam de fora até o carry-forward
acumular. A partir do segundo dia a base se completa. O job avisa isso em log.

---

## 3. O alerta que o Cloud Monitoring não consegue dar

O alerta do passo anterior cobre "o job falhou". Falta o caso pior: **o job
termina verde e grava dado errado.** Job com sucesso e base 40% menor não
dispara nada — e é exatamente o que quebra um dashboard em silêncio.

A view `vw_pipeline_alerts` detecta cinco sintomas: atraso, falha registrada,
salto impossível de volume, jogador duplicado no mesmo dia, e seed sintético
esquecido em produção.

Crie uma consulta agendada que avisa quando ela devolve alguma linha:

```bash
bq query --use_legacy_sql=false --display_name="RFM — alertas do pipeline" \
  --schedule="every 24 hours" \
  --destination_table="${DATASET}.pipeline_alert_log" \
  --append_table \
  "SELECT CURRENT_TIMESTAMP() AS detectado_em, sintoma, detalhe
   FROM \`${PROJECT_ID}.${DATASET}.vw_pipeline_alerts\`"
```

E um alerta de log em cima da tabela, ou — mais simples — deixe o painel de
frescor no topo do relatório (passo 4) e confira junto com o café. A tabela
`pipeline_alert_log` também serve de histórico: dá para ver se um sintoma é
novo ou se está lá há três semanas.

---

## 4. O carimbo de frescor no relatório

Este é o item que faz mais diferença por menos trabalho.

No Looker Studio, crie uma fonte apontando para `vw_data_freshness` e ponha um
**scorecard com o campo `aviso`** no topo de cada página. Ele já vem escrito:

- `Atualizado em 28/07`
- `⚠️ Parado há 3 dias · dado de 25/07`
- `⚠️ Última execução falhou · dado de 27/07`

Formatação condicional: fundo vermelho quando `estado` for `Falhou` ou
`Parado`, âmbar em `Atrasado`.

> Uma data solta não resolve — todo mundo lê "16/07" como "está atualizado"
> sem fazer a conta. O campo `aviso` diz a conclusão em vez do dado bruto,
> e é por isso que ele existe pronto na view.

---

## 5. Ordem dos extracts

O Looker atualiza os extracts no horário que você marcar, sem saber do
pipeline. Extract às 06:00 com job às 05:10 que demorou duas horas mostra o
dia anterior o dia inteiro.

Agende os extracts para **07:00**, e confira o horário de término real das
primeiras execuções:

```bash
gcloud run jobs executions list --job=rfm-pipeline \
  --region=southamerica-east1 --limit=5
```

Se o job estiver terminando depois das 07:00, atrase os extracts em vez de
adiantar o job — a Logs API não fica mais rápida de madrugada.

---

## 6. Trocar o token

```bash
printf '%s' "NOVO_TOKEN" | gcloud secrets versions add cio-api-token --data-file=-
```

O job usa `:latest`, então a próxima execução já pega. Não precisa
redeployar.

---

## O que ainda depende de gente

**A reconciliação com o Customer.io.** Uma vez por mês, ou depois de qualquer
edição nos segmentos `[RFM]`, compare as contagens (a consulta está no fim do
`docs/looker-blueprint.md`). Nenhum alerta pega isso: se alguém editar o
segmento 1956 pela interface, os dois lados continuam internamente
consistentes e passam a discordar entre si em silêncio.

**A conta da Logs API.** Ler 95 dias de três fluxos de evento todo dia é a
parte cara e frágil do desenho — é o que vai quebrar primeiro quando a base
crescer.

A saída seria o Customer.io entregar os eventos direto no BigQuery. O conector
existe e o plano cobre, mas a investigação em
[`docs/customerio-bigquery.md`](customerio-bigquery.md) mostrou que o obstáculo
está antes dele: nenhum source do CDP está emitindo os eventos de que
precisamos, o que sugere que eles entram pela Track API do Journeys — caminho
que não passa pelo pipeline do CDP. Leia aquela página antes de abrir a
conversa, para não pedir a integração errada.
