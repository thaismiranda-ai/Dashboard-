# Subir para o BigQuery e montar o layout no Looker

Roteiro para levantar o dashboard **antes** de existir carga real: cria as
tabelas, carrega um seed sintético para os gráficos renderizarem, você monta o
relatório, e depois purga o seed.

Tempo estimado: ~15 min de execução, o resto é montagem no Looker.

---

## 0. Antes de começar

```bash
gcloud auth login
gcloud config set project SEU_PROJETO

export PROJECT_ID="SEU_PROJETO"
export DATASET="crm_rfm"
```

Se o dataset for compartilhado com outras áreas, use um nome próprio
(`crm_rfm_dev`, por exemplo) para o seed sintético não encostar em nada de
produção. É mais fácil apagar um dataset inteiro do que caçar linhas.

---

## 1. Criar tabelas e views

```bash
./sql/deploy.sh --dry-run    # confere o SQL com os nomes já substituídos
./sql/deploy.sh              # aplica
```

Cria, nesta ordem: as três tabelas, as UDFs de classificação e as onze views.

Confira:

```bash
bq ls "${PROJECT_ID}:${DATASET}"
```

Devem aparecer 3 tabelas e 11 views. Se alguma view faltar, o `deploy.sh` para
no primeiro erro — o SQL que falhou é o último que ele imprimiu.

---

## 2. Gerar e carregar o seed

```bash
python3 pipeline/seed_data.py --out /tmp/seed --days 14

bq load --source_format=NEWLINE_DELIMITED_JSON \
  "${PROJECT_ID}:${DATASET}.rfm_snapshots" /tmp/seed/rfm_snapshots.ndjson.gz

bq load --source_format=NEWLINE_DELIMITED_JSON \
  "${PROJECT_ID}:${DATASET}.campaign_touches" /tmp/seed/campaign_touches.ndjson.gz
```

O que o seed tem de verdade e de mentira:

- **Verdade** — os totais diários por arquétipo de 11 a 16/07/2026 batem
  exatamente com as capturas reais. O KPI vai mostrar 149.220, Champions 3.806,
  e por aí. É de propósito: calibrar largura de coluna e formato de número em
  cima de valor aproximado dá retrabalho quando a carga real chega.
- **Mentira** — tudo que é por jogador: valor, produto, plataforma, origem, e
  quem migrou para onde. Esse dado não existe no histórico atual.
- Os 8 dias anteriores a 11/07 são extrapolados da tendência, só para o gráfico
  de evolução ter mais pontos durante a montagem.

Todo `player_id` começa com `SEED-`, então qualquer linha sintética se denuncia
no drill-down.

Confira que carregou:

```bash
bq query --use_legacy_sql=false "
SELECT snapshot_date, archetype, COUNT(*) AS jogadores
FROM \`${PROJECT_ID}.${DATASET}.rfm_snapshots\`
WHERE snapshot_date = '2026-07-16'
GROUP BY 1,2 ORDER BY 3 DESC"
```

Tem que dar Lost 89.285, Hibernating 32.196, At Risk 11.760, Need Attention
10.315, Champions 3.806, Loyal 1.069, Promising 789.

---

## 3. Montar o relatório

Siga `docs/looker-blueprint.md`. Duas coisas específicas de montar com seed:

**Conecte tudo como Live agora, não Extract.** Você vai purgar o seed e
recarregar com dado real; extract congelado no meio disso confunde. Troque para
Extract (nas fontes A–H) depois que a primeira carga real cair.

**A página 5 (drill-down) é o teste do seed.** Se ela mostrar `SEED-000123`,
está tudo conectado certo — e é o lembrete visual de que ainda não é real.

---

## 4. Purgar o seed

Antes de mostrar para qualquer pessoa fora da montagem:

```bash
bq query --use_legacy_sql=false "
DELETE FROM \`${PROJECT_ID}.${DATASET}.rfm_snapshots\`
WHERE STARTS_WITH(player_id, 'SEED-');
DELETE FROM \`${PROJECT_ID}.${DATASET}.campaign_touches\`
WHERE STARTS_WITH(player_id, 'SEED-');"
```

Confirme que zerou:

```bash
bq query --use_legacy_sql=false "
SELECT COUNT(*) AS sobraram
FROM \`${PROJECT_ID}.${DATASET}.rfm_snapshots\`
WHERE STARTS_WITH(player_id, 'SEED-')"
```

> Se um relatório com seed for compartilhado por engano, o estrago não é o
> layout — é alguém tirar conclusão de negócio de número inventado. Purgue
> antes de compartilhar, não depois.

---

## 5. Primeira carga real

```bash
export CIO_API_TOKEN="..."        # ou CIO_USE_CLI=1
export BQ_PROJECT="${PROJECT_ID}"

python3 pipeline/rfm_pipeline.py --date 2026-07-28 --dry-run -v
```

O `--dry-run` não grava nada e imprime a distribuição por arquétipo. É aí que
se descobre se a autenticação funciona — é a única parte do código escrita sem
confirmação no schema da API (está marcada no cabeçalho de
`pipeline/cio_client.py`). Se o token não for aceito, é ali que aparece.

Compare a distribuição impressa com as contagens dos segmentos `[RFM]`
1952–1958 na interface do Customer.io. Diferença acima de ~1% quer dizer que as
definições saíram de sincronia — investigue **antes** de gravar, não depois.

Batendo, tire o `--dry-run`:

```bash
python3 pipeline/rfm_pipeline.py --date 2026-07-28
```

E então agende diariamente, de madrugada. Cada execução lê ~200 dias de eventos
da Logs API a 50 por página, então não é rápida.

> **A primeira execução vai mostrar menos gente do que o esperado.** Sem
> snapshot anterior, só entram jogadores com depósito dentro da janela lida —
> os "Lost" mais antigos não geram evento nenhum e ficam de fora. A partir do
> segundo dia o carry-forward acumula, e a base se completa. É esperado; o
> pipeline avisa em log quando roda sem histórico.

---

## Checklist

- [ ] `bq ls` mostra 3 tabelas e 11 views
- [ ] A consulta de conferência devolve os sete arquétipos com os números certos
- [ ] Fontes conectadas como Live durante a montagem
- [ ] Layout montado seguindo o blueprint
- [ ] Seed purgado e conferido em zero
- [ ] `--dry-run` bate com os segmentos do Customer.io
- [ ] Primeira carga real gravada
- [ ] Execução diária agendada
- [ ] Fontes A–H trocadas para Extract, agendadas **depois** do pipeline
