"""Gera dados sintéticos para montar o layout no Looker Studio antes da carga real.

    python3 pipeline/seed_data.py --out /tmp/seed --days 14
    python3 pipeline/seed_data.py --out /tmp/seed --days 14 --scale 0.02   # amostra rápida

Produz dois NDJSON gzipados prontos para `bq load` na tabela que o
`sql/00_schema.sql` já criou.

POR QUE SEED E NÃO TABELA VAZIA

Gráfico sem dados esconde exatamente o que a montagem precisa decidir: se o
arquétipo está ordenado pela rampa ou pelo alfabeto, se a porcentagem tem uma
casa ou três, se o rótulo cabe na coluna, se a matriz de migração fica legível.
Nada disso aparece num painel escrito "sem dados" — você monta tudo, roda o
pipeline, e refaz metade.

O QUE É VERDADE E O QUE É INVENTADO

Verdade: os totais diários por arquétipo de 11 a 16/07/2026 batem EXATAMENTE
com as capturas reais. Se batessem só por aproximação, você calibraria largura
de coluna e formato de número em cima de valores que mudam na primeira carga.

Inventado: tudo que é por jogador — valor depositado, produto, plataforma,
origem, e quem migrou para onde. Esse dado não existe no histórico atual, é o
que o pipeline vai construir.

TODO player_id começa com `SEED-`. É o que torna a purga trivial e o que faz
qualquer linha sintética se denunciar no drill-down:

    DELETE FROM `PROJETO.DATASET.rfm_snapshots`   WHERE STARTS_WITH(player_id, 'SEED-');
    DELETE FROM `PROJETO.DATASET.campaign_touches` WHERE STARTS_WITH(player_id, 'SEED-');
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scoring import ARCHETYPE_RANK, ARCHETYPES, value_tier  # noqa: E402

SEED_PREFIX = "SEED-"

# --- capturas reais do pipeline, 11 a 16/07/2026 (as mesmas do dashboard) ---
REAL_START = date(2026, 7, 11)
REAL_SERIES: dict[str, list[int]] = {
    "Champions":      [3727, 3771, 3794, 3773, 3782, 3806],
    "Loyal":          [1191, 1170, 1146, 1110, 1072, 1069],
    "Promising":      [892, 884, 848, 839, 818, 789],
    "Need Attention": [9261, 9281, 9576, 9864, 10133, 10315],
    "At Risk":        [12879, 12863, 12600, 12357, 12027, 11760],
    "Hibernating":    [32212, 32214, 32211, 32193, 32194, 32196],
    "Lost":           [88512, 88548, 88715, 88884, 89119, 89285],
}

# Faixas de recência que definem cada arquétipo (ver scoring.py). O gerador
# sorteia dentro da faixa para que `days_since_last_deposit` seja coerente com
# o rótulo — senão a UDF de auditoria acusaria divergência em cima do seed.
RECENCY_BANDS: dict[str, tuple[int, int]] = {
    "Champions":      (0, 7),
    "Loyal":          (0, 7),
    "Promising":      (0, 7),
    "Need Attention": (8, 30),
    "At Risk":        (31, 90),
    "Hibernating":    (91, 180),
    "Lost":           (181, 900),
}
DEPOSIT_BANDS: dict[str, tuple[int, int]] = {
    "Champions":      (4, 14),
    "Loyal":          (2, 3),
    "Promising":      (1, 1),
    "Need Attention": (0, 2),
    "At Risk":        (0, 1),
    "Hibernating":    (0, 0),
    "Lost":           (0, 0),
}
# Valor típico depositado em 90 dias, por arquétipo (média lognormal).
VALUE_SCALE: dict[str, float] = {
    "Champions": 2600, "Loyal": 900, "Promising": 220,
    "Need Attention": 400, "At Risk": 300, "Hibernating": 60, "Lost": 20,
}

PRODUCTS = [("cassino", .52), ("esportes", .26), ("ambos", .17), ("nenhum", .05)]
PLATFORMS = [("mobile_app", .63), ("web", .37)]
DEVICES = [("android", .58), ("ios", .29), ("unknown", .13)]
UTM_SOURCES = [("google", .28), ("meta", .24), ("direto", .21),
               ("afiliados", .18), ("tiktok", .09)]
STATUSES = [("Active", .93), ("RequiresKyc", .05), ("Blocked", .02)]

# Campanhas reais do workspace 112427 (ids e nomes conferidos na API).
CAMPAIGNS = [
    ("492", "[HIG] Cassino — Sunset 120d — Ultima Chance", "email", "Hibernating"),
    ("522", "[MK] Payday — Classificador pay_day", "email", "Need Attention"),
    ("502", "[MKT] Flow 1 - Reativação Esportes", "push", "At Risk"),
    ("516", "[MK] Abandono de Jogo - Cassino", "push", "Need Attention"),
    ("508", "[MK] Welcome — KYC + Bonus", "email", "Promising"),
]


def br(n: int) -> str:
    """Milhar com ponto, como se escreve em português."""
    return f"{n:,}".replace(",", ".")


def pick(rng: random.Random, options: list[tuple[str, float]]) -> str:
    r = rng.random()
    acc = 0.0
    for nome, peso in options:
        acc += peso
        if r <= acc:
            return nome
    return options[-1][0]


def build_targets(days: int) -> list[tuple[date, dict[str, int]]]:
    """Alvo de contagem por arquétipo em cada dia.

    Os 6 dias reais entram como estão. Os dias anteriores são extrapolados para
    trás mantendo a tendência de cada arquétipo — serve para o gráfico de
    evolução ter mais que 6 pontos durante a montagem, e some na primeira carga
    de verdade.
    """
    reais = len(REAL_SERIES["Champions"])
    extras = max(0, days - reais)
    saida: list[tuple[date, dict[str, int]]] = []

    for i in range(extras, 0, -1):
        dia = REAL_START - timedelta(days=i)
        alvo = {}
        for nome, serie in REAL_SERIES.items():
            # inclinação média dos dias reais, projetada para trás
            passo = (serie[-1] - serie[0]) / (reais - 1)
            alvo[nome] = max(1, int(round(serie[0] - passo * i)))
        saida.append((dia, alvo))

    for j in range(reais):
        dia = REAL_START + timedelta(days=j)
        saida.append((dia, {nome: serie[j] for nome, serie in REAL_SERIES.items()}))

    return saida


def initial_assignment(alvo: dict[str, int]) -> list[str]:
    """Vetor de arquétipo por índice de jogador, no primeiro dia."""
    estado: list[str] = []
    for nome in ARCHETYPES:
        estado.extend([nome] * alvo[nome])
    return estado


def evolve(
    estado: list[str],
    alvo: dict[str, int],
    rng: random.Random,
    churn_ratio: float = 0.012,
) -> list[str]:
    """Move jogadores entre arquétipos até bater o alvo do dia.

    Duas camadas, e a segunda é o que faz a matriz de migração valer alguma
    coisa:

      1. Ajuste líquido — quem está sobrando sai para quem está faltando.
      2. Ruído de fundo — uma fração troca de arquétipo com o vizinho mesmo
         quando o alvo já foi atingido, em pares que se cancelam.

    Sem a camada 2, a matriz de migração só teria massa fora da diagonal onde
    houve variação líquida, e a página inteira mostraria quase nada — que é
    justamente o oposto da realidade, onde muita gente se cruza sem que os
    totais mudem.
    """
    novo = list(estado)
    atual: dict[str, list[int]] = {nome: [] for nome in ARCHETYPES}
    for idx, nome in enumerate(novo):
        atual[nome].append(idx)

    # --- 1. ajuste líquido, preferindo o vizinho mais próximo na escala ---
    sobra = {n: len(atual[n]) - alvo.get(n, 0) for n in ARCHETYPES}
    doadores = [n for n in ARCHETYPES if sobra[n] > 0]
    receptores = [n for n in ARCHETYPES if sobra[n] < 0]

    for destino in receptores:
        faltam = -sobra[destino]
        # vizinhos primeiro: migração de Champions direto para Lost é rara
        ordem = sorted(
            doadores,
            key=lambda d: abs(ARCHETYPE_RANK[d] - ARCHETYPE_RANK[destino]),
        )
        for origem in ordem:
            if faltam <= 0:
                break
            disponiveis = min(faltam, sobra[origem])
            if disponiveis <= 0:
                continue
            rng.shuffle(atual[origem])
            movidos = [atual[origem].pop() for _ in range(disponiveis)]
            for idx in movidos:
                novo[idx] = destino
            sobra[origem] -= disponiveis
            faltam -= disponiveis

    # --- 2. ruído de fundo em pares que se cancelam ---
    for i, origem in enumerate(ARCHETYPES[:-1]):
        destino = ARCHETYPES[i + 1]
        pool_a = [k for k, v in enumerate(novo) if v == origem]
        pool_b = [k for k, v in enumerate(novo) if v == destino]
        n = int(min(len(pool_a), len(pool_b)) * churn_ratio)
        if n <= 0:
            continue
        for idx in rng.sample(pool_a, n):
            novo[idx] = destino
        for idx in rng.sample(pool_b, n):
            novo[idx] = origem

    return novo


def player_profile(pid: int, rng: random.Random) -> dict:
    """Atributos estáveis do jogador — não mudam de um dia para o outro."""
    signup = date(2024, 1, 1) + timedelta(days=rng.randint(0, 900))
    tem_ftd = rng.random() < 0.97
    return {
        "player_id": f"{SEED_PREFIX}{pid:06d}",
        "internal_id": f"{SEED_PREFIX}cio{pid:06d}",
        "signup_date": signup.isoformat(),
        "first_deposit_date": (
            (signup + timedelta(days=rng.randint(0, 30))).isoformat() if tem_ftd else None
        ),
        "product_pref": pick(rng, PRODUCTS),
        "platform": pick(rng, PLATFORMS),
        "device_os": pick(rng, DEVICES),
        "utm_source": pick(rng, UTM_SOURCES),
        "utm_medium": rng.choice(["cpc", "organic", "referral", "email"]),
        "utm_campaign": rng.choice(["always_on", "payday", "reativacao", "aquisicao_q3"]),
        "player_status": pick(rng, STATUSES),
        # Semente própria para o valor: mantém o jogador "rico" ou "magro"
        # coerente ao longo dos dias, em vez de sortear valor novo todo dia.
        "wealth": rng.lognormvariate(0, 0.9),
    }


def snapshot_row(perfil: dict, archetype: str, dia: date, rng: random.Random) -> dict:
    lo, hi = RECENCY_BANDS[archetype]
    recencia = rng.randint(lo, hi)
    dlo, dhi = DEPOSIT_BANDS[archetype]
    dep_30 = rng.randint(dlo, dhi)
    dep_7 = min(dep_30, rng.randint(1, max(1, dep_30))) if recencia <= 7 else 0

    valor_90 = round(VALUE_SCALE[archetype] * perfil["wealth"] * rng.uniform(0.5, 1.6), 2)
    valor_30 = round(valor_90 * rng.uniform(0.2, 0.7), 2)
    valor_total = round(valor_90 * rng.uniform(1.5, 9.0), 2)
    dep_90 = max(dep_30, dep_30 + rng.randint(0, 4))
    dep_total = dep_90 + rng.randint(0, 40)

    # Atividade de jogo é independente de depósito: parte de quem está frio no
    # depósito continua abrindo o app. É o sinal que o drill-down usa.
    if rng.random() < 0.22:
        atividade = rng.randint(0, min(7, recencia)) if recencia > 0 else 0
    else:
        atividade = recencia + rng.randint(0, 10)

    produto = perfil["product_pref"]
    tem_esporte = produto in ("esportes", "ambos")
    tem_cassino = produto in ("cassino", "ambos")

    apostas = rng.randint(3, 220) if tem_esporte and recencia < 120 else 0
    stake = round(apostas * rng.uniform(8, 60), 2)
    # Margem da casa em torno de 6%, com dias em que o jogador ganha.
    ganhos = round(stake * rng.uniform(0.80, 1.05), 2)

    return {
        "snapshot_date": dia.isoformat(),
        "player_id": perfil["player_id"],
        "internal_id": perfil["internal_id"],
        "days_since_last_deposit": recencia,
        "last_deposit_at": (dia - timedelta(days=recencia)).isoformat() + "T14:00:00Z",
        "deposits_7d": dep_7,
        "deposits_30d": dep_30,
        "deposits_90d": dep_90,
        "deposits_total": dep_total,
        "deposit_value_30d": valor_30,
        "deposit_value_90d": valor_90,
        "deposit_value_total": valor_total,
        "days_since_last_activity": atividade,
        "last_activity_at": (dia - timedelta(days=atividade)).isoformat() + "T20:00:00Z",
        "active_days_30d": max(0, rng.randint(0, 28) if atividade < 30 else 0),
        "sports_bets_90d": apostas,
        "sports_stake_90d": stake,
        "sports_winnings_90d": ganhos,
        "sports_ggr_90d": round(stake - ganhos, 2),
        "casino_sessions_90d": rng.randint(2, 400) if tem_cassino and recencia < 120 else 0,
        "archetype": archetype,
        "value_tier": value_tier(valor_90),
        "signup_date": perfil["signup_date"],
        "first_deposit_date": perfil["first_deposit_date"],
        "product_pref": produto,
        "platform": perfil["platform"],
        "device_os": perfil["device_os"],
        "utm_source": perfil["utm_source"],
        "utm_medium": perfil["utm_medium"],
        "utm_campaign": perfil["utm_campaign"],
        "player_status": perfil["player_status"],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Seed sintético para montar o layout")
    p.add_argument("--out", required=True, help="Diretório de saída")
    p.add_argument("--days", type=int, default=14, help="Dias de histórico (padrão 14)")
    p.add_argument("--scale", type=float, default=1.0,
                   help="Fração da base. 1.0 = 149 mil jogadores; 0.02 para teste rápido")
    p.add_argument("--seed", type=int, default=42, help="Semente do gerador")
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(args.seed)

    alvos = build_targets(args.days)
    if args.scale != 1.0:
        alvos = [
            (dia, {n: max(1, int(v * args.scale)) for n, v in alvo.items()})
            for dia, alvo in alvos
        ]

    # Pool dimensionado pelo maior dia — a base cresce ao longo do período.
    maximo = max(sum(alvo.values()) for _, alvo in alvos)
    print(f"gerando {len(alvos)} dias, até {br(maximo)} jogadores/dia")

    perfis = [player_profile(i, rng) for i in range(maximo)]
    estado = initial_assignment(alvos[0][1])

    caminho_snap = os.path.join(args.out, "rfm_snapshots.ndjson.gz")
    caminho_touch = os.path.join(args.out, "campaign_touches.ndjson.gz")
    total_linhas = 0
    total_toques = 0

    with gzip.open(caminho_snap, "wt") as fs, gzip.open(caminho_touch, "wt") as ft:
        for n, (dia, alvo) in enumerate(alvos):
            if n > 0:
                # A base cresce: novos jogadores entram como Promising, que é o
                # que "primeiro depósito nesta semana" significa.
                faltam = sum(alvo.values()) - len(estado)
                if faltam > 0:
                    estado.extend(["Promising"] * faltam)
                estado = evolve(estado, alvo, rng)

            contagem: dict[str, int] = {}
            for idx, archetype in enumerate(estado):
                fs.write(json.dumps(snapshot_row(perfis[idx], archetype, dia, rng)) + "\n")
                contagem[archetype] = contagem.get(archetype, 0) + 1
                total_linhas += 1

            # Toques de campanha: cada régua atinge uma fatia do seu alvo.
            for cid, nome, canal, alvo_arch in CAMPAIGNS:
                elegiveis = [i for i, a in enumerate(estado) if a == alvo_arch]
                if not elegiveis:
                    continue
                n_toques = int(len(elegiveis) * rng.uniform(0.05, 0.18))
                for idx in rng.sample(elegiveis, min(n_toques, len(elegiveis))):
                    entregue = rng.random() < 0.94
                    aberto = entregue and rng.random() < 0.31
                    clicado = aberto and rng.random() < 0.19
                    ft.write(json.dumps({
                        "touch_date": dia.isoformat(),
                        "player_id": perfis[idx]["player_id"],
                        "campaign_id": cid,
                        "campaign_name": nome,
                        "channel": canal,
                        "delivered": entregue,
                        "opened": aberto,
                        "clicked": clicado,
                        "converted": clicado and rng.random() < 0.14,
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                    }) + "\n")
                    total_toques += 1

            # Confere que o dia bate com o alvo. Se não bater, o KPI do
            # dashboard mostra número que não é o real e a montagem calibra
            # formatação em cima de valor errado.
            for nome_arch, esperado in alvo.items():
                obtido = contagem.get(nome_arch, 0)
                assert obtido == esperado, (
                    f"{dia} {nome_arch}: gerou {obtido}, alvo {esperado}"
                )

    mb_snap = os.path.getsize(caminho_snap) / 1e6
    mb_touch = os.path.getsize(caminho_touch) / 1e6
    print(f"\n{br(total_linhas)} snapshots  -> {caminho_snap}  ({mb_snap:.1f} MB gz)")
    print(f"{br(total_toques)} toques      -> {caminho_touch}  ({mb_touch:.1f} MB gz)")
    print("\ntodos os dias bateram com os alvos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
