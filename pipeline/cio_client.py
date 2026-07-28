"""Cliente HTTP para a API do Customer.io (workspace Aposta1).

ESCOPO: só leitura. Nenhum método aqui escreve, edita ou apaga nada no
Customer.io. O pipeline lê a base e escreve no BigQuery; o caminho de volta
(sincronizar audiências) é uma decisão separada, e deliberadamente não está
implementado aqui.

⚠️ A AUTENTICAÇÃO É A ÚNICA PARTE NÃO VERIFICADA DESTE ARQUIVO.
O endpoint que troca o service account token (`sa_live_…`) por um JWT é
interno do CLI `cio` e não aparece no schema público da API — então ele não
foi inventado aqui. Duas saídas, nesta ordem de preferência:

  1. Exportar um bearer token já trocado:
         export CIO_API_TOKEN="<jwt>"
     É o que `CioClient` usa por padrão.

  2. Deixar o CLI oficial resolver o token, se ele estiver instalado:
         export CIO_USE_CLI=1
     Nesse modo o cliente chama `cio api …` em vez de falar HTTP direto.

Todo o RESTO — paths, params obrigatórios, formato de resposta, paginação —
foi conferido contra o schema da API.
"""

from __future__ import annotations

import json
import logging
import os
import random
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Iterator
from urllib import error, parse, request

log = logging.getLogger(__name__)

# Workspace Aposta1 (account 69932). O outro workspace da conta é o 193631
# (Aviao) — não é este.
DEFAULT_ENVIRONMENT_ID = "112427"
DEFAULT_BASE_URL = "https://eu.fly.customer.io"  # região EU

# Nomes reais dos eventos. Os `id` da API vêm minúsculos; o nome apresentável
# está em `metadata.last_seen_as`. Filtre por `name` usando o id minúsculo.
EVENT_DEPOSIT = "depositsuccessevent"
EVENT_BET = "betevent"
EVENT_CASINO = "casinogamelaunchedevent"

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 4


class CioError(RuntimeError):
    pass


@dataclass
class CioClient:
    environment_id: str = DEFAULT_ENVIRONMENT_ID
    base_url: str = DEFAULT_BASE_URL
    token: str | None = field(default_factory=lambda: os.environ.get("CIO_API_TOKEN"))
    use_cli: bool = field(default_factory=lambda: os.environ.get("CIO_USE_CLI") == "1")
    timeout: int = 60

    def __post_init__(self) -> None:
        if not self.use_cli and not self.token:
            raise CioError(
                "Sem credencial: defina CIO_API_TOKEN com um bearer token, ou "
                "CIO_USE_CLI=1 para delegar ao CLI `cio`. Ver o cabeçalho de "
                "pipeline/cio_client.py."
            )

    # -------------------------------------------------------------------------
    # Transporte
    # -------------------------------------------------------------------------

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: dict[str, Any]) -> dict:
        return self._request("POST", path, body=body)

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict:
        path = path.replace("{environment_id}", self.environment_id)

        if self.use_cli:
            return self._via_cli(method, path, params, body)

        url = f"{self.base_url}{path}"
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            url = f"{url}?{parse.urlencode(clean)}"

        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if data:
            headers["Content-Type"] = "application/json"

        # Backoff exponencial com jitter, honrando Retry-After. O cliente
        # oficial faz o mesmo; sem isso, um 429 no meio de uma varredura de
        # eventos derruba o pipeline inteiro.
        for tentativa in range(MAX_RETRIES + 1):
            req = request.Request(url, data=data, headers=headers, method=method)
            try:
                with request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                    return json.loads(raw) if raw else {}
            except error.HTTPError as e:
                if e.code not in RETRY_STATUSES or tentativa == MAX_RETRIES:
                    raise CioError(
                        f"{method} {path} -> HTTP {e.code}: {e.read()[:400].decode(errors='replace')}"
                    ) from e
                espera = self._backoff(e, tentativa)
                log.warning("HTTP %s em %s, tentando de novo em %.1fs", e.code, path, espera)
                time.sleep(espera)
            except error.URLError as e:
                if tentativa == MAX_RETRIES:
                    raise CioError(f"{method} {path} -> {e.reason}") from e
                time.sleep(self._backoff(None, tentativa))

        raise CioError(f"{method} {path}: retries esgotados")

    @staticmethod
    def _backoff(e: error.HTTPError | None, tentativa: int) -> float:
        if e is not None:
            retry_after = e.headers.get("Retry-After") if e.headers else None
            if retry_after and retry_after.isdigit():
                return float(retry_after)
        return (2 ** tentativa) + random.uniform(0, 1)

    def _via_cli(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None,
        body: dict[str, Any] | None,
    ) -> dict:
        cmd = ["cio", "api", path, "-X", method]
        if params:
            cmd += ["--params", json.dumps({k: v for k, v in params.items() if v is not None})]
        if body is not None:
            cmd += ["--json", json.dumps(body)]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        if out.returncode != 0:
            raise CioError(f"cio api {path} falhou ({out.returncode}): {out.stderr[:400]}")
        return json.loads(out.stdout) if out.stdout.strip() else {}

    # -------------------------------------------------------------------------
    # Eventos — a única fonte com histórico real de R, F e M
    #
    # Não use os atributos de perfil `deposit_value_total` / `active_days_total`:
    # são contadores que as automations 533/540/541 começaram a somar em
    # ~jun/2026, sem backfill. Quem confiar neles vai concluir que a base
    # inteira nasceu em junho.
    # -------------------------------------------------------------------------

    def iter_events(
        self,
        event_name: str,
        since: str,
        until: str,
        page_size: int = 50,
    ) -> Iterator[dict]:
        """Itera eventos do workspace inteiro numa janela.

        `since`/`until` em RFC3339 (`2026-07-01T00:00:00Z`). Pagina por cursor
        `meta.continuation`, não por número de página. O `limit` tem teto de 50
        na API — pedir mais é silenciosamente ignorado.
        """
        continuation: str | None = None
        paginas = 0

        while True:
            resp = self.get(
                "/v1/environments/{environment_id}/logs",
                {
                    "type": "event",
                    "name": event_name,
                    "from": since,
                    "to": until,
                    "limit": min(page_size, 50),
                    "continuation": continuation,
                },
            )
            logs = resp.get("logs") or []
            yield from logs

            paginas += 1
            continuation = (resp.get("meta") or {}).get("continuation")
            if not continuation or not logs:
                log.info("%s: %d páginas lidas", event_name, paginas)
                return

    # -------------------------------------------------------------------------
    # Export de perfis — assíncrono, três passos
    # -------------------------------------------------------------------------

    def start_customer_export(
        self,
        attributes: list[str],
        notify_email: str,
        filters: str = "",
    ) -> int:
        """Enfileira o export da base. Devolve o export_id.

        Os cinco campos do body são TODOS obrigatórios pelo schema, mesmo os
        que não usamos — daí o `filters: ""` (base completa) e o
        `export_relationships: False` explícitos.

        Por que export e não paginar `/customers`: são ~399 mil perfis a 50 por
        página, ou seja ~8 mil requisições. O export resolve numa chamada.
        """
        resp = self.post(
            "/v1/environments/{environment_id}/customers/exports",
            {
                "attributes": attributes,
                "email": notify_email,
                "export_relationships": False,
                "exported_from": "rfm-pipeline",
                "filters": filters,
            },
        )
        export_id = resp.get("export_id")
        if export_id is None:
            raise CioError(f"export sem export_id na resposta: {resp}")
        return int(export_id)

    def wait_for_export(
        self,
        export_id: int,
        poll_seconds: int = 15,
        timeout_seconds: int = 3600,
    ) -> dict:
        """Faz poll até o export terminar. Levanta se falhar ou estourar o tempo."""
        limite = time.time() + timeout_seconds
        while time.time() < limite:
            info = self.get(
                "/v1/environments/{environment_id}/exports/{id}".replace("{id}", str(export_id))
            )
            export = info.get("export", info)
            if export.get("failed"):
                raise CioError(f"export {export_id} falhou: {export}")
            if export.get("done"):
                return export
            log.info("export %s: %s/%s", export_id, export.get("done"), export.get("total"))
            time.sleep(poll_seconds)
        raise CioError(f"export {export_id} não terminou em {timeout_seconds}s")

    def export_download_url(self, export_id: int) -> str:
        """URL assinada (S3) do arquivo pronto.

        O schema registra POST; a documentação oficial cita GET. Se o POST der
        405, troque para GET — não deu para confirmar qual dos dois vale.
        """
        resp = self.post(
            "/v1/environments/{environment_id}/exports/{id}/download".replace(
                "{id}", str(export_id)
            ),
            {},
        )
        url = resp.get("url")
        if not url:
            raise CioError(f"download sem url: {resp}")
        return url

    # -------------------------------------------------------------------------
    # Deliveries — para cruzar campanha com arquétipo
    # -------------------------------------------------------------------------

    def start_deliveries_export(
        self,
        start_ts: int,
        end_ts: int,
        attributes: list[str] | None = None,
    ) -> str:
        """Enfileira o export de deliveries numa janela (epoch em segundos).

        Os TREZE campos do body são obrigatórios pelo schema. Os que não
        filtramos vão como string vazia / zero — omiti-los devolve 400.
        """
        resp = self.post(
            "/v1/environments/{environment_id}/exports/deliveries",
            {
                "action_id": "",
                "attributes": attributes or [],
                "campaign_id": "",
                "delivery_type": "",
                "drafted": False,
                "end_ts": end_ts,
                "exported_from": "rfm-pipeline",
                "metric": "",
                "newsletter_id": "",
                "start_ts": start_ts,
                "template_id": "",
                "transactional_message_id": "",
                "trigger_id": 0,
            },
        )
        export_id = resp.get("export_id")
        if not export_id:
            raise CioError(f"export de deliveries sem export_id: {resp}")
        return str(export_id)

    # -------------------------------------------------------------------------
    # Catálogo
    # -------------------------------------------------------------------------

    def list_attributes(self) -> list[str]:
        """Todos os nomes de atributo de perfil.

        Pagina até vir array vazio — `meta.pagination.total` volta 0 neste
        endpoint (bug conhecido da API), então não dá para usá-lo como parada.
        """
        nomes: list[str] = []
        page = 1
        while True:
            resp = self.get(
                "/v1/environments/{environment_id}/attributes", {"page": page}
            )
            lote = resp.get("attributes") or []
            if not lote:
                return nomes
            nomes += [a.get("name") for a in lote if a.get("name")]
            page += 1
            if page > 50:  # trava contra loop infinito se a API mudar
                log.warning("list_attributes parou em 50 páginas")
                return nomes
