# Entregar eventos do Customer.io direto no BigQuery

Investigação sobre substituir a leitura diária da Logs API por entrega contínua.
Workspace 112427 (Aposta1, EU, conta 69932). Levantamento feito **só com
leituras** — nada foi criado, alterado ou habilitado.

---

## Resposta curta

O conector existe e o plano cobre. O obstáculo é **antes** do conector: não
está confirmado que os eventos que precisamos passam pelo pipeline do CDP.

---

## Três coisas com nomes parecidos e direções diferentes

Esta é a parte que faz o pedido sair errado. As três existem no Customer.io:

| | Direção | Onde vive | Serve? |
|---|---|---|---|
| **Warehouse Sync** | sai → object storage | `/v1/environments/112427/warehouse_sync` | **Não.** Só S3, GCS, Azure e Yandex — o body não tem bloco de BigQuery |
| **CDP Destination** | sai → ferramenta externa | `/cdp/api/workspaces/112427/destinations` | **Sim, é este** |
| **Reverse ETL** | entra ← warehouse | `/cdp/api/workspaces/112427/reverse_etls` | **Não.** Traz dado *do* BigQuery *para* o Customer.io |

O Warehouse Sync não suportar BigQuery é fato do schema, não leitura de
documentação: o corpo do POST tem exatamente quatro blocos de storage
(`s3_config`, `gcs_config`, `azure_config`, `yandex_config`) e nenhum é
warehouse.

Cuidado também com dois conectores de nome quase igual: `bigquery` (source, de
entrada) e `google-bigquery` (destination, de saída). São coisas opostas.

---

## O que está liberado

Do catálogo `/cdp/api/workspaces/112427/available_destinations`:

| Destino | option_id | mode | premium |
|---|---|---|---|
| Google BigQuery (Advanced) | `google-bigquery` | `static-etl` | sim |
| Snowflake (Advanced) | `snowflake` | `static-etl` | sim |
| Amazon Redshift (Advanced) | `amazon-redshift` | `static-etl` | sim |
| Google Cloud Storage (Advanced) | `google-cloud-storage` | `cloud` | sim |

Databricks não está no catálogo.

A conta é `premium: true` e `gated_features` inclui
**`cdp_premium_integrations`** — que é o que os destinos de warehouse exigem.
`warehouse_sync` também está liberado (o 404 daquele endpoint significa "não
há sync configurado", não "indisponível").

---

## O obstáculo

Um destination só recebe o que entrou no pipeline **por um source**. Da própria
documentação interna do Customer.io:

> The payload always originates from a CDP source. A destination action can
> only fire on data that entered the pipeline through a source. A Journeys
> workflow "Send Event" action does not produce a source payload; its event
> stays inside Journeys and never reaches this destination.

Os sete sources do workspace hoje:

| id | nome | eventos | ligado a destino |
|---|---|---|---|
| 2583 | Journeys Message Metrics | **ativo** (`Email Sent`, `Email Delivered`) | nenhum |
| 73154 | React Native | — | Journeys Workspace (1374) |
| 10390 | Journeys API: Casino Millionaire | 0 | nenhum |
| 10392 | Journeys API: ap1-web | 0 | nenhum |
| 10483 | Journeys API: aposta1-prod | 0 | nenhum |
| 83891 | Journeys API: pipeline-rfm-bigquery | 0 | nenhum |
| 84309 | Journeys API: n8n-zenvia-webhook | 0 | nenhum |

**Nenhum source está emitindo `DepositSuccessEvent`, `BetEvent` ou
`CasinoGameLaunchedEvent`.** O único source vivo emite métrica de e-mail, que
não é o que o RFM precisa.

Isso é consistente com os eventos entrarem pela Track API do Journeys, direto —
caminho que não passa pelo CDP. Se for esse o caso, ligar um destino BigQuery
hoje entregaria métrica de e-mail e mais nada.

> Também vale conferir: já existe um source chamado
> `Journeys API: pipeline-rfm-bigquery` (id 83891), com zero eventos. Alguém do
> time pode ter começado isso antes. Vale saber quem e por quê antes de mexer.

---

## O que não deu para determinar pela API

Registrado sem preencher com palpite:

1. **Os campos de configuração do destino BigQuery.** O endpoint de manifest
   devolve 404 para conectores `static-etl` — é estrutural, não permissão (o
   mesmo endpoint funciona para o GCS, que é `mode: cloud`). Não extrapolei do
   GCS: são conectores diferentes.
2. **A cadência de entrega.** O nome `static-etl` sugere lote, não streaming, e
   a API não expõe intervalo nem latência. Isso muda materialmente a conta — se
   for lote diário, o ganho sobre o pipeline atual é bem menor do que parece.
3. **Se o destino cria as tabelas sozinho** ou exige schema pré-criado.
4. **Custo.** O endpoint de billing devolve 403 para o papel `CRM Analyst`. Não
   sei se há cobrança por volume entregue.
5. **Se um source `customerio` pode alimentar um destino `static-etl`.** Nada na
   API confirma nem proíbe.

---

## Próximos passos, na ordem

**1. Descobrir por onde os eventos entram.** É a pergunta que decide tudo o
resto, e não custa nada: quem integrou o backoffice sabe se usa a Track API do
Journeys ou um source do CDP. Se for Track API direto, o restante desta página
fica em suspenso até essa integração mudar de caminho — e mudar o caminho de
ingestão de uma base em produção é um projeto, não um ajuste.

**2. Se os eventos passarem pelo CDP**, abrir o formulário do conector em
`fly.customer.io/workspaces/112427/pipelines/destinations/add?destination=google-bigquery`
e transcrever os campos. Isso resolve os itens 1, 2 e 3 da lista acima de uma
vez — o que a API esconde, a interface mostra.

**3. Confirmar a cadência antes de desenhar qualquer coisa.** Entrega em lote
diário não justifica trocar o pipeline; entrega contínua justifica.

**4. Custo com o CSM.** A conta tem um (`has_csm: true`), e essa é a via — o
papel atual não enxerga billing.

---

## Enquanto isso

O pipeline atual continua sendo o caminho certo. A leitura diária da Logs API é
a parte cara e frágil do desenho, mas ela funciona, e trocá-la depende de uma
mudança de ingestão que está fora do alcance deste repositório.

Se a pressão de custo aparecer antes da resposta do item 1, o ajuste barato é
reduzir a janela incremental: hoje são 95 dias porque a métrica mais longa é de
90. Cortar as janelas de 90 para 30 dias derrubaria o volume de leitura em
dois terços, ao custo de perder as métricas de 90 dias — que hoje quase não são
usadas no relatório.
