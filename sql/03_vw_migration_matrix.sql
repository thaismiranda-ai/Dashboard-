-- =============================================================================
-- 03 — Matriz de migração: para onde cada jogador foi.
--
-- É a análise que o dashboard atual sugere mas não mostra. "At Risk caiu 8,7%
-- e Lost subiu" pode significar duas coisas opostas: os At Risk se recuperaram
-- e outra gente caiu em Lost, ou os próprios At Risk viraram Lost. Só a matriz
-- responde.
--
-- CUSTO: a view faz self-join da tabela particionada em 3 defasagens. Se a base
-- crescer muito, materialize com `sql/deploy.sh --materialize` em vez de deixar
-- o Looker recalcular a cada refresh.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 3a. Matriz completa origem -> destino
-- Filtre SEMPRE por lag_days no Looker (senão você soma 1d + 7d + 28d).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_migration_matrix` AS
WITH lags AS (
  SELECT lag_days FROM UNNEST([1, 7, 28]) AS lag_days
),
pairs AS (
  SELECT
    l.lag_days,
    cur.snapshot_date,
    cur.player_id,
    prv.archetype      AS archetype_from,
    prv.archetype_rank AS rank_from,
    cur.archetype      AS archetype_to,
    cur.archetype_rank AS rank_to,
    cur.product_pref,
    cur.utm_source,
    cur.value_tier,
    cur.deposit_value_total,
    cur.deposit_value_90d
  FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily` AS cur
  CROSS JOIN lags AS l
  -- INNER JOIN de propósito: quem não existia no snapshot anterior não é
  -- migração, é entrada de base. Isso vive na view 3c.
  JOIN `${PROJECT_ID}.${DATASET}.vw_rfm_daily` AS prv
    ON prv.player_id     = cur.player_id
   AND prv.snapshot_date = DATE_SUB(cur.snapshot_date, INTERVAL l.lag_days DAY)
)
SELECT
  lag_days,
  snapshot_date,
  archetype_from,
  rank_from,
  archetype_to,
  rank_to,
  product_pref,
  utm_source,
  value_tier,

  COUNT(*)          AS players,
  SUM(deposit_value_total)    AS value_moved,
  SUM(deposit_value_90d) AS deposits_90d_moved,

  -- Direção do movimento. rank menor = mais saudável, então rank_to < rank_from
  -- é subida.
  CASE
    WHEN rank_to < rank_from THEN 'Recuperou'
    WHEN rank_to > rank_from THEN 'Piorou'
    ELSE 'Ficou'
  END AS movement,

  rank_from - rank_to AS steps_gained   -- positivo = subiu de arquétipo

FROM pairs
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14;


-- -----------------------------------------------------------------------------
-- 3b. Fluxo líquido por arquétipo — quem ganhou e quem perdeu gente, e para
-- quem. Responde "o Need Attention cresceu 11% — veio de onde?".
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_migration_net_flow` AS
WITH m AS (
  SELECT * FROM `${PROJECT_ID}.${DATASET}.vw_migration_matrix`
),
inflow AS (
  SELECT lag_days, snapshot_date, archetype_to AS archetype,
         archetype_from AS counterpart, SUM(players) AS players, SUM(value_moved) AS ltv
  FROM m WHERE archetype_from != archetype_to
  GROUP BY 1, 2, 3, 4
),
outflow AS (
  SELECT lag_days, snapshot_date, archetype_from AS archetype,
         archetype_to AS counterpart, SUM(players) AS players, SUM(value_moved) AS ltv
  FROM m WHERE archetype_from != archetype_to
  GROUP BY 1, 2, 3, 4
)
SELECT
  COALESCE(i.lag_days, o.lag_days)           AS lag_days,
  COALESCE(i.snapshot_date, o.snapshot_date) AS snapshot_date,
  COALESCE(i.archetype, o.archetype)         AS archetype,
  COALESCE(i.counterpart, o.counterpart)     AS counterpart_archetype,

  COALESCE(i.players, 0)                     AS players_in,
  COALESCE(o.players, 0)                     AS players_out,
  COALESCE(i.players, 0) - COALESCE(o.players, 0) AS net_players,

  COALESCE(i.ltv, 0)                         AS ltv_in,
  COALESCE(o.ltv, 0)                         AS ltv_out,
  COALESCE(i.ltv, 0) - COALESCE(o.ltv, 0)    AS net_ltv

FROM inflow AS i
FULL OUTER JOIN outflow AS o
  ON  i.lag_days      = o.lag_days
 AND  i.snapshot_date = o.snapshot_date
 AND  i.archetype     = o.archetype
 AND  i.counterpart   = o.counterpart;


-- -----------------------------------------------------------------------------
-- 3c. Entradas e saídas da base — o que a matriz de migração NÃO cobre.
-- Sem isso os números não fecham e ninguém entende por quê.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_base_churn_flow` AS
WITH lags AS (
  SELECT lag_days FROM UNNEST([1, 7, 28]) AS lag_days
),
dates AS (
  SELECT DISTINCT snapshot_date FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily`
),
frame AS (
  SELECT d.snapshot_date, l.lag_days
  FROM dates AS d CROSS JOIN lags AS l
)
SELECT
  f.snapshot_date,
  f.lag_days,

  (SELECT COUNT(*) FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily` c
    WHERE c.snapshot_date = f.snapshot_date
      AND NOT EXISTS (
        SELECT 1 FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily` p
        WHERE p.player_id = c.player_id
          AND p.snapshot_date = DATE_SUB(f.snapshot_date, INTERVAL f.lag_days DAY))
  ) AS players_entered,

  (SELECT COUNT(*) FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily` p
    WHERE p.snapshot_date = DATE_SUB(f.snapshot_date, INTERVAL f.lag_days DAY)
      AND NOT EXISTS (
        SELECT 1 FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily` c
        WHERE c.player_id = p.player_id
          AND c.snapshot_date = f.snapshot_date)
  ) AS players_left

FROM frame AS f;
