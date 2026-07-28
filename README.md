# Dashboard RFM — Aposta1

Pipeline, modelo de dados e blueprint do dashboard de saúde da base de
jogadores. Customer.io → BigQuery → Looker Studio.

```
pipeline/   extração do Customer.io, classificação RFM e carga no BigQuery
sql/        DDL, views para o Looker e UDFs de classificação
docs/       blueprint de montagem do relatório
```

```bash
./run_tests.sh                                   # tudo que roda sem credencial
PROJECT_ID=... DATASET=crm_rfm ./sql/deploy.sh   # cria tabelas e views
python3 pipeline/seed_data.py --out /tmp/seed    # dados sintéticos p/ montar o layout
python3 pipeline/rfm_pipeline.py --dry-run       # calcula sem gravar
```

Para levantar o dashboard antes de existir carga real, siga
[`docs/deploy.md`](docs/deploy.md) — ele cobre deploy, seed, montagem e purga.

## O que você precisa saber antes de mexer

**As regras de classificação não são nossas.** Os segmentos 1952–1958 do
workspace 112427 já classificam a base em produção, e é deles que saem os
números que o time de CRM usa para disparar campanha.
`pipeline/scoring.py` transcreve essas regras. Mudar um corte aqui sem mudar
lá faz o Looker e o Customer.io discordarem sobre quantos Champions existem —
e a partir daí ninguém confia em nenhum dos dois.

**A base classificada é só quem já depositou.** São ~149 mil dos ~399 mil
perfis do workspace. Os outros ~250 mil nunca foram clientes; contá-los
inflaria "Lost" com gente que nunca chegou.

**Apesar do nome, a classificação em produção usa só R e F.** O eixo monetário
não entra: quem depositou R$ 20 e quem depositou R$ 8.000 na mesma semana caem
no mesmo arquétipo. Por isso o valor vive num eixo separado (`value_tier`,
`deposit_value_*`) e alimenta a análise de LTV sem mexer no rótulo.

**"GGR" aqui é só esportes.** Vem de `BetEvent.TotalStake - TotalWinnings`.
`CasinoGameLaunchedEvent` não expõe valor monetário nenhum, então cassino
entra em recência e frequência e nunca em receita. Não existe atributo de GGR,
NGR ou saldo no perfil — foi conferido nos 124 atributos do workspace.

**Não use os atributos `deposit_value_total` / `active_days_total` do perfil.**
São contadores que as automations 533/540/541 começaram a somar em ~jun/2026,
sem backfill. Quem depositou R$ 50 mil em 2024 aparece com R$ 0. O pipeline
reconstrói tudo dos eventos justamente por isso.

## Modelo de dados

`rfm_snapshots` guarda uma linha por jogador por dia. Todas as views saem de
`vw_rfm_daily`, que é onde "base saudável" e a ordem dos arquétipos são
definidas uma única vez.

| View | Responde |
|---|---|
| `vw_base_health_daily` | Qual o tamanho da base saudável e a distância da meta |
| `vw_archetype_trend` | Como cada arquétipo variou em 1, 7 e 28 dias |
| `vw_archetype_daily` | O mesmo, mas filtrável por produto, canal e faixa de valor |
| `vw_migration_matrix` | Quem saiu de onde e foi para onde |
| `vw_migration_net_flow` | Quem ganhou e perdeu gente, e para quem |
| `vw_base_churn_flow` | Quem entrou e quem saiu da base |
| `vw_value_by_archetype` | Quanto cada arquétipo pesa em cabeças e em reais |
| `vw_cohort_by_archetype` | Se as safras novas amadurecem melhor que as antigas |
| `vw_campaign_effect` | Se quem foi tocado se recuperou mais que quem não foi |
| `vw_player_drilldown` | A lista de pessoas, pronta para exportar |

## Pipeline

```bash
export CIO_API_TOKEN="..."       # ou CIO_USE_CLI=1 para delegar ao CLI `cio`
export BQ_PROJECT="..."

python3 pipeline/rfm_pipeline.py --date 2026-07-28
python3 pipeline/rfm_pipeline.py --backfill-from 2026-07-01 --backfill-to 2026-07-28
```

Roda uma vez por dia. Cada execução lê ~200 dias de eventos da Logs API (50 por
página, com cursor), recalcula as janelas móveis e herda o histórico de vida do
snapshot anterior — é esse carry-forward que mantém os "Lost" antigos na base,
já que eles não geram evento nenhum na janela.

Reprocessar um dia é seguro: eventos posteriores à data são ignorados e a
partição é substituída, não acrescentada.

## Estado

Roda e é testado: classificação, agregação, carry-forward, paridade
Python/SQL e consistência entre as colunas do Python e do DDL — 39 casos.

Não foi executado contra a API real nem contra o BigQuery: este ambiente não
tem credencial de nenhum dos dois. A troca do service account token por JWT é
a única parte do código escrita sem confirmação no schema, e está marcada no
cabeçalho de `pipeline/cio_client.py`. Na primeira execução com credencial,
comece por `--dry-run`.
