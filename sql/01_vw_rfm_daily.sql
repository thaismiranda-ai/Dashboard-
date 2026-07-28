-- =============================================================================
-- 01_vw_rfm_daily — View base. TODA outra view e todo gráfico do Looker saem
-- daqui, para que "base saudável" signifique a mesma coisa em todo lugar.
-- =============================================================================

CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_rfm_daily` AS
WITH latest AS (
  SELECT MAX(snapshot_date) AS max_date
  FROM `${PROJECT_ID}.${DATASET}.rfm_snapshots`
)
SELECT
  s.snapshot_date,
  s.player_id,
  s.internal_id,

  s.days_since_last_deposit,
  s.deposits_7d,
  s.deposits_30d,
  s.deposits_90d,
  s.deposits_total,
  s.deposit_value_30d,
  s.deposit_value_90d,
  s.deposit_value_total,

  s.days_since_last_activity,
  s.active_days_30d,
  s.sports_bets_90d,
  s.sports_ggr_90d,
  s.casino_sessions_90d,

  s.archetype,
  s.value_tier,

  -- Ordem canônica: 1 = mais saudável, 7 = mais frio.
  -- O Looker Studio ordena texto alfabeticamente por padrão, o que embaralha os
  -- arquétipos e faz "At Risk" aparecer antes de "Champions". Ordene SEMPRE os
  -- gráficos por este campo, nunca pelo nome.
  CASE s.archetype
    WHEN 'Champions'      THEN 1
    WHEN 'Loyal'          THEN 2
    WHEN 'Promising'      THEN 3
    WHEN 'Need Attention' THEN 4
    WHEN 'At Risk'        THEN 5
    WHEN 'Hibernating'    THEN 6
    WHEN 'Lost'           THEN 7
  END AS archetype_rank,

  -- Agrupamento executivo. "Base saudável" = Champions + Loyal + Promising,
  -- que é a definição que o KPI herói e a meta de 45% usam.
  CASE
    WHEN s.archetype IN ('Champions', 'Loyal', 'Promising') THEN 'Saudável'
    WHEN s.archetype IN ('Need Attention', 'At Risk')       THEN 'Em risco'
    ELSE 'Frio'
  END AS health_bucket,

  -- Em Champions/Loyal/Promising crescer é bom; nos demais crescer é ruim.
  -- Sem este sinal o dashboard pinta "Lost +0,9%" de verde.
  CASE
    WHEN s.archetype IN ('Champions', 'Loyal', 'Promising') THEN 1
    ELSE -1
  END AS growth_polarity,

  s.signup_date,
  s.first_deposit_date,
  COALESCE(s.product_pref,   'não informado') AS product_pref,
  COALESCE(s.platform,       'não informado') AS platform,
  COALESCE(s.device_os,      'não informado') AS device_os,
  COALESCE(s.utm_source,     'direto')        AS utm_source,
  COALESCE(s.utm_medium,     'não informado') AS utm_medium,
  COALESCE(s.player_status,  'não informado') AS player_status,

  -- Idade da conta no dia do snapshot — separa "novo de verdade" de
  -- "cadastrado há um ano e depositou uma vez agora".
  DATE_DIFF(s.snapshot_date, s.signup_date, DAY)        AS account_age_days,
  DATE_DIFF(s.snapshot_date, s.first_deposit_date, DAY) AS days_since_ftd,
  s.first_deposit_date IS NOT NULL                      AS has_ftd,

  -- Jogou mas não depositou na janela: um sinal de intenção que a
  -- classificação (só depósito) não enxerga.
  s.days_since_last_activity < s.days_since_last_deposit AS active_but_not_depositing,

  -- Facilita filtros relativos no Looker sem depender de parâmetro de data.
  DATE_DIFF(l.max_date, s.snapshot_date, DAY) AS days_ago,
  s.snapshot_date = l.max_date                AS is_latest_snapshot

FROM `${PROJECT_ID}.${DATASET}.rfm_snapshots` AS s
CROSS JOIN latest AS l
-- Defesa: se o pipeline gravar alguém sem arquétipo, ele fica fora de todos os
-- gráficos em vez de virar uma fatia "null" silenciosa na composição.
WHERE s.archetype IS NOT NULL;
