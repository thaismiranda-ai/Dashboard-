"""Pipeline RFM: Customer.io -> BigQuery.

    python3 pipeline/rfm_pipeline.py --date 2026-07-28
    python3 pipeline/rfm_pipeline.py --date 2026-07-28 --dry-run
    python3 pipeline/rfm_pipeline.py --backfill-from 2026-07-01 --backfill-to 2026-07-28

POR QUE ELE RECONSTRÓI TUDO DOS EVENTOS

O caminho fácil seria ler os atributos `deposit_value_total`,
`deposit_count_total` e `active_days_total` do perfil — eles já existem. Mas
são contadores incrementais criados pelas automations 533/540/541 em ~jun/2026,
sem backfill: quem depositou R$ 50 mil em 2024 aparece com R$ 0 até depositar de
novo. Um dashboard construído em cima disso mostraria uma base que nasceu em
junho.

Então o pipeline lê `DepositSuccessEvent`, `BetEvent` e
`CasinoGameLaunchedEvent` da Logs API e refaz as contas. É mais lento e é a
única forma de os números serem verdade.

CUSTO DE EXECUÇÃO

A Logs API entrega 50 eventos por página com cursor. Uma janela de 90 dias da
base inteira são centenas de milhares de eventos, ou seja milhares de
requisições. Rode uma vez por dia, fora do horário de pico, e prefira
`--backfill-from` para carga inicial.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aggregate import aggregate_events, carry_forward, merge_profile  # noqa: E402
from cio_client import (  # noqa: E402
    EVENT_BET,
    EVENT_CASINO,
    EVENT_DEPOSIT,
    CioClient,
)
from scoring import classify, value_tier  # noqa: E402

log = logging.getLogger("rfm")

# 90 dias é o mínimo: a janela mais longa das métricas é `*_90d`. 200 dá folga
# para a fronteira de "Lost" (>180d) ser calculada em vez de assumida.
LOOKBACK_DAYS = 200

BQ_TABLE = "rfm_snapshots"


def _rfc3339(d: date) -> str:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def build_rows(
    client: CioClient,
    ref_date: date,
    profiles: dict[str, dict] | None = None,
    previous_rows: list[dict] | None = None,
) -> list[dict]:
    """Monta as linhas do snapshot de um dia. Uma linha por jogador depositante.

    `previous_rows` é o snapshot do dia anterior. Sem ele, só entram jogadores
    com depósito dentro da janela lida — o que exclui justamente os "Lost"
    (>180 dias sem depositar), que são a maior fatia da base. Ver
    aggregate.carry_forward.
    """
    inicio = ref_date - timedelta(days=LOOKBACK_DAYS)
    since, until = _rfc3339(inicio), _rfc3339(ref_date + timedelta(days=1))

    log.info("lendo eventos de %s a %s", inicio, ref_date)
    depositos = list(client.iter_events(EVENT_DEPOSIT, since, until))
    apostas = list(client.iter_events(EVENT_BET, since, until))
    cassino = list(client.iter_events(EVENT_CASINO, since, until))
    log.info(
        "eventos lidos: %d depósitos, %d apostas, %d sessões de cassino",
        len(depositos), len(apostas), len(cassino),
    )

    metrics = aggregate_events(depositos, apostas, cassino, ref_date)
    if previous_rows:
        antes = len(metrics)
        metrics = carry_forward(metrics, previous_rows, ref_date)
        log.info(
            "carry-forward: %d jogadores vieram do histórico sem evento na janela",
            len(metrics) - antes,
        )
    profiles = profiles or {}
    agora = datetime.now(timezone.utc)
    linhas: list[dict] = []

    for pid, m in metrics.items():
        dias = m.days_since_last_deposit(ref_date)
        archetype = classify(dias, m.deposits_30d)

        # Sem arquétipo = nunca depositou na janela lida. Fora da base
        # classificada, exatamente como o segmento 1941 define.
        if archetype is None:
            continue

        perfil = merge_profile(m, profiles.get(pid, {}))
        linhas.append(
            {
                "snapshot_date": ref_date.isoformat(),
                "player_id": pid,
                "internal_id": m.internal_id,
                "days_since_last_deposit": dias,
                "last_deposit_at": (
                    m.last_deposit_date.isoformat() + "T00:00:00Z"
                    if m.last_deposit_date else None
                ),
                "deposits_7d": m.deposits_7d,
                "deposits_30d": m.deposits_30d,
                "deposits_90d": m.deposits_90d,
                "deposits_total": m.deposits_total,
                "deposit_value_30d": round(m.deposit_value_30d, 2),
                "deposit_value_90d": round(m.deposit_value_90d, 2),
                "deposit_value_total": round(m.deposit_value_total, 2),
                "days_since_last_activity": m.days_since_last_activity(ref_date),
                "last_activity_at": (
                    m.last_activity_date.isoformat() + "T00:00:00Z"
                    if m.last_activity_date else None
                ),
                "active_days_30d": len(m.active_dates_30d),
                "sports_bets_90d": m.sports_bets_90d,
                "sports_stake_90d": round(m.sports_stake_90d, 2),
                "sports_winnings_90d": round(m.sports_winnings_90d, 2),
                "sports_ggr_90d": round(m.sports_ggr_90d, 2),
                "casino_sessions_90d": m.casino_sessions_90d,
                "archetype": archetype,
                "value_tier": value_tier(m.deposit_value_90d),
                "signup_date": (
                    perfil["signup_date"].isoformat() if perfil["signup_date"] else None
                ),
                "first_deposit_date": (
                    perfil["first_deposit_date"].isoformat()
                    if perfil["first_deposit_date"] else None
                ),
                "product_pref": m.product_pref,
                "platform": m.platform,
                "device_os": m.device_os,
                "utm_source": perfil["utm_source"],
                "utm_medium": perfil["utm_medium"],
                "utm_campaign": perfil["utm_campaign"],
                "player_status": perfil["player_status"],
                "ingested_at": agora.isoformat(),
            }
        )

    return linhas


def read_previous_snapshot(project: str, dataset: str, ref_date: date) -> list[dict]:
    """Lê o snapshot mais recente ANTERIOR ao dia pedido.

    Não é necessariamente o dia -1: se o pipeline falhou ontem, o histórico
    mais novo é de anteontem, e usá-lo é melhor do que perder os jogadores sem
    evento na janela. Buscar o "último anterior" em vez de "ontem" faz o
    pipeline se recuperar sozinho de um dia perdido.
    """
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    table_id = f"{project}.{dataset}.{BQ_TABLE}"
    query = f"""
        SELECT player_id, internal_id, snapshot_date, last_deposit_at,
               deposits_total, deposit_value_total,
               platform, device_os, utm_source, utm_medium, utm_campaign
        FROM `{table_id}`
        WHERE snapshot_date = (
          SELECT MAX(snapshot_date) FROM `{table_id}` WHERE snapshot_date < @d
        )
    """
    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("d", "DATE", ref_date.isoformat())
            ]
        ),
    )
    linhas = [
        {
            "player_id": r["player_id"],
            "internal_id": r["internal_id"],
            "snapshot_date": r["snapshot_date"],
            "last_deposit_date": r["last_deposit_at"],
            "deposits_total": r["deposits_total"],
            "deposit_value_total": r["deposit_value_total"],
            "platform": r["platform"],
            "device_os": r["device_os"],
            "utm_source": r["utm_source"],
            "utm_medium": r["utm_medium"],
            "utm_campaign": r["utm_campaign"],
        }
        for r in job
    ]
    if linhas:
        log.info("snapshot anterior: %d jogadores de %s", len(linhas), linhas[0]["snapshot_date"])
    else:
        log.warning(
            "sem snapshot anterior — só entram jogadores com depósito nos "
            "últimos %d dias. Os 'Lost' mais antigos vão faltar até a base "
            "acumular histórico.", LOOKBACK_DAYS,
        )
    return linhas


def write_to_bigquery(
    rows: list[dict], project: str, dataset: str, ref_date: date
) -> None:
    """Grava a partição do dia, substituindo o que já estiver lá.

    DELETE + insert (e não append) para que reprocessar um dia não duplique
    jogadores. Como as janelas são calculadas a partir de `ref_date` e eventos
    futuros são ignorados, rodar o mesmo dia duas vezes dá o mesmo resultado.
    """
    from google.cloud import bigquery  # import tardio: só quem grava precisa

    client = bigquery.Client(project=project)
    table_id = f"{project}.{dataset}.{BQ_TABLE}"

    client.query(
        f"DELETE FROM `{table_id}` WHERE snapshot_date = @d",
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("d", "DATE", ref_date.isoformat())
            ]
        ),
    ).result()

    erros = client.insert_rows_json(table_id, rows)
    if erros:
        raise RuntimeError(f"BigQuery recusou linhas: {erros[:3]}")
    log.info("%d linhas gravadas em %s", len(rows), table_id)


def log_run(
    project: str, dataset: str, run_id: str, ref_date: date,
    started: datetime, status: str, players: int, error: str | None,
) -> None:
    from google.cloud import bigquery

    bigquery.Client(project=project).insert_rows_json(
        f"{project}.{dataset}.pipeline_runs",
        [{
            "run_id": run_id,
            "snapshot_date": ref_date.isoformat(),
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "players_written": players,
            "error_message": error,
        }],
    )


def run_one_day(args, ref_date: date) -> int:
    run_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc)
    client = CioClient(environment_id=args.environment_id)

    try:
        anterior = (
            None if args.dry_run
            else read_previous_snapshot(args.project, args.dataset, ref_date)
        )
        rows = build_rows(client, ref_date, previous_rows=anterior)
    except Exception as e:  # noqa: BLE001
        if not args.dry_run:
            log_run(args.project, args.dataset, run_id, ref_date, started, "failed", 0, str(e))
        raise

    distribuicao: dict[str, int] = {}
    for r in rows:
        distribuicao[r["archetype"]] = distribuicao.get(r["archetype"], 0) + 1
    log.info("%s: %d jogadores classificados", ref_date, len(rows))
    for nome in ("Champions", "Loyal", "Promising", "Need Attention",
                 "At Risk", "Hibernating", "Lost"):
        n = distribuicao.get(nome, 0)
        pct = (n / len(rows) * 100) if rows else 0
        log.info("   %-16s %7d  %5.1f%%", nome, n, pct)

    if args.dry_run:
        log.info("dry-run: nada foi gravado")
        return len(rows)

    write_to_bigquery(rows, args.project, args.dataset, ref_date)
    log_run(args.project, args.dataset, run_id, ref_date, started, "success", len(rows), None)
    return len(rows)


def main() -> int:
    p = argparse.ArgumentParser(description="Snapshot diário de RFM no BigQuery")
    p.add_argument("--date", help="Dia do snapshot (YYYY-MM-DD). Padrão: ontem.")
    p.add_argument("--backfill-from", help="Início do backfill (YYYY-MM-DD)")
    p.add_argument("--backfill-to", help="Fim do backfill (YYYY-MM-DD)")
    p.add_argument("--project", default=os.environ.get("BQ_PROJECT"))
    p.add_argument("--dataset", default=os.environ.get("BQ_DATASET", "crm_rfm"))
    p.add_argument("--environment-id", default=os.environ.get("CIO_ENVIRONMENT_ID", "112427"))
    p.add_argument("--dry-run", action="store_true", help="Só calcula e imprime")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
    )

    if not args.dry_run and not args.project:
        p.error("--project (ou BQ_PROJECT) é obrigatório fora do dry-run")

    if args.backfill_from:
        inicio = date.fromisoformat(args.backfill_from)
        fim = date.fromisoformat(args.backfill_to or args.backfill_from)
        dias = [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]
    else:
        alvo = (
            date.fromisoformat(args.date)
            if args.date
            else date.today() - timedelta(days=1)
        )
        dias = [alvo]

    total = 0
    for d in dias:
        total += run_one_day(args, d)
    log.info("pronto: %d dia(s), %d linhas", len(dias), total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
