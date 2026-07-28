"""Classificação RFM: de métricas cruas para um dos 7 arquétipos.

DECISÃO DE DESIGN — thresholds absolutos, não quintis.

O jeito clássico de pontuar RFM é por quintil: os 20% mais recentes ganham
R=5, e assim por diante. Aqui isso seria um tiro no pé. Quintil é relativo à
base do dia: se a base inteira esfriar, os quintis descem junto e o dashboard
mostra a mesma distribuição de sempre — o gráfico de evolução vira uma linha
reta que não significa nada.

Com corte absoluto ("R=5 é quem apostou nos últimos 7 dias"), a série temporal
passa a ser comparável entre dias, que é justamente o que o dashboard existe
para mostrar. O preço é que os cortes precisam ser revisados quando o negócio
muda de patamar — daí eles viverem aqui em cima, versionados, e não espalhados
pelo código.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# -----------------------------------------------------------------------------
# Cortes. Cada lista é (score, limite) avaliada de cima para baixo.
# -----------------------------------------------------------------------------

# Recência: dias desde a última aposta. Menor é melhor.
RECENCY_BANDS: Final = [
    (5, 7),    # apostou na última semana
    (4, 14),
    (3, 30),
    (2, 60),
    (1, None),  # mais de 60 dias — o resto
]

# Frequência: nº de apostas nos últimos 90 dias. Maior é melhor.
FREQUENCY_BANDS: Final = [
    (5, 60),
    (4, 20),
    (3, 8),
    (2, 3),
    (1, None),
]

# Monetário: depósito líquido em BRL nos últimos 90 dias. Maior é melhor.
MONETARY_BANDS: Final = [
    (5, 2000.0),
    (4, 750.0),
    (3, 250.0),
    (2, 50.0),
    (1, None),
]

ARCHETYPES: Final = (
    "Champions",
    "Loyal",
    "Promising",
    "Need Attention",
    "At Risk",
    "Hibernating",
    "Lost",
)

# Ordem canônica — precisa bater com o CASE de archetype_rank em
# sql/01_vw_rfm_daily.sql.
ARCHETYPE_RANK: Final = {name: i + 1 for i, name in enumerate(ARCHETYPES)}


def score_recency(recency_days: int | None) -> int:
    """Nunca apostou (None) é o pior caso possível, não um dado faltante."""
    if recency_days is None:
        return 1
    for score, limit in RECENCY_BANDS:
        if limit is None or recency_days <= limit:
            return score
    return 1


def score_frequency(frequency_90d: int | None) -> int:
    value = frequency_90d or 0
    for score, limit in FREQUENCY_BANDS:
        if limit is None or value >= limit:
            return score
    return 1


def score_monetary(monetary_90d: float | None) -> int:
    value = monetary_90d or 0.0
    for score, limit in MONETARY_BANDS:
        if limit is None or value >= limit:
            return score
    return 1


def combine_fm(f_score: int, m_score: int) -> int:
    """Funde F e M num eixo só.

    Com 5x5x5 seriam 125 combinações para mapear em 7 caixas — impossível de
    revisar e de explicar para o time de CRM. Colapsar F e M num eixo deixa uma
    grade 5x5 que cabe numa tabela e que qualquer pessoa consegue auditar.
    Arredonda para cima: entre "gasta pouco mas joga muito" e o contrário, o
    benefício da dúvida vai para o jogador.
    """
    return round((f_score + m_score) / 2 + 0.001)


def classify(r_score: int, fm_score: int) -> str:
    """Grade 5x5 (R x FM) -> arquétipo.

           FM=1        FM=2        FM=3            FM=4        FM=5
    R=5    Promising   Promising   Loyal           Champions   Champions
    R=4    Promising   Promising   Loyal           Champions   Champions
    R=3    Need Att.   Need Att.   Need Attention  Loyal       Loyal
    R=2    Hibernat.   Hibernat.   At Risk         At Risk     At Risk
    R=1    Lost        Lost        Lost            Lost        Lost

    As 25 células estão cobertas e são mutuamente exclusivas.

    Sobre a linha R=1 ser toda "Lost": um jogador de alto valor sumido há mais
    de 60 dias é tentador de chamar de "At Risk", mas risco é o que ainda dá
    para evitar. Depois de 60 dias a perda já aconteceu — o que existe é
    reconquista, que é outra régua e outro custo. Para achar essas baleias
    dentro de Lost, use ltv_total no drill-down (view 06), que é onde a
    pergunta "quem vale a pena reconquistar?" pertence.
    """
    if r_score <= 1:
        return "Lost"
    if r_score == 2:
        return "At Risk" if fm_score >= 3 else "Hibernating"
    if r_score == 3:
        return "Loyal" if fm_score >= 4 else "Need Attention"
    # r_score >= 4
    if fm_score >= 4:
        return "Champions"
    if fm_score == 3:
        return "Loyal"
    return "Promising"


@dataclass(frozen=True)
class RfmResult:
    r_score: int
    f_score: int
    m_score: int
    fm_score: int
    archetype: str
    archetype_rank: int


def score_player(
    recency_days: int | None,
    frequency_90d: int | None,
    monetary_90d: float | None,
) -> RfmResult:
    r = score_recency(recency_days)
    f = score_frequency(frequency_90d)
    m = score_monetary(monetary_90d)
    fm = combine_fm(f, m)
    archetype = classify(r, fm)
    return RfmResult(
        r_score=r,
        f_score=f,
        m_score=m,
        fm_score=fm,
        archetype=archetype,
        archetype_rank=ARCHETYPE_RANK[archetype],
    )
