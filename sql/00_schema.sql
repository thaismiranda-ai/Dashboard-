-- =============================================================================
-- 00_schema.sql — Tabelas base do RFM Health (Aposta1)
-- Executar UMA vez por ambiente. Idempotente (CREATE ... IF NOT EXISTS).
-- Substitua ${PROJECT_ID} e ${DATASET} antes de rodar (veja sql/deploy.sh).
--
-- AS COLUNAS SÃO O QUE O CUSTOMER.IO REALMENTE ENTREGA
--
-- O workspace 112427 não tem atributo de GGR, NGR, saldo, produto nem UF no
-- perfil. Foi verificado atributo por atributo (124 no total). O que existe:
--
--   · Valor  -> só de `DepositSuccessEvent.Amount` (depósito, não GGR).
--   · GGR    -> só derivável de esportes, via
--               `BetEvent.TotalStake - BetEvent.TotalWinnings`.
--               Cassino (`CasinoGameLaunchedEvent`) NÃO tem valor monetário
--               nenhum — só dá recência e frequência.
--   · Produto e canal -> só existem em evento, nunca no perfil.
--
-- Por isso não há coluna `ggr_total` nem `ltv_total` aqui: seriam um campo
-- bonito que ninguém consegue preencher com verdade. `deposit_value_total` é o
-- proxy honesto de valor, e o nome diz exatamente o que ele é.
--
-- Também não use os atributos `deposit_value_total` / `active_days_total` do
-- perfil: são contadores incrementais que as automations 533/540/541 começaram
-- a somar em ~jun/2026, sem backfill. Quem só olhar para eles vai achar que a
-- base inteira nasceu em junho. O pipeline reconstrói tudo dos eventos.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS `${PROJECT_ID}.${DATASET}`
OPTIONS (location = 'US');

-- -----------------------------------------------------------------------------
-- rfm_snapshots — 1 linha por jogador por dia. Coração do dashboard.
--
-- Contém apenas quem JÁ DEPOSITOU (equivalente ao segmento 1941). São ~149 mil
-- dos ~399 mil perfis do workspace. Os outros ~250 mil nunca foram clientes e
-- entrariam como "Lost", inflando o pior balde com gente que nunca chegou.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET}.rfm_snapshots`
(
  snapshot_date       DATE      NOT NULL OPTIONS (description = 'Dia da fotografia da base'),
  player_id           STRING    NOT NULL OPTIONS (description = 'customer id no Customer.io'),
  internal_id         STRING    OPTIONS (description = 'cio_id interno, para casar com logs'),

  -- Eixo R — recência de DEPÓSITO (é o que a classificação usa)
  days_since_last_deposit INT64 OPTIONS (description = 'Dias desde o último DepositSuccessEvent'),
  last_deposit_at     TIMESTAMP,

  -- Eixo F — contagem de depósitos por janela
  deposits_7d         INT64,
  deposits_30d        INT64     OPTIONS (description = 'Usado na classificação da faixa quente'),
  deposits_90d        INT64,
  deposits_total      INT64,

  -- Eixo M — valor depositado. NÃO entra na classificação (ver scoring.py).
  deposit_value_30d   NUMERIC,
  deposit_value_90d   NUMERIC,
  deposit_value_total NUMERIC   OPTIONS (description = 'Depósito acumulado, reconstruído de eventos'),

  -- Atividade de jogo (separada de depósito — jogar não é depositar)
  days_since_last_activity INT64,
  last_activity_at    TIMESTAMP,
  active_days_30d     INT64     OPTIONS (description = 'Dias distintos com aposta ou sessão de cassino'),

  -- Esportes: única fonte de GGR que existe
  sports_bets_90d     INT64,
  sports_stake_90d    NUMERIC,
  sports_winnings_90d NUMERIC,
  sports_ggr_90d      NUMERIC   OPTIONS (description = 'TotalStake - TotalWinnings de BetEvent. Só esportes.'),

  -- Cassino: sem valor monetário disponível na API
  casino_sessions_90d INT64     OPTIONS (description = 'Contagem de CasinoGameLaunchedEvent. Sem valor.'),

  archetype           STRING    OPTIONS (description = 'Champions | Loyal | Promising | Need Attention | At Risk | Hibernating | Lost'),
  value_tier          STRING    OPTIONS (description = 'Alto | Médio | Baixo | Mínimo — eixo separado do arquétipo'),

  -- Enriquecimento para filtros e drill-down
  signup_date         DATE,
  first_deposit_date  DATE      OPTIONS (description = 'De FirstDepositTimestamp'),
  product_pref        STRING    OPTIONS (description = 'cassino | esportes | ambos | nenhum — derivado de eventos'),
  platform            STRING    OPTIONS (description = 'web | mobile_app — do último DepositSuccessEvent'),
  device_os           STRING    OPTIONS (description = 'android | ios | unknown'),
  utm_source          STRING,
  utm_medium          STRING,
  utm_campaign        STRING,
  player_status       STRING    OPTIONS (description = 'Active | Blocked | RequiresKyc (PlayerStatusString)'),

  ingested_at         TIMESTAMP NOT NULL
)
PARTITION BY snapshot_date
CLUSTER BY archetype, product_pref
OPTIONS (
  description = 'Snapshot diário de RFM por jogador depositante. Fonte: Customer.io Exports + Logs API.',
  require_partition_filter = FALSE  -- o Looker precisa varrer janelas móveis
);

-- -----------------------------------------------------------------------------
-- campaign_touches — quem foi impactado por qual campanha e quando.
-- Fonte: POST /exports/deliveries por janela.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET}.campaign_touches`
(
  touch_date      DATE      NOT NULL,
  player_id       STRING    NOT NULL,
  campaign_id     STRING    NOT NULL,
  campaign_name   STRING,
  channel         STRING    OPTIONS (description = 'email | sms | push | webhook | in_app'),

  delivered       BOOL,
  opened          BOOL,
  clicked         BOOL,
  converted       BOOL      OPTIONS (description = 'Flag de conversão do próprio Customer.io'),

  ingested_at     TIMESTAMP NOT NULL
)
PARTITION BY touch_date
CLUSTER BY campaign_id, player_id
OPTIONS (description = 'Toques de campanha por jogador. Fonte: Customer.io deliveries export.');

-- -----------------------------------------------------------------------------
-- pipeline_runs — auditoria. Sem isso ninguém sabe se o dashboard está velho,
-- e um dashboard velho que parece atual é pior do que um dashboard quebrado.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET}.pipeline_runs`
(
  run_id          STRING    NOT NULL,
  snapshot_date   DATE      NOT NULL,
  started_at      TIMESTAMP NOT NULL,
  finished_at     TIMESTAMP,
  status          STRING    OPTIONS (description = 'running | success | failed'),
  players_written INT64,
  events_read     INT64,
  error_message   STRING
)
OPTIONS (description = 'Log de execuções do pipeline RFM.');
