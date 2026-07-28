-- =============================================================================
-- 01_vw_rfm_daily — View base. TODA outra view e todo gráfico do Looker
-- deveriam sair daqui, para que "arquétipo saudável" signifique a mesma coisa
-- em todo lugar.
-- =============================================================================

CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_rfm_daily` AS
WITH latest AS (
  SELECT MAX(snapshot_date) AS max_date
  FROM `${PROJECT_ID}.${DATASET}.rfm_snapshots`
)
SELECT
  s.snapshot_date,
  s.player_id,

  s.recency_days,
  s.frequency_90d,
  s.monetary_90d,
  s.ggr_90d,
  s.r_score,
  s.f_score,
  s.m_score,
  s.fm_score,
  s.archetype,

  -- Ordem canônica: 1 = mais saudável, 7 = mais frio.
  -- O Looker Studio ordena texto alfabeticamente por padrão, o que embaralha
  -- os arquétipos. Sempre ordene os gráficos por este campo.
  CASE s.archetype
    WHEN 'Champions'      THEN 1
    WHEN 'Loyal'          THEN 2
    WHEN 'Promising'      THEN 3
    WHEN 'Need Attention' THEN 4
    WHEN 'At Risk'        THEN 5
    WHEN 'Hibernating'    THEN 6
    WHEN 'Lost'           THEN 7
    ELSE 99
  END AS archetype_rank,

  -- Agrupamento executivo. "Base saudável" = Champions + Loyal + Promising.
  CASE
    WHEN s.archetype IN ('Champions', 'Loyal', 'Promising')  THEN 'Saudável'
    WHEN s.archetype IN ('Need Attention', 'At Risk')        THEN 'Em risco'
    ELSE 'Frio'
  END AS health_bucket,

  -- Em Champions/Loyal/Promising crescer é bom; nos demais crescer é ruim.
  -- Este sinal evita pintar de verde um crescimento de "Lost".
  CASE
    WHEN s.archetype IN ('Champions', 'Loyal', 'Promising') THEN 1
    ELSE -1
  END AS growth_polarity,

  s.signup_date,
  s.first_deposit_date,
  s.last_bet_at,
  COALESCE(s.product_pref, 'não informado') AS product_pref,
  COALESCE(s.channel,      'não informado') AS channel,
  COALESCE(s.state_uf,     'ND')            AS state_uf,
  COALESCE(s.is_vip, FALSE)                 AS is_vip,

  s.ltv_total,
  s.ggr_total,

  -- Idade da conta no dia do snapshot — separa "novo de verdade" de
  -- "cadastrado há um ano e nunca engajou".
  DATE_DIFF(s.snapshot_date, s.signup_date, DAY) AS account_age_days,
  s.first_deposit_date IS NOT NULL              AS has_ftd,

  -- Facilita filtros relativos no Looker sem depender de parâmetro de data.
  DATE_DIFF(l.max_date, s.snapshot_date, DAY)   AS days_ago,
  s.snapshot_date = l.max_date                  AS is_latest_snapshot

FROM `${PROJECT_ID}.${DATASET}.rfm_snapshots` AS s
CROSS JOIN latest AS l;
