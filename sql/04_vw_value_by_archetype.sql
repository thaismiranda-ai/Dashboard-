-- =============================================================================
-- 04 — Valor por arquétipo.
--
-- O dashboard atual conta cabeças. Cabeça e real contam histórias diferentes:
-- Champions são 2,5% da base e provavelmente carregam a maior parte do GGR.
-- Enquanto o gráfico só mostrar headcount, "base saudável de 3,8%" parece uma
-- catástrofe quando pode ser concentração normal de valor.
-- =============================================================================

CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_value_by_archetype` AS
WITH base AS (
  SELECT
    snapshot_date,
    archetype,
    archetype_rank,
    health_bucket,
    product_pref,
    channel,
    is_vip,

    COUNT(*)                          AS players,
    COUNTIF(has_ftd)                  AS players_with_ftd,

    SUM(monetary_90d)                 AS deposits_90d,
    SUM(ggr_90d)                      AS ggr_90d,
    SUM(ltv_total)                    AS ltv_total,
    SUM(ggr_total)                    AS ggr_total,
    SUM(frequency_90d)                AS bets_90d,

    -- Mediana resiste a baleia. Sempre mostre as duas ao lado: se a média é
    -- 3x a mediana, o segmento é carregado por poucos jogadores.
    APPROX_QUANTILES(ltv_total, 100)[OFFSET(50)] AS ltv_median,
    APPROX_QUANTILES(ltv_total, 100)[OFFSET(90)] AS ltv_p90,
    APPROX_QUANTILES(ggr_90d,   100)[OFFSET(50)] AS ggr_90d_median

  FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily`
  GROUP BY 1, 2, 3, 4, 5, 6, 7
),
day_totals AS (
  SELECT
    snapshot_date,
    SUM(players)      AS total_players,
    SUM(ggr_90d)      AS total_ggr_90d,
    SUM(deposits_90d) AS total_deposits_90d,
    SUM(ltv_total)    AS total_ltv
  FROM base
  GROUP BY 1
)
SELECT
  b.snapshot_date,
  b.archetype,
  b.archetype_rank,
  b.health_bucket,
  b.product_pref,
  b.channel,
  b.is_vip,

  b.players,
  b.players_with_ftd,
  b.deposits_90d,
  b.ggr_90d,
  b.ltv_total,
  b.ggr_total,
  b.bets_90d,

  -- Por cabeça
  SAFE_DIVIDE(b.ggr_90d,      b.players) AS arpu_90d,
  SAFE_DIVIDE(b.deposits_90d, b.players) AS deposit_per_player_90d,
  SAFE_DIVIDE(b.ltv_total,    b.players) AS ltv_per_player,
  SAFE_DIVIDE(b.ggr_90d,      NULLIF(b.bets_90d, 0)) AS ggr_per_bet,
  b.ltv_median,
  b.ltv_p90,
  b.ggr_90d_median,

  -- Sinal de concentração: quanto a média se descola da mediana.
  SAFE_DIVIDE(SAFE_DIVIDE(b.ltv_total, b.players), NULLIF(b.ltv_median, 0))
    AS ltv_mean_to_median,

  -- Shares — o par que importa. Compare lado a lado no dashboard.
  SAFE_DIVIDE(b.players,   t.total_players)      AS share_of_players,
  SAFE_DIVIDE(b.ggr_90d,   t.total_ggr_90d)      AS share_of_ggr,
  SAFE_DIVIDE(b.ltv_total, t.total_ltv)          AS share_of_ltv,

  -- >1 significa que o segmento pesa mais no bolso do que no headcount.
  SAFE_DIVIDE(
    SAFE_DIVIDE(b.ggr_90d, t.total_ggr_90d),
    NULLIF(SAFE_DIVIDE(b.players, t.total_players), 0)
  ) AS value_index

FROM base AS b
JOIN day_totals AS t USING (snapshot_date);


-- -----------------------------------------------------------------------------
-- 4b. Coortes de cadastro x arquétipo atual.
-- Responde "as safras novas estão amadurecendo melhor do que as antigas?" —
-- que é a pergunta por trás de "Promising caiu 11,5%".
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_cohort_by_archetype` AS
SELECT
  snapshot_date,
  DATE_TRUNC(signup_date, MONTH) AS cohort_month,
  archetype,
  archetype_rank,
  health_bucket,
  product_pref,
  channel,

  COUNT(*)                       AS players,
  COUNTIF(has_ftd)               AS players_with_ftd,
  SUM(ltv_total)                 AS ltv_total,
  SUM(ggr_90d)                   AS ggr_90d,
  AVG(account_age_days)          AS avg_account_age_days,
  SAFE_DIVIDE(COUNTIF(has_ftd), COUNT(*)) AS ftd_rate

FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily`
WHERE signup_date IS NOT NULL
GROUP BY 1, 2, 3, 4, 5, 6, 7;
