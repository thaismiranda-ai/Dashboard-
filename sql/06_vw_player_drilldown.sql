-- =============================================================================
-- 06 — Drill-down por jogador.
--
-- É a ponta acionável: o analista clica num arquétipo, chega numa lista de
-- pessoas, exporta e joga de volta no Customer.io como audiência.
--
-- Só o snapshot mais recente. Uma tabela de detalhe com histórico completo
-- multiplicaria ~150 mil jogadores por N dias e travaria o relatório.
-- =============================================================================

CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_player_drilldown` AS
WITH latest AS (
  SELECT MAX(snapshot_date) AS d FROM `${PROJECT_ID}.${DATASET}.rfm_snapshots`
),
cur AS (
  SELECT * FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily`
  WHERE snapshot_date = (SELECT d FROM latest)
),
prev_7 AS (
  SELECT player_id, archetype AS archetype_7d_ago, archetype_rank AS rank_7d_ago
  FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily`
  WHERE snapshot_date = DATE_SUB((SELECT d FROM latest), INTERVAL 7 DAY)
),
last_touch AS (
  SELECT
    player_id,
    MAX(touch_date) AS last_touch_date,
    -- ARRAY_AGG ... LIMIT 1 é o jeito de pegar "a campanha do toque mais
    -- recente" sem uma window function extra.
    ARRAY_AGG(campaign_name ORDER BY touch_date DESC LIMIT 1)[SAFE_OFFSET(0)]
      AS last_campaign_name,
    COUNTIF(touch_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)) AS touches_30d,
    COUNTIF(clicked AND touch_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)) AS clicks_30d
  FROM `${PROJECT_ID}.${DATASET}.campaign_touches`
  GROUP BY player_id
)
SELECT
  c.snapshot_date,
  c.player_id,

  c.archetype,
  c.archetype_rank,
  c.health_bucket,
  p.archetype_7d_ago,

  CASE
    WHEN p.rank_7d_ago IS NULL          THEN 'Novo na base'
    WHEN c.archetype_rank < p.rank_7d_ago THEN 'Recuperou'
    WHEN c.archetype_rank > p.rank_7d_ago THEN 'Piorou'
    ELSE 'Estável'
  END AS movement_7d,

  c.recency_days,
  c.frequency_90d,
  c.monetary_90d,
  c.ggr_90d,
  c.r_score,
  c.f_score,
  c.m_score,

  c.ltv_total,
  c.ggr_total,

  c.signup_date,
  c.first_deposit_date,
  c.last_bet_at,
  c.account_age_days,
  c.has_ftd,
  c.product_pref,
  c.channel,
  c.state_uf,
  c.is_vip,

  t.last_touch_date,
  t.last_campaign_name,
  COALESCE(t.touches_30d, 0) AS touches_30d,
  COALESCE(t.clicks_30d, 0)  AS clicks_30d,

  -- Fadiga de comunicação: muito toque, zero clique. Vale tirar da régua
  -- antes de queimar o canal.
  COALESCE(t.touches_30d, 0) >= 8 AND COALESCE(t.clicks_30d, 0) = 0 AS is_fatigued,

  -- Prioridade de ação. Ordem pensada para a lista já sair acionável:
  -- vale muito + está escorregando primeiro.
  CASE
    WHEN c.archetype = 'At Risk'        AND c.ltv_total >= 1000 THEN '1 · Resgatar valor alto'
    WHEN c.archetype = 'Need Attention' AND c.ltv_total >= 1000 THEN '2 · Segurar valor alto'
    WHEN c.archetype = 'At Risk'                                THEN '3 · Resgatar'
    WHEN c.archetype = 'Need Attention'                         THEN '4 · Reengajar'
    WHEN c.archetype = 'Promising'                              THEN '5 · Acelerar onboarding'
    WHEN c.archetype = 'Champions'                              THEN '6 · Manter (VIP)'
    WHEN c.archetype = 'Hibernating'                            THEN '7 · Reativação em massa'
    ELSE '8 · Sem ação'
  END AS action_priority

FROM cur AS c
LEFT JOIN prev_7    AS p USING (player_id)
LEFT JOIN last_touch AS t USING (player_id);


-- -----------------------------------------------------------------------------
-- 6b. Audiências prontas para exportar de volta ao Customer.io.
-- Uma linha por jogador em cada lista de trabalho. É esta view que o
-- `pipeline/rfm_pipeline.py --sync-audiences` lê.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_audience_export` AS
WITH tagged AS (
  SELECT
    player_id,
    archetype,
    ltv_total,
    recency_days,
    snapshot_date,
    CASE
      WHEN archetype = 'At Risk' AND ltv_total >= 1000 AND NOT is_fatigued
        THEN 'rfm_resgate_valor_alto'
      WHEN archetype = 'Need Attention' AND NOT is_fatigued
        THEN 'rfm_reengajamento'
      WHEN archetype = 'Promising' AND NOT has_ftd
        THEN 'rfm_onboarding_sem_ftd'
      WHEN archetype = 'Champions'
        THEN 'rfm_vip_manutencao'
      WHEN archetype = 'Hibernating' AND touches_30d = 0
        THEN 'rfm_reativacao_massa'
    END AS audience
  FROM `${PROJECT_ID}.${DATASET}.vw_player_drilldown`
)
SELECT player_id, audience, archetype, ltv_total, recency_days, snapshot_date
FROM tagged
WHERE audience IS NOT NULL;
