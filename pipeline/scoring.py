"""Classificação RFM — réplica fiel das regras que já rodam no Customer.io.

DE ONDE VÊM ESTAS REGRAS

Não foram inventadas aqui. Os segmentos 1952–1958 do workspace 112427 já
classificam a base em produção, e o dashboard atual conta essas caixas. Se este
código usasse cortes próprios, o Looker e o Customer.io mostrariam números
diferentes para "Champions" e ninguém conseguiria reconciliar os dois — o tipo
de divergência que mata a confiança num dashboard mais rápido do que qualquer
gráfico feio.

As regras abaixo são transcrição literal do campo `description` de cada
segmento, conferidas contra o `conditions` de cada um:

    1952 Champions       depositou <=7d E >=4x/30d
    1953 Loyal           depositou <=7d E 2-3x/30d
    1954 Promising/New   depositou <=7d E 1x/30d
    1955 Need Attention  último depósito 8-30d
    1956 At Risk         último depósito 31-90d
    1957 Hibernating     último depósito 91-180d
    1958 Lost            último depósito >180d
    1941 Base            já depositou (pré-requisito de todos)

O QUE ESTAS REGRAS *NÃO* FAZEM — e por que isso importa

Apesar do nome, a classificação em produção usa só R e F, ambos medidos sobre
depósito. O eixo M (valor) não entra: um jogador que depositou R$ 20 uma vez na
semana passada e outro que depositou R$ 8.000 caem os dois em "Promising".

Isso é exatamente o buraco por trás da pergunta "quanto vale cada arquétipo?".
A resposta deste módulo é deliberada: manter a CLASSIFICAÇÃO idêntica à de
produção (para os números baterem) e expor o valor num eixo separado —
`value_tier` — que alimenta a análise de LTV e a priorização do drill-down sem
mexer no rótulo do arquétipo.

Se um dia a decisão for levar o valor para dentro da classificação, isso muda os
números do dashboard e precisa mudar junto nos segmentos do Customer.io. Não é
um ajuste de código; é uma mudança de definição de negócio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# -----------------------------------------------------------------------------
# Cortes de recência de depósito, em dias. Espelham os `within` (em segundos)
# das condições dos segmentos: 604800 = 7d, 2592000 = 30d.
# -----------------------------------------------------------------------------
RECENCY_HOT: Final = 7        # <=7d  -> topo (Champions/Loyal/Promising)
RECENCY_COOLING: Final = 30   # 8-30d -> Need Attention
RECENCY_LAPSING: Final = 90   # 31-90d -> At Risk
RECENCY_DORMANT: Final = 180  # 91-180d -> Hibernating
#                             # >180d  -> Lost

# Cortes de frequência de depósito em 30 dias, aplicados só a quem está quente.
FREQ_CHAMPION: Final = 4      # >=4x/30d
FREQ_LOYAL: Final = 2         # 2-3x/30d
#                             # 1x/30d -> Promising

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
# sql/01_vw_rfm_daily.sql e com a ordem da rampa de cores no blueprint.
ARCHETYPE_RANK: Final = {name: i + 1 for i, name in enumerate(ARCHETYPES)}

# Faixas de valor depositado nos últimos 90 dias (BRL). Eixo SEPARADO da
# classificação — ver a nota no topo do módulo.
VALUE_TIERS: Final = [
    ("Alto", 2000.0),
    ("Médio", 500.0),
    ("Baixo", 50.0),
    ("Mínimo", 0.0),
]


def classify(
    days_since_last_deposit: int | None,
    deposits_30d: int,
) -> str | None:
    """Arquétipo a partir da recência e da contagem de depósitos em 30 dias.

    Devolve None para quem nunca depositou: essa pessoa está fora da base
    classificada (segmento 1941 é pré-requisito). São ~250 mil dos ~400 mil
    perfis do workspace, e é por isso que o dashboard fala em ~149 mil
    jogadores e não em 400 mil. Contá-los como "Lost" inflaria o pior balde com
    gente que nunca chegou a ser cliente.
    """
    if days_since_last_deposit is None:
        return None

    if days_since_last_deposit <= RECENCY_HOT:
        # Quem depositou na última semana necessariamente tem >=1 em 30 dias,
        # então estes três casos cobrem toda a faixa quente.
        if deposits_30d >= FREQ_CHAMPION:
            return "Champions"
        if deposits_30d >= FREQ_LOYAL:
            return "Loyal"
        return "Promising"

    if days_since_last_deposit <= RECENCY_COOLING:
        return "Need Attention"
    if days_since_last_deposit <= RECENCY_LAPSING:
        return "At Risk"
    if days_since_last_deposit <= RECENCY_DORMANT:
        return "Hibernating"
    return "Lost"


def value_tier(deposit_value_90d: float | None) -> str:
    """Eixo de valor, independente do arquétipo."""
    value = deposit_value_90d or 0.0
    for name, floor in VALUE_TIERS:
        if value >= floor:
            return name
    return "Mínimo"


@dataclass(frozen=True)
class RfmResult:
    archetype: str | None
    archetype_rank: int | None
    value_tier: str
    days_since_last_deposit: int | None
    deposits_30d: int
    deposit_value_90d: float


def score_player(
    days_since_last_deposit: int | None,
    deposits_30d: int = 0,
    deposit_value_90d: float | None = None,
) -> RfmResult:
    archetype = classify(days_since_last_deposit, deposits_30d)
    return RfmResult(
        archetype=archetype,
        archetype_rank=ARCHETYPE_RANK[archetype] if archetype else None,
        value_tier=value_tier(deposit_value_90d),
        days_since_last_deposit=days_since_last_deposit,
        deposits_30d=deposits_30d,
        deposit_value_90d=deposit_value_90d or 0.0,
    )
