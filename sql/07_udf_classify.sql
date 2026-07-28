-- =============================================================================
-- 07 — UDFs de classificação RFM.
--
-- Espelho fiel de pipeline/scoring.py. O pipeline já grava `archetype` na
-- tabela, então em operação normal ninguém chama estas funções. Elas existem
-- para dois casos em que o Python não alcança:
--
--   1. Backfill — reclassificar meses de histórico direto no warehouse depois
--      de mudar um corte, sem reprocessar tudo pela API do Customer.io.
--   2. Auditoria — conferir que a tabela bate com a regra:
--
--      SELECT COUNT(*) AS divergencias
--      FROM `proj.ds.rfm_snapshots`
--      WHERE archetype != `proj.ds.rfm_classify`(r_score, fm_score);
--
--      Qualquer número diferente de zero significa que o pipeline e esta
--      definição saíram de sincronia. Mexeu num, mexa no outro.
-- =============================================================================

CREATE OR REPLACE FUNCTION `${PROJECT_ID}.${DATASET}.rfm_score_recency`(recency_days INT64)
RETURNS INT64
AS (
  CASE
    WHEN recency_days IS NULL THEN 1   -- nunca apostou = pior caso, não NULL
    WHEN recency_days <= 7    THEN 5
    WHEN recency_days <= 14   THEN 4
    WHEN recency_days <= 30   THEN 3
    WHEN recency_days <= 60   THEN 2
    ELSE 1
  END
);

CREATE OR REPLACE FUNCTION `${PROJECT_ID}.${DATASET}.rfm_score_frequency`(frequency_90d INT64)
RETURNS INT64
AS (
  CASE
    WHEN COALESCE(frequency_90d, 0) >= 60 THEN 5
    WHEN COALESCE(frequency_90d, 0) >= 20 THEN 4
    WHEN COALESCE(frequency_90d, 0) >= 8  THEN 3
    WHEN COALESCE(frequency_90d, 0) >= 3  THEN 2
    ELSE 1
  END
);

CREATE OR REPLACE FUNCTION `${PROJECT_ID}.${DATASET}.rfm_score_monetary`(monetary_90d NUMERIC)
RETURNS INT64
AS (
  CASE
    WHEN COALESCE(monetary_90d, 0) >= 2000 THEN 5
    WHEN COALESCE(monetary_90d, 0) >= 750  THEN 4
    WHEN COALESCE(monetary_90d, 0) >= 250  THEN 3
    WHEN COALESCE(monetary_90d, 0) >= 50   THEN 2
    ELSE 1
  END
);

-- Funde F e M num eixo. FLOOR(x + 0.5) arredonda o .5 sempre para cima —
-- ROUND() do BigQuery faz o mesmo, mas ser explícito aqui evita que alguém
-- "simplifique" para ROUND() num dialeto que arredonda para par e mude a
-- classificação de metade da base sem perceber.
CREATE OR REPLACE FUNCTION `${PROJECT_ID}.${DATASET}.rfm_combine_fm`(f_score INT64, m_score INT64)
RETURNS INT64
AS (
  CAST(FLOOR((f_score + m_score) / 2 + 0.5) AS INT64)
);

-- Grade 5x5. Ver a tabela completa em pipeline/scoring.py::classify.
CREATE OR REPLACE FUNCTION `${PROJECT_ID}.${DATASET}.rfm_classify`(r_score INT64, fm_score INT64)
RETURNS STRING
AS (
  CASE
    WHEN r_score <= 1                    THEN 'Lost'
    WHEN r_score = 2 AND fm_score >= 3   THEN 'At Risk'
    WHEN r_score = 2                     THEN 'Hibernating'
    WHEN r_score = 3 AND fm_score >= 4   THEN 'Loyal'
    WHEN r_score = 3                     THEN 'Need Attention'
    WHEN fm_score >= 4                   THEN 'Champions'
    WHEN fm_score = 3                    THEN 'Loyal'
    ELSE 'Promising'
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
    ELSE 99
  END
);
