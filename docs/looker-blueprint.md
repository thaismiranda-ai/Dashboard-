# Blueprint do relatório — RFM Health no Looker Studio

Guia de montagem do relatório. Cada página lista a fonte de dados, os gráficos,
os campos e as armadilhas específicas daquele gráfico.

Nenhuma API pública do Looker Studio edita relatórios, então isto é um roteiro
de montagem manual — mas é um roteiro fechado: todo campo calculado está pronto
para colar, e toda cor já saiu validada.

---

## 1. Fontes de dados

Crie uma fonte BigQuery por view. **Não use uma fonte só com a tabela crua** —
as views é que carregam as definições de "base saudável" e a ordenação dos
arquétipos, e é o que impede duas páginas de discordarem.

| # | Fonte (view) | Alimenta | Modo |
|---|---|---|---|
| A | `vw_base_health_daily` | KPI herói, meta de 45% | Extract |
| B | `vw_archetype_trend` | Evolução, cartões de variação | Extract |
| C | `vw_archetype_daily` | Composição filtrável | Extract |
| D | `vw_migration_matrix` | Matriz de migração | Extract |
| E | `vw_migration_net_flow` | Fluxo líquido | Extract |
| F | `vw_value_by_archetype` | Valor e LTV | Extract |
| G | `vw_cohort_by_archetype` | Coortes | Extract |
| H | `vw_campaign_effect` | Efeito de campanha | Extract |
| I | `vw_player_drilldown` | Tabela de jogadores | **Live** |

**Extract vs Live.** Extract materializa um snapshot no Looker e atualiza no
horário que você marcar: rápido e com custo de BigQuery previsível. Deixe em
Live só o drill-down (I), que precisa refletir o snapshot do dia e é consultado
com filtro apertado. Se A–H ficarem em Live, cada pessoa que abrir o relatório
dispara varredura na tabela particionada, e a conta do BigQuery vira função do
número de curiosos.

Agende os extracts para **depois** do pipeline. Um extract às 6h com pipeline às
7h mostra o dia anterior o dia inteiro — e sem carimbo de atualização ninguém
percebe.

---

## 2. Paleta

Os sete arquétipos **não são categorias, são uma escala ordenada** de saúde.
Sete matizes diferentes (verde, azul, roxo, âmbar…) gastam o canal de cor com
identidade e não mostram a ordem: o leitor não consegue dizer se roxo é melhor
ou pior que âmbar sem consultar a legenda.

Por isso a paleta é uma **rampa de um matiz só**, do mais claro (mais saudável,
mais destaque sobre o fundo escuro) ao mais escuro (mais frio, recuando para o
fundo). A ordem vira visível sem legenda.

### Arquétipos — superfície escura (`#1A1F2E`)

| Arquétipo | Hex | Contraste |
|---|---|---|
| Champions | `#cde2fb` | 12,40:1 |
| Loyal | `#9ec5f4` | 9,18:1 |
| Promising | `#6da7ec` | 6,56:1 |
| Need Attention | `#3987e5` | 4,51:1 |
| At Risk | `#256abf` | 3,04:1 |
| Hibernating | `#184f95` | 2,03:1 |
| **Lost** | `#4a4f5a` | 2,00:1 |

Validado com o script de paleta em modo `--ordinal`: luminosidade monótona,
salto adjacente ≥ 0,06 e ponta mais próxima da superfície acima de 2:1.

**Lost é cinza, fora da rampa, de propósito.** Ele é ~60% da base e ia dominar
visualmente todo gráfico de composição. Cinza neutro diz "massa de fundo" em
vez de "mais um degrau", e o contraste ligeiramente menor que Hibernating
mantém a recessão monótona: quanto pior o arquétipo, menos ele grita.

> Sete degraus não cabem na rampa nesta superfície — o máximo que passa em
> todos os testes é seis. Foi por isso que Lost saiu para o cinza, e não por
> gosto. Se um dia a superfície do relatório clarear, refaça a conta.

### Variação (canal separado)

Identidade e polaridade são coisas diferentes e não podem dividir o mesmo
canal. As setas e os números de variação usam a escala de status:

| Papel | Hex |
|---|---|
| Movimento bom | `#0ca30c` |
| Atenção | `#fab219` |
| Ruim | `#d03b3b` |

Sempre com seta **e** rótulo — nunca só a cor.

### Chrome

| Papel | Hex |
|---|---|
| Fundo da página | `#0F1218` |
| Superfície do cartão | `#1A1F2E` |
| Texto primário | `#F0F3F6` |
| Texto secundário | `#8B96A5` |
| Linha de grade | `#2c2c2a` |

---

## 3. Campos calculados

Cole na fonte de dados indicada. A sintaxe é a do Looker Studio.

### Fonte B (`vw_archetype_trend`)

**`Variação 7d orientada`** — o campo que resolve o pior bug do dashboard
atual, que pinta "Lost +0,9%" de verde porque o número subiu.

```
signed_move_7d
```

Já vem pronto da view (`delta_pct_7d * growth_polarity`). Positivo é sempre bom.

**`Cor da variação`** — para o formatting condicional dos cartões:

```
CASE
  WHEN signed_move_7d >  0.02 THEN "Bom"
  WHEN signed_move_7d < -0.02 THEN "Ruim"
  ELSE "Estável"
END
```

A banda morta de ±2% evita que ruído diário de meio ponto vire alarme.

**`Rótulo de variação`**:

```
CONCAT(
  CASE WHEN delta_pct_7d >= 0 THEN "▲ " ELSE "▼ " END,
  CAST(ROUND(ABS(delta_pct_7d) * 100, 1) AS TEXT), "%"
)
```

### Fonte A (`vw_base_health_daily`)

**`Distância da meta (p.p.)`**:

```
ROUND((healthy_share - healthy_target) * 100, 1)
```

**`Concentração de valor`** — o contexto que impede ler "3,8% saudável" como
catástrofe:

```
CONCAT(
  CAST(ROUND(healthy_share * 100, 1) AS TEXT), "% da base · ",
  CAST(ROUND(ltv_share_healthy * 100, 0) AS TEXT), "% do valor"
)
```

### Fonte F (`vw_value_by_archetype`)

**`Índice de valor`** já vem como `value_index`. Formate como número com 1
decimal e trate assim na leitura: `1,0` = o segmento pesa no bolso o mesmo que
pesa em cabeças; `4,0` = pesa quatro vezes mais.

**`Média vs mediana`** — sinal de que poucas baleias carregam o segmento:

```
CASE
  WHEN ltv_mean_to_median >= 3 THEN "Concentrado em poucos"
  WHEN ltv_mean_to_median >= 1.5 THEN "Moderado"
  ELSE "Distribuído"
END
```

### Fonte I (`vw_player_drilldown`)

**`Jogando sem depositar`** — o campo mais acionável do relatório. A
classificação só olha depósito, então esta pessoa está marcada como fria mesmo
tendo aberto o app ontem:

```
CASE
  WHEN active_but_not_depositing AND days_since_last_activity <= 7
    THEN "Sim — ativo há 7d"
  WHEN active_but_not_depositing THEN "Sim"
  ELSE "Não"
END
```

---

## 4. Páginas

### Página 1 — Saúde da base

Para quem abre o relatório e tem 30 segundos.

| Bloco | Gráfico | Fonte | Dimensões / Métricas |
|---|---|---|---|
| Topo | Scorecard | A | `healthy_share` (%), comparação com período anterior |
| Topo | Scorecard | A | `base_players` |
| Topo | Scorecard | A | `Distância da meta (p.p.)` |
| Faixa | Barra 100% empilhada | C | Dim: `archetype` · Métrica: `players` · Ordenar por `archetype_rank` |
| Meio | Série temporal | A | Dim: `snapshot_date` · Métricas: `healthy_share`, `healthy_target` |
| Base | 4 scorecards | B | `players` + `Rótulo de variação`, um por arquétipo em foco |

**Ordenação.** Em todo gráfico com `archetype`, ordene por `archetype_rank`
crescente. O padrão do Looker é alfabético, que coloca "At Risk" antes de
"Champions" e embaralha a rampa de cor — o gráfico fica bonito e ilegível.

**A linha da meta** é uma segunda métrica constante (`healthy_target`), não uma
linha de referência do menu. Linha de referência não aparece na legenda nem no
tooltip; como métrica, ela aparece nos dois.

**Nunca dois eixos Y.** Se quiser mostrar % saudável e nº de jogadores na mesma
tendência, faça dois gráficos. Eixo duplo permite provar qualquer correlação só
escolhendo as escalas.

### Página 2 — Para onde as pessoas vão

A página que o dashboard atual não tem.

| Bloco | Gráfico | Fonte | Configuração |
|---|---|---|---|
| Topo | Controle | D | Lista suspensa de `lag_days`, **padrão 7** |
| Esquerda | Tabela dinâmica com mapa de calor | D | Linha: `archetype_from` · Coluna: `archetype_to` · Métrica: `players` |
| Direita | Barras horizontais | E | Dim: `archetype` · Métrica: `net_players` |
| Base | Barras empilhadas | E | Dim: `counterpart_archetype` · Métricas: `players_in`, `players_out` |
| Rodapé | Scorecards | — | `players_entered`, `players_left` (view `vw_base_churn_flow`) |

**`lag_days` precisa de filtro obrigatório.** A view traz 1, 7 e 28 dias
empilhados. Sem o filtro, o Looker soma os três e a matriz mostra ~3x o número
real, sem nenhum aviso. Se o controle permitir "todos", trave-o.

**A diagonal domina o mapa de calor.** A maioria fica no mesmo arquétipo, então
a célula "Lost → Lost" sozinha achata a escala de cor e todo o resto vira uma
cor só. Adicione um filtro `archetype_from != archetype_to` no gráfico da
matriz: o interesse está fora da diagonal.

Para o mapa de calor use uma rampa **sequencial de um matiz** (o mesmo azul),
não a paleta dos arquétipos — aqui a cor codifica magnitude, não identidade.

**Entradas e saídas ficam separadas** porque não são migração. Somar as duas
coisas no mesmo gráfico faz os números pararem de fechar e ninguém descobre por
quê.

### Página 3 — Quanto vale cada arquétipo

| Bloco | Gráfico | Fonte | Configuração |
|---|---|---|---|
| Topo | Barras pareadas | F | Dim: `archetype` · Métricas: `share_of_players`, `share_of_ggr` |
| Topo | Barras | F | Dim: `archetype` · Métrica: `value_index`, linha de referência em 1,0 |
| Meio | Tabela | F | `players`, `ltv_per_player`, `value_median`, `Média vs mediana` |
| Meio | Série temporal | F | Dim: `snapshot_date` · Métrica: `deposit_value_total` por arquétipo |
| Base | Mapa de calor | G | Linha: `cohort_month` · Coluna: `archetype` · Métrica: `players` |

**Mostre média e mediana lado a lado, sempre.** Em base de apostas, o LTV médio
de Champions é puxado por um punhado de jogadores. Média sozinha vira meta que
ninguém bate; mediana sozinha esconde a concentração que sustenta a receita.

**Rotule GGR como "GGR esportes".** É o que ele é: `TotalStake -
TotalWinnings` do `BetEvent`. Cassino não expõe valor nenhum na API, então quem
lê "GGR" sem qualificação vai supor que inclui cassino e comparar com um número
do backoffice que não bate. Deixe uma nota fixa no gráfico.

### Página 4 — Efeito de campanha

| Bloco | Gráfico | Fonte | Configuração |
|---|---|---|---|
| Topo | Aviso fixo | — | Ver abaixo — texto obrigatório |
| Topo | Controles | H | `window_days` (padrão 7) e `has_min_sample = true` |
| Meio | Barras pareadas | H | Dim: `campaign_name` · Métricas: `recovery_rate`, `recovery_rate_control` |
| Meio | Tabela | H | `players_touched`, `open_rate`, `recovery_rate_diff` |
| Base | Tabela dinâmica | H | Linha: `campaign_name` · Coluna: `archetype_before` · Métrica: `recovery_rate_diff` |

**O aviso é parte do gráfico, não decoração.** Texto sugerido:

> Comparação observacional, não teste A/B. O grupo de controle não foi
> sorteado — é quem a régua não selecionou, e a régua escolhe justamente quem
> tem mais chance de reagir. A diferença mistura efeito de campanha com viés de
> seleção e tende a superestimar. Serve para priorizar o que testar, não para
> provar incrementalidade.

**Deixe `has_min_sample = true` ligado por padrão.** Abaixo de ~300 pessoas em
cada lado a diferença é ruído, e uma campanha com 12 tocados vai liderar o
ranking com 100% de recuperação.

Para medir efeito de verdade: holdout aleatório no Customer.io. Reserve 10% do
público-alvo dentro da própria régua, deixe rodar duas semanas e compare
tocados contra o holdout — aí a diferença é causal, e o mesmo gráfico serve.

### Página 5 — Jogadores (drill-down)

| Bloco | Componente | Fonte | Configuração |
|---|---|---|---|
| Topo | Controles | I | `archetype`, `value_tier`, `product_pref`, `platform`, `Jogando sem depositar` |
| Corpo | Tabela paginada | I | Ordenar por `action_priority`, depois `deposit_value_total` desc |
| Colunas | — | I | `player_id`, `archetype`, `movement_7d`, `days_since_last_deposit`, `deposit_value_total`, `touches_30d`, `is_fatigued`, `action_priority` |

Ative a exportação de CSV na tabela — é como a lista vira audiência no
Customer.io. A view `vw_audience_export` já monta os cinco grupos de trabalho
prontos, se preferir automatizar em vez de exportar à mão.

**`is_fatigued`** marca quem recebeu 8+ toques em 30 dias sem clicar em nenhum.
Vale tirar da régua antes de queimar o canal — e antes de virar reclamação de
spam, que custa domínio.

---

## 5. Filtros

Um controle de período e os filtros de dimensão numa faixa única no topo,
válidos para a página inteira. Filtro espalhado entre gráficos faz o leitor
comparar dois gráficos que estão olhando recortes diferentes sem perceber.

**O filtro de produto e canal não vale na página 1.** Os cartões da fonte B têm
deltas calculados sobre a base inteira: filtrando por "cassino", o número de
jogadores muda e a variação não — porque a variação continua sendo a da base
toda. Deixe esses controles nas páginas 2 a 5, onde as fontes preservam as
dimensões de recorte. Se a página 1 precisar mesmo de recorte, a saída é
calcular deltas por recorte numa view nova, não apontar o controle para a
fonte B.

---

## 6. Antes de publicar

- [ ] Todo gráfico com `archetype` está ordenado por `archetype_rank`, não pelo nome
- [ ] A matriz de migração tem `lag_days` travado num valor
- [ ] Nenhum gráfico usa dois eixos Y
- [ ] O GGR está rotulado como "GGR esportes" em toda ocorrência
- [ ] A página 4 tem o aviso de viés de seleção visível sem rolar
- [ ] Há um carimbo de última atualização (use `MAX(snapshot_date)`) — sem ele,
      um pipeline parado há três dias parece um dashboard atual
- [ ] Os extracts estão agendados depois do pipeline
- [ ] Abrir o relatório no celular: a barra de composição e a matriz são os dois
      que costumam quebrar

---

## 7. Reconciliar com o Customer.io

Uma vez por mês, ou depois de qualquer edição nos segmentos `[RFM]`:

```sql
SELECT archetype, COUNT(*) AS no_bigquery
FROM `PROJETO.DATASET.rfm_snapshots`
WHERE snapshot_date = CURRENT_DATE()
GROUP BY 1
ORDER BY 1;
```

Compare com a contagem de cada segmento 1952–1958 na interface. Diferença
acima de ~1% quer dizer que as definições saíram de sincronia — e aí o número
do Looker e o número que o time de CRM usa para disparar campanha discordam,
que é o pior lugar possível para uma divergência.

As regras estão transcritas em `pipeline/scoring.py`. Mudou lá, muda no
Customer.io — e vice-versa.
