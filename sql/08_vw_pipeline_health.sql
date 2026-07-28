-- =============================================================================
-- 08 — Saúde do pipeline.
--
-- Um dashboard que para de atualizar não fica em branco: ele continua
-- mostrando os números de anteontem, com a mesma cara de sempre. Quem abrir vai
-- tomar decisão em cima de dado velho sem desconfiar de nada — que é pior do
-- que um dashboard visivelmente quebrado.
--
-- Estas views existem para que isso seja impossível: uma alimenta o carimbo de
-- frescor no topo do relatório, a outra alimenta o alerta.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 8a. Frescor — uma linha só, para o cartão no topo do relatório.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_data_freshness` AS
WITH ultimo AS (
  SELECT
    MAX(snapshot_date) AS ultimo_snapshot,
    MAX(ingested_at)   AS ultima_ingestao,
    COUNT(DISTINCT snapshot_date) AS dias_no_historico
  FROM `${PROJECT_ID}.${DATASET}.rfm_snapshots`
),
ultima_corrida AS (
  SELECT status, finished_at, error_message, players_written
  FROM `${PROJECT_ID}.${DATASET}.pipeline_runs`
  ORDER BY started_at DESC
  LIMIT 1
)
SELECT
  u.ultimo_snapshot,
  u.ultima_ingestao,
  u.dias_no_historico,
  DATE_DIFF(CURRENT_DATE(), u.ultimo_snapshot, DAY) AS dias_de_atraso,

  r.status         AS status_ultima_corrida,
  r.finished_at    AS fim_ultima_corrida,
  r.error_message  AS erro_ultima_corrida,
  r.players_written,

  -- O pipeline roda de madrugada para o dia anterior, então 1 dia de defasagem
  -- é o normal. 2 já é um dia perdido.
  CASE
    WHEN r.status = 'failed'                                      THEN 'Falhou'
    WHEN DATE_DIFF(CURRENT_DATE(), u.ultimo_snapshot, DAY) <= 1   THEN 'Atualizado'
    WHEN DATE_DIFF(CURRENT_DATE(), u.ultimo_snapshot, DAY) <= 2   THEN 'Atrasado'
    ELSE                                                               'Parado'
  END AS estado,

  -- Texto pronto para o cartão. Melhor uma frase que ninguém precisa
  -- interpretar do que uma data que todo mundo lê como "está atualizado".
  CASE
    WHEN r.status = 'failed'
      THEN CONCAT('⚠️ Última execução falhou · dado de ',
                  FORMAT_DATE('%d/%m', u.ultimo_snapshot))
    WHEN DATE_DIFF(CURRENT_DATE(), u.ultimo_snapshot, DAY) <= 1
      THEN CONCAT('Atualizado em ', FORMAT_DATE('%d/%m', u.ultimo_snapshot))
    ELSE CONCAT('⚠️ Parado há ',
                CAST(DATE_DIFF(CURRENT_DATE(), u.ultimo_snapshot, DAY) AS STRING),
                ' dias · dado de ', FORMAT_DATE('%d/%m', u.ultimo_snapshot))
  END AS aviso

FROM ultimo AS u
CROSS JOIN ultima_corrida AS r;


-- -----------------------------------------------------------------------------
-- 8b. Sinais de problema. Uma linha por sintoma detectado; vazio = tudo bem.
--
-- É esta view que a consulta agendada de alerta lê. Detectar "não rodou" é o
-- óbvio; os outros três pegam o caso pior, em que o job termina com sucesso e
-- grava lixo.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.vw_pipeline_alerts` AS
WITH diario AS (
  SELECT
    snapshot_date,
    COUNT(*)                             AS jogadores,
    COUNTIF(archetype IS NULL)           AS sem_arquetipo,
    COUNT(DISTINCT player_id)            AS jogadores_distintos
  FROM `${PROJECT_ID}.${DATASET}.rfm_snapshots`
  GROUP BY 1
),
comparado AS (
  SELECT
    d.*,
    LAG(d.jogadores) OVER (ORDER BY d.snapshot_date) AS jogadores_ontem
  FROM diario AS d
),
ultimo_dia AS (
  SELECT * FROM comparado ORDER BY snapshot_date DESC LIMIT 1
)

-- 1. Não rodou.
SELECT
  'atraso' AS sintoma,
  CONCAT('Sem snapshot há ',
         CAST(DATE_DIFF(CURRENT_DATE(), MAX(snapshot_date), DAY) AS STRING),
         ' dias (último: ', CAST(MAX(snapshot_date) AS STRING), ')') AS detalhe
FROM `${PROJECT_ID}.${DATASET}.rfm_snapshots`
HAVING DATE_DIFF(CURRENT_DATE(), MAX(snapshot_date), DAY) >= 2

UNION ALL

-- 2. Rodou e falhou.
SELECT
  'falha',
  CONCAT('Execução de ', CAST(snapshot_date AS STRING), ' falhou: ',
         COALESCE(error_message, 'sem mensagem'))
FROM `${PROJECT_ID}.${DATASET}.pipeline_runs`
WHERE status = 'failed'
  AND started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 36 HOUR)

UNION ALL

-- 3. Rodou, deu "sucesso", e a base mudou de tamanho de um jeito impossível.
--    Uma variação de 20% em um dia numa base de 149 mil é erro de extração,
--    não comportamento de jogador.
SELECT
  'volume',
  CONCAT('Base saltou de ', CAST(jogadores_ontem AS STRING), ' para ',
         CAST(jogadores AS STRING), ' em um dia (',
         CAST(ROUND(SAFE_DIVIDE(jogadores - jogadores_ontem, jogadores_ontem) * 100, 1) AS STRING),
         '%)')
FROM ultimo_dia
WHERE jogadores_ontem IS NOT NULL
  AND ABS(SAFE_DIVIDE(jogadores - jogadores_ontem, jogadores_ontem)) > 0.20

UNION ALL

-- 4. Jogador duplicado no mesmo dia. Quebraria toda contagem sem aparecer em
--    lugar nenhum — os gráficos continuariam somando 100%.
SELECT
  'duplicidade',
  CONCAT(CAST(jogadores - jogadores_distintos AS STRING),
         ' linhas duplicadas em ', CAST(snapshot_date AS STRING))
FROM ultimo_dia
WHERE jogadores > jogadores_distintos

UNION ALL

-- 5. Seed sintético em produção. O `deploy.md` manda purgar antes de
--    compartilhar; isto é a rede caso alguém esqueça.
SELECT
  'seed',
  CONCAT(CAST(COUNT(*) AS STRING),
         ' linhas sintéticas (SEED-) ainda na tabela — rode a purga do deploy.md')
FROM `${PROJECT_ID}.${DATASET}.rfm_snapshots`
WHERE STARTS_WITH(player_id, 'SEED-')
HAVING COUNT(*) > 0;
