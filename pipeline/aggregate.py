"""Agregação de eventos crus em métricas RFM por jogador.

Esta camada é pura de propósito: entra lista de eventos, sai dicionário por
jogador. Nada de rede, nada de BigQuery, nada de relógio — a data de referência
é parâmetro. É o que permite testar a parte que erra de verdade (janelas,
fusos, conversão de tipo) sem credencial nenhuma.

ARMADILHAS DOS DADOS, todas confirmadas contra a API:

  · Todo atributo volta como STRING. `Amount` é `"100"`, nunca 100. Somar sem
    converter concatena em silêncio.
  · Timestamps são epoch em SEGUNDOS, como string — menos `last_active_date`,
    que é `YYYY-MM-DD`.
  · `TotalStake`/`TotalWinnings` (BetEvent) podem vir ausentes ou vazios.
  · CasinoGameLaunchedEvent não tem valor monetário nenhum. Cassino entra em
    recência e frequência, jamais em receita.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable

# Fuso do negócio. Um depósito às 22h de Brasília é 01h UTC do dia seguinte;
# usar UTC cru joga a atividade da noite para o dia errado e faz a recência
# oscilar um dia sem motivo.
TZ_OFFSET_HOURS = -3


def to_float(value: Any) -> float:
    """Converte valor da API para float. String vazia, None e lixo viram 0.0."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    texto = str(value).strip().replace(",", ".")
    if not texto:
        return 0.0
    try:
        return float(texto)
    except ValueError:
        return 0.0


def to_int(value: Any) -> int:
    return int(to_float(value))


def epoch_to_local_date(epoch: Any) -> date | None:
    """Epoch em segundos (int ou string) -> data no fuso do negócio."""
    segundos = to_int(epoch)
    if segundos <= 0:
        return None
    dt = datetime.fromtimestamp(segundos, tz=timezone.utc)
    return dt.astimezone(timezone(_offset())).date()


def _offset():
    from datetime import timedelta

    return timedelta(hours=TZ_OFFSET_HOURS)


@dataclass
class PlayerMetrics:
    player_id: str
    internal_id: str | None = None

    last_deposit_date: date | None = None
    deposits_7d: int = 0
    deposits_30d: int = 0
    deposits_90d: int = 0
    deposits_total: int = 0
    deposit_value_30d: float = 0.0
    deposit_value_90d: float = 0.0
    deposit_value_total: float = 0.0

    # (dia, valor) de cada depósito visto na janela. Guardado porque o
    # carry-forward precisa somar só os depósitos posteriores ao snapshot
    # anterior — sem a lista, não dá para saber quais são.
    deposit_events: list[tuple[date, float]] = field(default_factory=list)

    last_activity_date: date | None = None
    active_dates_30d: set[date] = field(default_factory=set)

    sports_bets_90d: int = 0
    sports_stake_90d: float = 0.0
    sports_winnings_90d: float = 0.0
    casino_sessions_90d: int = 0

    platform: str | None = None
    device_os: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None

    def days_since_last_deposit(self, ref: date) -> int | None:
        if self.last_deposit_date is None:
            return None
        return (ref - self.last_deposit_date).days

    def days_since_last_activity(self, ref: date) -> int | None:
        if self.last_activity_date is None:
            return None
        return (ref - self.last_activity_date).days

    def deposits_since(self, corte: date) -> int:
        """Depósitos ESTRITAMENTE depois de `corte`. Usado no carry-forward."""
        return sum(1 for dia, _ in self.deposit_events if dia > corte)

    def deposit_value_since(self, corte: date) -> float:
        return sum(v for dia, v in self.deposit_events if dia > corte)

    @property
    def sports_ggr_90d(self) -> float:
        """GGR de esportes. Pode ser NEGATIVO num período em que os jogadores
        ganharam mais do que apostaram — isso é real, não é bug. Zerar aqui
        inflaria a receita."""
        return self.sports_stake_90d - self.sports_winnings_90d

    @property
    def product_pref(self) -> str:
        tem_esporte = self.sports_bets_90d > 0
        tem_cassino = self.casino_sessions_90d > 0
        if tem_esporte and tem_cassino:
            return "ambos"
        if tem_esporte:
            return "esportes"
        if tem_cassino:
            return "cassino"
        return "nenhum"


def _log_date(log: dict) -> date | None:
    return epoch_to_local_date(log.get("timestamp"))


def _player_id(log: dict) -> str | None:
    return log.get("customer_id") or log.get("internal_id")


def aggregate_events(
    deposits: Iterable[dict],
    bets: Iterable[dict],
    casino: Iterable[dict],
    ref_date: date,
) -> dict[str, PlayerMetrics]:
    """Consolida os três fluxos de evento em métricas por jogador.

    `ref_date` é o dia do snapshot. Todas as janelas (7/30/90) são contadas
    para trás a partir dele — nunca a partir de "hoje", para que reprocessar um
    dia antigo dê o mesmo resultado de quando ele rodou pela primeira vez.
    """
    players: dict[str, PlayerMetrics] = {}

    def get(pid: str, log: dict) -> PlayerMetrics:
        if pid not in players:
            players[pid] = PlayerMetrics(
                player_id=pid, internal_id=log.get("internal_id")
            )
        return players[pid]

    # --- depósitos: alimentam R, F e M ---
    for log in deposits:
        pid = _player_id(log)
        dia = _log_date(log)
        if not pid or dia is None or dia > ref_date:
            continue
        m = get(pid, log)
        attrs = log.get("attrs") or {}
        valor = to_float(attrs.get("Amount"))
        idade = (ref_date - dia).days

        m.deposit_events.append((dia, valor))
        m.deposits_total += 1
        m.deposit_value_total += valor
        if idade <= 7:
            m.deposits_7d += 1
        if idade <= 30:
            m.deposits_30d += 1
            m.deposit_value_30d += valor
        if idade <= 90:
            m.deposits_90d += 1
            m.deposit_value_90d += valor

        if m.last_deposit_date is None or dia > m.last_deposit_date:
            m.last_deposit_date = dia
            # Plataforma/canal vêm do depósito MAIS RECENTE — é o retrato de
            # como a pessoa se comporta hoje, não de como ela chegou.
            m.platform = attrs.get("Platform") or m.platform
            m.device_os = attrs.get("DeviceOS") or m.device_os
            m.utm_source = attrs.get("UtmSource") or m.utm_source
            m.utm_medium = attrs.get("UtmMedium") or m.utm_medium
            m.utm_campaign = attrs.get("UtmCampaign") or m.utm_campaign

    # --- apostas esportivas: atividade + única fonte de GGR ---
    for log in bets:
        pid = _player_id(log)
        dia = _log_date(log)
        if not pid or dia is None or dia > ref_date:
            continue
        m = get(pid, log)
        attrs = log.get("attrs") or {}
        idade = (ref_date - dia).days

        if idade <= 90:
            m.sports_bets_90d += 1
            m.sports_stake_90d += to_float(attrs.get("TotalStake"))
            m.sports_winnings_90d += to_float(attrs.get("TotalWinnings"))
        if idade <= 30:
            m.active_dates_30d.add(dia)
        if m.last_activity_date is None or dia > m.last_activity_date:
            m.last_activity_date = dia

    # --- cassino: só recência e frequência, nunca valor ---
    for log in casino:
        pid = _player_id(log)
        dia = _log_date(log)
        if not pid or dia is None or dia > ref_date:
            continue
        m = get(pid, log)
        idade = (ref_date - dia).days

        if idade <= 90:
            m.casino_sessions_90d += 1
        if idade <= 30:
            m.active_dates_30d.add(dia)
        if m.last_activity_date is None or dia > m.last_activity_date:
            m.last_activity_date = dia

    return players


def carry_forward(
    metrics: dict[str, PlayerMetrics],
    previous_rows: Iterable[dict],
    ref_date: date,
) -> dict[str, PlayerMetrics]:
    """Traz o histórico do snapshot anterior para o de hoje.

    POR QUE ISSO EXISTE — o bug que ele conserta

    O pipeline lê uma janela de eventos (~200 dias). Quem depositou pela última
    vez há 300 dias não produz UM evento nessa janela: sem carry-forward, essa
    pessoa simplesmente não gera linha e some do dashboard. Só que ela é
    exatamente o arquétipo "Lost" — que é ~60% da base. O dashboard perderia a
    maioria da base e ainda pareceria certo, porque as porcentagens continuam
    somando 100%.

    A separação que resolve:

      · Métricas de JANELA (7/30/90 dias) sempre saem dos eventos lidos. A
        janela é maior que 90 dias, então elas estão sempre completas e não há
        risco de contar duas vezes.
      · Métricas de VIDA (último depósito, total acumulado) vêm do snapshot
        anterior e só recebem os eventos posteriores a ele. É o que dá memória
        além da janela.

    O efeito colateral bom é custo: depois da carga inicial, a janela poderia
    até encolher para ~95 dias sem perder ninguém.
    """
    for prev in previous_rows:
        pid = prev.get("player_id")
        if not pid:
            continue

        prev_last = prev.get("last_deposit_date")
        if isinstance(prev_last, str):
            prev_last = date.fromisoformat(prev_last[:10])

        m = metrics.get(pid)
        if m is None:
            # Nenhum evento na janela: o jogador existe só pelo histórico.
            # É o caso do "Lost" que sumiria.
            m = PlayerMetrics(player_id=pid, internal_id=prev.get("internal_id"))
            m.last_deposit_date = prev_last
            m.deposits_total = to_int(prev.get("deposits_total"))
            m.deposit_value_total = to_float(prev.get("deposit_value_total"))
            m.platform = prev.get("platform")
            m.device_os = prev.get("device_os")
            m.utm_source = prev.get("utm_source")
            m.utm_medium = prev.get("utm_medium")
            m.utm_campaign = prev.get("utm_campaign")
            metrics[pid] = m
            continue

        # Jogador com eventos na janela: soma o acumulado antigo apenas dos
        # eventos ANTERIORES ao snapshot passado, que é o que a janela não
        # cobriu. Os eventos de dentro da janela já foram contados.
        prev_snapshot = prev.get("snapshot_date")
        if isinstance(prev_snapshot, str):
            prev_snapshot = date.fromisoformat(prev_snapshot[:10])

        novos_desde = m.deposits_since(prev_snapshot) if prev_snapshot else 0
        valor_desde = m.deposit_value_since(prev_snapshot) if prev_snapshot else 0.0

        m.deposits_total = to_int(prev.get("deposits_total")) + novos_desde
        m.deposit_value_total = to_float(prev.get("deposit_value_total")) + valor_desde

        if prev_last and (m.last_deposit_date is None or prev_last > m.last_deposit_date):
            m.last_deposit_date = prev_last

    return metrics


def merge_profile(metrics: PlayerMetrics, profile: dict[str, Any]) -> dict[str, Any]:
    """Junta métricas de evento com os atributos do perfil exportado.

    Cuidado com os duplicados por caixa: a base tem `CPF`/`Cpf`,
    `Email`/`email`, `Name`/`name`, `FirstName`/`First name`,
    `casino_reactivation_cooldown`/`cassino_reactivation_cooldown`. Aqui só
    interessam os que entram no snapshot, e cada um é lido com fallback.
    """

    def attr(*nomes: str) -> Any:
        for n in nomes:
            v = profile.get(n)
            if v not in (None, ""):
                return v
        return None

    return {
        "signup_date": epoch_to_local_date(
            attr("CreatedOn", "created_at", "_created_in_customerio_at")
        ),
        "first_deposit_date": epoch_to_local_date(attr("FirstDepositTimestamp")),
        "player_status": attr("PlayerStatusString"),
        # UTM do perfil só entra se o depósito não trouxe — o do depósito é
        # mais recente e mais confiável.
        "utm_source": metrics.utm_source or attr("UtmSource"),
        "utm_medium": metrics.utm_medium or attr("UtmMedium"),
        "utm_campaign": metrics.utm_campaign or attr("UtmCampaign"),
    }
