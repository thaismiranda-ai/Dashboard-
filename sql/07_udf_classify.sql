-- =============================================================================
-- 07 — UDFs de classificação RFM.
--
-- Espelho fiel de pipeline/scoring.py, que por sua vez é espelho fiel dos
-- segmentos 1952–1958 do Customer.io (workspace 112427). Três lugares com a
-- mesma regra; os dois primeiros são checados um contra o outro por
-- pipeline/test_sql_parity.py. O terceiro — o Customer.io — não dá para
-- checar por código: se alguém editar um segmento pela interface, só a
-- consulta de reconciliação abaixo denuncia.
--
-- RECONCILIAÇÃO (rode depois de qualquer mexida em segmento):
--
--   SELECT archetype, COUNT(*) AS no_bigquery
--   FROM `proj.ds.rfm_snapshots`
--   WHERE snapshot_date = CURRENT_DATE()
--   GROUP BY 1 ORDER BY 1;
--
--   Compare com a contagem de cada segmento [RFM] na interface do Customer.io.
--   Diferença de mais de ~1% quer dizer que as definições saíram de sincronia.
--
-- AUDITORIA interna (Python x SQL):
--
--   SELECT COUNT(*) AS divergencias
--   FROM `proj.ds.rfm_snapshots`
--   WHERE archetype != `proj.ds.rfm_classify`(days_since_last_deposit, deposits_30d);
-- =============================================================================

-- Arquétipo a partir da recência de depósito e da contagem em 30 dias.
-- NULL = nunca depositou, portanto fora da base classificada (segmento 1941).
CREATE OR REPLACE FUNCTION `${PROJECT_ID}.${DATASET}.rfm_classify`(
  days_since_last_deposit INT64,
  deposits_30d INT64
)
RETURNS STRING
AS (
  CASE
    WHEN days_since_last_deposit IS NULL       THEN NULL          -- nunca depositou
    WHEN days_since_last_deposit <= 7 THEN
      CASE
        WHEN COALESCE(deposits_30d, 0) >= 4    THEN 'Champions'   -- seg 1952
        WHEN COALESCE(deposits_30d, 0) >= 2    THEN 'Loyal'       -- seg 1953
        ELSE                                        'Promising'   -- seg 1954
      END
    WHEN days_since_last_deposit <= 30         THEN 'Need Attention'  -- seg 1955
    WHEN days_since_last_deposit <= 90         THEN 'At Risk'         -- seg 1956
    WHEN days_since_last_deposit <= 180        THEN 'Hibernating'     -- seg 1957
    ELSE                                            'Lost'            -- seg 1958
  END
);

CREATE OR REPLACE FUNCTION `${PROJECT_ID}.${DATASET}.rfm_archetype_rank`(archetype STRING)
RETURNS INT64
AS (
  CASE archetype
    WHEN 'Champions'      THEN 1
    WHEN 'Loyal'          THEN 2
    WHEN 'Promising'      THEN 3
    WHEN 'Need Attention' THEN 4
    WHEN 'At Risk'        THEN 5
    WHEN 'Hibernating'    THEN 6
    WHEN 'Lost'           THEN 7
    ELSE NULL
  END
);

-- Eixo de valor — deliberadamente SEPARADO do arquétipo. A classificação em
-- produção não olha valor; esta função existe para que a análise de LTV e a
-- priorização do drill-down possam olhar, sem mexer no rótulo.
CREATE OR REPLACE FUNCTION `${PROJECT_ID}.${DATASET}.rfm_value_tier`(deposit_value_90d NUMERIC)
RETURNS STRING
AS (
  CASE
    WHEN COALESCE(deposit_value_90d, 0) >= 2000 THEN 'Alto'
    WHEN COALESCE(deposit_value_90d, 0) >= 500  THEN 'Médio'
    WHEN COALESCE(deposit_value_90d, 0) >= 50   THEN 'Baixo'
    ELSE                                             'Mínimo'
  END
);
