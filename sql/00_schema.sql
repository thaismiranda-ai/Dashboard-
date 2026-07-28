-- =============================================================================
-- 00_schema.sql — Tabelas base do RFM Health (Aposta1)
-- Executar UMA vez por ambiente. Idempotente (CREATE ... IF NOT EXISTS).
-- =============================================================================
-- Substitua ${PROJECT_ID} e ${DATASET} antes de rodar (veja sql/deploy.sh).

CREATE SCHEMA IF NOT EXISTS `${PROJECT_ID}.${DATASET}`
OPTIONS (location = 'US');

-- -----------------------------------------------------------------------------
-- rfm_snapshots — 1 linha por jogador por dia. Coração do dashboard.
-- Particionada por snapshot_date e clusterizada por arquétipo para que os
-- filtros de período/segmento do Looker Studio não varram a tabela inteira.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET}.rfm_snapshots`
(
  snapshot_date   DATE      NOT NULL OPTIONS (description = 'Dia da fotografia da base'),
  player_id       STRING    NOT NULL OPTIONS (description = 'ID do jogador (customer id no Customer.io)'),

  -- Métricas cruas
  recency_days    INT64     OPTIONS (description = 'Dias desde a última aposta/atividade'),
  frequency_90d   INT64     OPTIONS (description = 'Nº de apostas/sessões nos últimos 90 dias'),
  monetary_90d    NUMERIC   OPTIONS (description = 'Depósito líquido em BRL nos últimos 90 dias'),
  ggr_90d         NUMERIC   OPTIONS (description = 'GGR em BRL nos últimos 90 dias'),

  -- Scores 1..5 (thresholds ABSOLUTOS — ver pipeline/scoring.py)
  r_score         INT64     OPTIONS (description = 'Score de recência, 1 (frio) a 5 (quente)'),
  f_score         INT64     OPTIONS (description = 'Score de frequência, 1 a 5'),
  m_score         INT64     OPTIONS (description = 'Score monetário, 1 a 5'),
  fm_score        INT64     OPTIONS (description = 'ROUND((f_score + m_score)/2) — eixo usado na matriz'),

  archetype       STRING    NOT NULL OPTIONS (description = 'Champions | Loyal | Promising | Need Attention | At Risk | Hibernating | Lost'),

  -- Enriquecimento para os filtros e o drill-down
  signup_date     DATE      OPTIONS (description = 'Data de cadastro'),
  first_deposit_date DATE   OPTIONS (description = 'Data do primeiro depósito (FTD)'),
  last_bet_at     TIMESTAMP OPTIONS (description = 'Timestamp da última aposta'),
  product_pref    STRING    OPTIONS (description = 'cassino | esportes | ambos | nenhum'),
  channel         STRING    OPTIONS (description = 'Canal de aquisição'),
  state_uf        STRING    OPTIONS (description = 'UF do jogador'),
  is_vip          BOOL      OPTIONS (description = 'Flag de VIP vinda do CRM'),

  ltv_total       NUMERIC   OPTIONS (description = 'Depósito líquido acumulado desde o cadastro'),
  ggr_total       NUMERIC   OPTIONS (description = 'GGR acumulado desde o cadastro'),

  ingested_at     TIMESTAMP NOT NULL OPTIONS (description = 'Quando o pipeline gravou esta linha')
)
PARTITION BY snapshot_date
CLUSTER BY archetype, product_pref
OPTIONS (
  description = 'Snapshot diário de RFM por jogador. Fonte: Customer.io -> pipeline RFM.',
  require_partition_filter = FALSE  -- Looker Studio precisa varrer janelas móveis
);

-- -----------------------------------------------------------------------------
-- campaign_touches — quem foi impactado por qual campanha e quando.
-- Alimenta a análise de "efeito de campanha" cruzada com arquétipo.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET}.campaign_touches`
(
  touch_date      DATE      NOT NULL OPTIONS (description = 'Dia do envio'),
  player_id       STRING    NOT NULL,
  campaign_id     STRING    NOT NULL OPTIONS (description = 'ID da campanha/automation no Customer.io'),
  campaign_name   STRING,
  channel         STRING    OPTIONS (description = 'email | push | sms | in_app | webhook'),

  delivered       BOOL      OPTIONS (description = 'Entrega confirmada'),
  opened          BOOL,
  clicked         BOOL,
  converted       BOOL      OPTIONS (description = 'Houve depósito ou aposta na janela de atribuição'),

  ingested_at     TIMESTAMP NOT NULL
)
PARTITION BY touch_date
CLUSTER BY campaign_id, player_id
OPTIONS (
  description = 'Toques de campanha por jogador. Fonte: Customer.io deliveries/activities.'
);

-- -----------------------------------------------------------------------------
-- pipeline_runs — auditoria. Sem isso ninguém sabe se o dashboard está velho.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET}.pipeline_runs`
(
  run_id          STRING    NOT NULL,
  snapshot_date   DATE      NOT NULL,
  started_at      TIMESTAMP NOT NULL,
  finished_at     TIMESTAMP,
  status          STRING    OPTIONS (description = 'running | success | failed'),
  players_written INT64,
  error_message   STRING
)
OPTIONS (description = 'Log de execuções do pipeline RFM.');
