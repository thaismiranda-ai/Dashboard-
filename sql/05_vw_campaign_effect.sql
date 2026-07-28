-- =============================================================================
-- 05 — Efeito de campanha por arquétipo.
--
-- ⚠️ LEIA ANTES DE APRESENTAR ESTES NÚMEROS.
-- Isto NÃO é um teste A/B. O grupo "não tocado" não foi sorteado — ele é o
-- resto da base que a régua não selecionou, e a régua seleciona justamente
-- quem tem mais chance de reagir (ou menos, dependendo da campanha). A
-- diferença entre tocado e não tocado mistura efeito da campanha com viés de
-- seleção, e vai quase sempre superestimar o efeito.
--
-- Use como termômetro de priorização ("qual régua merece um teste sério?"),
-- nunca como prova de incrementalidade. Para prova, é preciso holdout
-- aleatório no Customer.io — está documentado em docs/looker-blueprint.md.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 5a. Toque + estado antes e depois
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_campaign_outcomes` AS
WITH windows AS (
  SELECT w FROM UNNEST([7, 14]) AS w
),
touches AS (
  -- Um jogador pode receber a mesma campanha várias vezes na janela.
  -- Considera-se o primeiro toque do dia para não contar a mesma pessoa duas vezes.
  SELECT
    touch_date,
    player_id,
    campaign_id,
    ANY_VALUE(campaign_name) AS campaign_name,
    ANY_VALUE(channel)       AS channel,
    LOGICAL_OR(delivered)    AS delivered,
    LOGICAL_OR(opened)       AS opened,
    LOGICAL_OR(clicked)      AS clicked,
    LOGICAL_OR(converted)    AS converted
  FROM `${PROJECT_ID}.${DATASET}.campaign_touches`
  GROUP BY 1, 2, 3
)
SELECT
  w.w AS window_days,
  t.touch_date,
  t.campaign_id,
  t.campaign_name,
  t.channel,
  t.player_id,

  pre.archetype       AS archetype_before,
  pre.archetype_rank  AS rank_before,
  pre.health_bucket   AS health_before,
  pre.product_pref,
  pre.value_tier,
  pre.deposit_value_total       AS ltv_before,

  post.archetype      AS archetype_after,
  post.archetype_rank AS rank_after,
  post.health_bucket  AS health_after,

  t.delivered,
  t.opened,
  t.clicked,
  t.converted,

  pre.archetype_rank - post.archetype_rank AS steps_gained,
  post.archetype_rank < pre.archetype_rank AS recovered,
  post.archetype_rank > pre.archetype_rank AS degraded,

  -- Depósito incremental observado na janela. deposit_value_90d é uma janela móvel
  -- de 90 dias, então a diferença aproxima o que entrou (e o que caducou) —
  -- não é depósito bruto do período. Trate como direcional.
  post.deposit_value_90d - pre.deposit_value_90d     AS delta_deposits_90d

FROM touches AS t
CROSS JOIN windows AS w
JOIN `${PROJECT_ID}.${DATASET}.vw_rfm_daily` AS pre
  ON pre.player_id = t.player_id
 AND pre.snapshot_date = t.touch_date
JOIN `${PROJECT_ID}.${DATASET}.vw_rfm_daily` AS post
  ON post.player_id = t.player_id
 AND post.snapshot_date = DATE_ADD(t.touch_date, INTERVAL w.w DAY);


-- -----------------------------------------------------------------------------
-- 5b. Placar por campanha x arquétipo, com o grupo de comparação ao lado.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_campaign_effect` AS
WITH touched AS (
  SELECT
    window_days,
    touch_date          AS ref_date,
    campaign_id,
    campaign_name,
    channel,
    archetype_before,
    rank_before,

    COUNT(*)                                  AS players_touched,
    COUNTIF(delivered)                        AS delivered,
    COUNTIF(opened)                           AS opened,
    COUNTIF(clicked)                          AS clicked,
    COUNTIF(recovered)                        AS recovered,
    COUNTIF(degraded)                         AS degraded,
    SAFE_DIVIDE(COUNTIF(recovered), COUNT(*)) AS recovery_rate,
    AVG(delta_deposits_90d)                   AS avg_delta_deposits

  FROM `${PROJECT_ID}.${DATASET}.vw_campaign_outcomes`
  GROUP BY 1, 2, 3, 4, 5, 6, 7
),
-- Comparação: mesma data, mesmo arquétipo, quem NÃO recebeu NENHUMA campanha
-- na janela. Note o "nenhuma" — comparar com quem recebeu outra régua
-- responderia outra pergunta.
untouched AS (
  SELECT
    w.w                       AS window_days,
    pre.snapshot_date         AS ref_date,
    pre.archetype             AS archetype_before,

    COUNT(*)                                                        AS players_control,
    COUNTIF(post.archetype_rank < pre.archetype_rank)               AS recovered_control,
    SAFE_DIVIDE(COUNTIF(post.archetype_rank < pre.archetype_rank), COUNT(*))
                                                                    AS recovery_rate_control,
    AVG(post.deposit_value_90d - pre.deposit_value_90d)                       AS avg_delta_deposits_control

  FROM `${PROJECT_ID}.${DATASET}.vw_rfm_daily` AS pre
  CROSS JOIN UNNEST([7, 14]) AS w
  JOIN `${PROJECT_ID}.${DATASET}.vw_rfm_daily` AS post
    ON post.player_id = pre.player_id
   AND post.snapshot_date = DATE_ADD(pre.snapshot_date, INTERVAL w DAY)
  WHERE NOT EXISTS (
    SELECT 1
    FROM `${PROJECT_ID}.${DATASET}.campaign_touches` AS ct
    WHERE ct.player_id = pre.player_id
      AND ct.touch_date BETWEEN pre.snapshot_date
                            AND DATE_ADD(pre.snapshot_date, INTERVAL w DAY)
  )
  GROUP BY 1, 2, 3
)
SELECT
  t.window_days,
  t.ref_date,
  t.campaign_id,
  t.campaign_name,
  t.channel,
  t.archetype_before,
  t.rank_before,

  t.players_touched,
  t.delivered,
  t.opened,
  t.clicked,
  SAFE_DIVIDE(t.opened,  NULLIF(t.delivered, 0)) AS open_rate,
  SAFE_DIVIDE(t.clicked, NULLIF(t.opened, 0))    AS click_to_open_rate,

  t.recovered,
  t.degraded,
  t.recovery_rate,
  t.avg_delta_deposits,

  u.players_control,
  u.recovery_rate_control,
  u.avg_delta_deposits_control,

  -- Diferença observada, NÃO efeito causal. Ver o aviso no topo do arquivo.
  t.recovery_rate - u.recovery_rate_control AS recovery_rate_diff,
  SAFE_DIVIDE(t.recovery_rate, NULLIF(u.recovery_rate_control, 0)) AS recovery_rate_ratio,

  -- Guarda-chuva contra leitura de amostra minúscula: abaixo de ~300 tocados
  -- a diferença é ruído. O blueprint manda esconder essas linhas por padrão.
  t.players_touched >= 300 AND u.players_control >= 300 AS has_min_sample

FROM touched AS t
LEFT JOIN untouched AS u
  ON  u.window_days      = t.window_days
 AND  u.ref_date         = t.ref_date
 AND  u.archetype_before = t.archetype_before;
