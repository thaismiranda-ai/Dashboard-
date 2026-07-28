-- =============================================================================
-- 02 — Séries diárias por arquétipo.
--
-- São DUAS views de propósito diferente, e trocar uma pela outra é o erro mais
-- comum aqui:
--
--   vw_archetype_daily  -> mantém as dimensões de recorte (produto, canal, VIP).
--                          O Looker filtra e re-agrega à vontade. SEM deltas,
--                          porque delta de % não se soma entre recortes.
--   vw_archetype_trend  -> totais da base inteira, COM deltas de 1/7/28 dias
--                          já calculados. Use nos KPIs e no gráfico de evolução.
--                          NÃO aplique filtro de produto/canal em cima dela:
--                          os deltas continuariam sendo os da base inteira.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 2a. Série filtrável
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_archetype_daily` AS
SELECT
  snapshot_date,
  archetype,
  archetype_rank,
  health_bucket,
  growth_polarity,
  product_pref,
  utm_source,
  value_tier,
  platform,

  COUNT(*)                     AS players,
  SUM(deposit_value_90d)            AS deposits_90d,
  SUM(sports_ggr_90d)                 AS sports_ggr_90d,
  SUM(deposit_value_total)               AS deposit_value_total,
  AVG(days_since_last_deposit) AS avg_days_since_deposit,
  AVG(deposits_30d)            AS avg_deposits_30d,
  COUNTIF(has_ftd)             AS players_with_ftd

FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily`
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9;


-- -----------------------------------------------------------------------------
-- 2b. Série total com deltas
--
-- Os deltas usam LEFT JOIN em snapshot_date - N (e não LAG(N)), de propósito:
-- se o pipeline pular um dia, LAG(7) devolveria a variação de 8 dias sem avisar.
-- Com o join, um dia faltante vira NULL — visível no gráfico em vez de mentiroso.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_archetype_trend` AS
WITH by_day AS (
  SELECT
    snapshot_date,
    archetype,
    archetype_rank,
    health_bucket,
    growth_polarity,
    COUNT(*)          AS players,
    SUM(deposit_value_90d) AS deposits_90d,
    SUM(sports_ggr_90d)      AS sports_ggr_90d
  FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily`
  GROUP BY 1, 2, 3, 4, 5
),
day_totals AS (
  SELECT snapshot_date, SUM(players) AS base_players
  FROM by_day
  GROUP BY 1
)
SELECT
  d.snapshot_date,
  d.archetype,
  d.archetype_rank,
  d.health_bucket,
  d.growth_polarity,

  d.players,
  t.base_players,
  SAFE_DIVIDE(d.players, t.base_players) AS share,   -- formate como % no Looker

  d.deposits_90d,
  d.sports_ggr_90d,

  p1.players  AS players_d1,
  p7.players  AS players_d7,
  p28.players AS players_d28,

  d.players - p1.players  AS delta_abs_1d,
  d.players - p7.players  AS delta_abs_7d,
  d.players - p28.players AS delta_abs_28d,

  SAFE_DIVIDE(d.players - p1.players,  p1.players)  AS delta_pct_1d,
  SAFE_DIVIDE(d.players - p7.players,  p7.players)  AS delta_pct_7d,
  SAFE_DIVIDE(d.players - p28.players, p28.players) AS delta_pct_28d,

  -- Variação já orientada: positivo = movimento BOM, negativo = movimento RUIM,
  -- independente do sinal bruto. É este campo que deve colorir os cartões —
  -- "Lost +0,9%" não pode aparecer verde.
  SAFE_DIVIDE(d.players - p7.players, p7.players) * d.growth_polarity
    AS signed_move_7d

FROM by_day AS d
JOIN day_totals AS t
  ON t.snapshot_date = d.snapshot_date
LEFT JOIN by_day AS p1
  ON p1.archetype = d.archetype
 AND p1.snapshot_date = DATE_SUB(d.snapshot_date, INTERVAL 1 DAY)
LEFT JOIN by_day AS p7
  ON p7.archetype = d.archetype
 AND p7.snapshot_date = DATE_SUB(d.snapshot_date, INTERVAL 7 DAY)
LEFT JOIN by_day AS p28
  ON p28.archetype = d.archetype
 AND p28.snapshot_date = DATE_SUB(d.snapshot_date, INTERVAL 28 DAY);


-- -----------------------------------------------------------------------------
-- 2c. Saúde da base — uma linha por dia. Alimenta o KPI herói e a meta de 45%.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_base_health_daily` AS
WITH daily AS (
  SELECT
    snapshot_date,
    COUNT(*)                                                AS base_players,
    COUNTIF(health_bucket = 'Saudável')                      AS healthy_players,
    COUNTIF(health_bucket = 'Em risco')                      AS at_risk_players,
    COUNTIF(health_bucket = 'Frio')                          AS cold_players,
    SUM(deposit_value_total)                                           AS deposit_value_total,
    SUM(IF(health_bucket = 'Saudável', deposit_value_total, 0))         AS ltv_healthy
  FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily`
  GROUP BY 1
)
SELECT
  snapshot_date,
  base_players,
  healthy_players,
  at_risk_players,
  cold_players,

  SAFE_DIVIDE(healthy_players, base_players) AS healthy_share,
  0.45                                       AS healthy_target,  -- meta Q3
  SAFE_DIVIDE(healthy_players, base_players) - 0.45 AS gap_to_target,

  deposit_value_total,
  ltv_healthy,
  -- Quanto do valor da base está concentrado na fatia saudável. Se a base
  -- saudável é 4% mas carrega 60% do LTV, o número pequeno engana.
  SAFE_DIVIDE(ltv_healthy, deposit_value_total) AS ltv_share_healthy

FROM daily;
