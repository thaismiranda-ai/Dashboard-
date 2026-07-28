# Blueprint do relatório — o que dá para montar hoje

Guia de montagem do relatório **"RFM Health — Aposta1"** em cima da tabela que
já existe: `rfm-customer-502116.crm.rfm_snapshots`, alimentada desde 12/07 pelo
`pipeline.py`.

> Este é o blueprint do **grão agregado** — 7 linhas por dia, uma por
> arquétipo. É o que a tabela atual tem e o que dá para montar sem mexer em
> nada da infraestrutura.
>
> O outro blueprint (`looker-blueprint.md`) descreve o relatório do **grão por
> jogador**, que desbloqueia matriz de migração, LTV e efeito de campanha. Ele
> depende de trocar o pipeline e habilitar billing — é fase 2, não agora.

---

## 0. Antes de começar: confira os nomes das colunas

A documentação descreve as colunas, mas não os nomes literais. Rode isto no
console do BigQuery e ajuste o SQL deste guia se algum nome divergir:

```sql
SELECT * FROM `rfm-customer-502116.crm.rfm_snapshots`
ORDER BY snapshot_date DESC LIMIT 3;
```

Este guia assume: `snapshot_date`, `archetype`, `customer_count`, `segment_id`,
`segment_name`. Se o carimbo de horário tiver outro nome, ele só aparece no
cartão de frescor (página 1) — troque lá.

Confira também quantos dias já existem, porque é isso que decide se o gráfico
de evolução vale a pena:

```sql
SELECT COUNT(DISTINCT snapshot_date) AS dias,
       MIN(snapshot_date) AS primeiro,
       MAX(snapshot_date) AS ultimo
FROM `rfm-customer-502116.crm.rfm_snapshots`;
```

Com menos de 7 dias, monte tudo menos a série temporal e volte nela depois.

---

## 1. As fontes de dados

**Use "Consulta personalizada", não a tabela direto.**

Conectar a tabela crua obrigaria a resolver ordenação de arquétipo, base
saudável e variação com campos calculados espalhados por vários gráficos — que
é onde duas páginas passam a discordar sem ninguém perceber. A consulta resolve
uma vez só.

E aqui não custa nada: são 7 linhas por dia. Mesmo com um ano de histórico são
~2.500 linhas, muito abaixo do limite de 1 TB/mês do Sandbox.

> Por que não uma view no BigQuery: no Sandbox, **views também expiram em 60
> dias**. A consulta personalizada vive dentro do relatório — não tem o que
> expirar.

No Looker Studio: **Criar → Fonte de dados → BigQuery → Consulta
personalizada** → projeto `rfm-customer-502116` → cole o SQL.

### Fonte A — série por arquétipo (alimenta quase tudo)

```sql
WITH base AS (
  SELECT
    snapshot_date,
    archetype,
    SUM(customer_count) AS jogadores
  FROM `rfm-customer-502116.crm.rfm_snapshots`
  GROUP BY 1, 2
),
totais AS (
  SELECT snapshot_date, SUM(jogadores) AS base_total
  FROM base GROUP BY 1
)
SELECT
  b.snapshot_date,
  b.archetype,
  b.jogadores,
  t.base_total,
  SAFE_DIVIDE(b.jogadores, t.base_total) AS share,

  -- Ordem canônica: 1 = mais saudável, 7 = mais frio.
  -- O Looker ordena texto por ordem alfabética, o que coloca "At Risk" antes
  -- de "Champions" e embaralha a leitura. Ordene SEMPRE por este campo.
  CASE b.archetype
    WHEN 'Champions'      THEN 1
    WHEN 'Loyal'          THEN 2
    WHEN 'Promising'      THEN 3
    WHEN 'Need Attention' THEN 4
    WHEN 'At Risk'        THEN 5
    WHEN 'Hibernating'    THEN 6
    WHEN 'Lost'           THEN 7
  END AS archetype_rank,

  CASE
    WHEN b.archetype IN ('Champions','Loyal','Promising') THEN 'Saudável'
    WHEN b.archetype IN ('Need Attention','At Risk')      THEN 'Em risco'
    ELSE 'Frio'
  END AS health_bucket,

  -- Em Champions/Loyal/Promising crescer é bom; nos demais, crescer é ruim.
  CASE WHEN b.archetype IN ('Champions','Loyal','Promising') THEN 1 ELSE -1 END
    AS growth_polarity,

  -- Comparação com 7 dias antes. Usa JOIN em snapshot_date - 7, e não LAG(7),
  -- de propósito: o pipeline roda no PC da Thais e só quando ela está logada,
  -- então dia faltante acontece. LAG(7) devolveria a variação de 8 dias sem
  -- avisar; o JOIN devolve NULL, que aparece no gráfico em vez de mentir.
  p7.jogadores AS jogadores_d7,
  b.jogadores - p7.jogadores AS delta_abs_7d,
  SAFE_DIVIDE(b.jogadores - p7.jogadores, p7.jogadores) AS delta_pct_7d,

  -- Variação já orientada: positivo = movimento BOM, sempre.
  -- É este campo que colore os cartões. Sem ele, "Lost +0,9%" aparece verde.
  SAFE_DIVIDE(b.jogadores - p7.jogadores, p7.jogadores)
    * CASE WHEN b.archetype IN ('Champions','Loyal','Promising') THEN 1 ELSE -1 END
    AS variacao_orientada_7d,

  -- Índice com o primeiro dia = 100. É o que permite pôr os sete arquétipos
  -- num gráfico só: Lost (89 mil) e Promising (790) no mesmo eixo linear
  -- achatam as cinco séries de baixo numa reta colada no zero. Indexado, o que
  -- se compara é o crescimento relativo, que é a pergunta do gráfico.
  -- O Looker Studio não sabe indexar sozinho — precisa vir pronto daqui.
  SAFE_DIVIDE(
    b.jogadores,
    FIRST_VALUE(b.jogadores) OVER (PARTITION BY b.archetype ORDER BY b.snapshot_date)
  ) * 100 AS indice_base_100

FROM base AS b
JOIN totais AS t USING (snapshot_date)
LEFT JOIN base AS p7
  ON p7.archetype = b.archetype
 AND p7.snapshot_date = DATE_SUB(b.snapshot_date, INTERVAL 7 DAY)
```

### Fonte B — saúde da base (uma linha por dia)

```sql
WITH diario AS (
  SELECT
    snapshot_date,
    SUM(customer_count) AS base_total,
    SUM(IF(archetype IN ('Champions','Loyal','Promising'), customer_count, 0))
      AS saudaveis,
    SUM(IF(archetype IN ('Need Attention','At Risk'), customer_count, 0))
      AS em_risco,
    SUM(IF(archetype IN ('Hibernating','Lost'), customer_count, 0))
      AS frios
  FROM `rfm-customer-502116.crm.rfm_snapshots`
  GROUP BY 1
)
SELECT
  snapshot_date,
  base_total,
  saudaveis,
  em_risco,
  frios,
  SAFE_DIVIDE(saudaveis, base_total)        AS share_saudavel,
  0.45                                      AS meta,           -- meta Q3
  SAFE_DIVIDE(saudaveis, base_total) - 0.45 AS distancia_meta,

  DATE_DIFF(CURRENT_DATE(), snapshot_date, DAY) AS dias_atras,

  -- Carimbo de frescor. O pipeline depende do notebook estar ligado, então
  -- "parado há 3 dias" é cenário real, não hipótese.
  CASE
    WHEN DATE_DIFF(CURRENT_DATE(), MAX(snapshot_date) OVER (), DAY) <= 1
      THEN CONCAT('Atualizado em ', FORMAT_DATE('%d/%m', MAX(snapshot_date) OVER ()))
    ELSE CONCAT('⚠️ Parado há ',
                CAST(DATE_DIFF(CURRENT_DATE(), MAX(snapshot_date) OVER (), DAY) AS STRING),
                ' dias · dado de ',
                FORMAT_DATE('%d/%m', MAX(snapshot_date) OVER ()))
  END AS aviso_frescor
FROM diario
```

---

## 2. Cores

O relatório hoje usa sete matizes (verde, azul, ciano, roxo, âmbar, cinza,
cinza-escuro). Sugiro trocar por uma **rampa de um matiz só**.

O motivo: os arquétipos são uma **escala ordenada** de saúde, não categorias
soltas. Com sete cores arbitrárias, ninguém sabe se roxo é melhor ou pior que
âmbar sem consultar a legenda. Com a rampa, a ordem se lê sozinha — mais claro
é mais saudável.

É uma troca de dois minutos, num lugar só: **Recurso → Gerenciar cores por
valor de dimensão**.

| Arquétipo | Hex |
|---|---|
| Champions | `#cde2fb` |
| Loyal | `#9ec5f4` |
| Promising | `#6da7ec` |
| Need Attention | `#3987e5` |
| At Risk | `#256abf` |
| Hibernating | `#184f95` |
| **Lost** | `#42464f` |

Valores validados para fundo escuro (luminosidade monótona, salto suficiente
entre degraus vizinhos, cada um legível sobre a superfície).

**Lost é cinza, fora da rampa, de propósito.** Ele é ~60% da base e, como
degrau da rampa, dominaria visualmente toda composição. Cinza neutro diz "massa
de fundo" em vez de "mais um degrau", e é ligeiramente mais escuro que
Hibernating para a recessão continuar monótona: quanto pior o arquétipo, menos
ele grita.

Para as setas de variação, use cores de status — canal separado da identidade,
sempre com seta **e** número, nunca só a cor:

| Papel | Hex |
|---|---|
| Movimento bom | `#0ca30c` |
| Ruim | `#d03b3b` |

---

## 3. A página

Uma página só. Com este grão de dado, espalhar em várias só esconde as coisas.

### Faixa 1 — cartões

| Gráfico | Fonte | Configuração |
|---|---|---|
| Scorecard | B | `aviso_frescor` — texto, sem agregação. **Ponha em primeiro lugar.** |
| Scorecard | B | `share_saudavel`, formato porcentagem, comparação de período |
| Scorecard | B | `base_total` |
| Scorecard | B | `distancia_meta`, rótulo "p.p. até a meta" |

**O cartão de frescor vale mais do que parece.** O pipeline roda no notebook da
Thais e só quando ela está logada. Um fim de semana com o notebook desligado e
o dashboard mostra sexta-feira, com a mesma cara de sempre. O campo já vem com
a frase pronta porque data solta todo mundo lê como "está atualizado" sem fazer
a conta.

Formatação condicional: fundo vermelho quando o texto contiver `⚠️`.

### Faixa 2 — composição

**Gráfico de barras empilhadas 100%**, fonte A:
- Dimensão de detalhamento: `archetype`
- Métrica: `jogadores`
- Ordenar por: `archetype_rank`, crescente
- Filtro: data mais recente

### Faixa 3 — evolução (o gráfico principal)

**Série temporal**, fonte A:
- Dimensão: `snapshot_date`
- Detalhamento: `archetype`
- Métrica: `jogadores`
- Ordenar por: `archetype_rank`

**Use a métrica `indice_base_100`, não `jogadores`.**

Lost tem ~89 mil e Promising ~790. Com a contagem crua no mesmo eixo, as cinco
séries de baixo viram uma reta colada no zero e o gráfico não mostra movimento
nenhum — que é exatamente o que ele existe para mostrar. Eu caí nessa ao montar
o protótipo e só percebi depois de renderizar e olhar.

Indexado, todas partem de 100 no primeiro dia e o que se compara é crescimento
relativo. Need Attention subindo para 111 enquanto At Risk cai para 91 fica
óbvio; em contagem crua, invisível.

Configure o eixo Y com mínimo 85 e máximo 115 (Estilo → Eixo Y esquerdo), senão
o Looker parte do zero e achata tudo de novo.

Se preferir contagem absoluta, a alternativa é **dois gráficos lado a lado** —
um com Lost e Hibernating, outro com os cinco de cima. Não use escala
logarítmica: cabe tudo, mas variação de 10% quase não se vê e quem não está
acostumado lê errado.

Não use eixo Y duplo em hipótese nenhuma. Duas escalas no mesmo gráfico deixam
qualquer correlação ser provada só escolhendo os limites.

### Faixa 4 — tabela e KPIs por arquétipo

**Tabela**, fonte A, filtrada na data mais recente:

| Coluna | Campo |
|---|---|
| Arquétipo | `archetype` |
| Jogadores | `jogadores` |
| Var. 7d | `delta_pct_7d`, formato porcentagem |
| Share | `share`, formato porcentagem |

Ordenar por `archetype_rank`. Formatação condicional na variação usando
**`variacao_orientada_7d`**: verde quando positivo, vermelho quando negativo.

> É este campo que impede o erro mais comum deste dashboard: "Lost ▲ 0,9%"
> pintado de verde porque o número subiu. Em Lost, subir é ruim.

**Quatro scorecards** abaixo, fonte A, cada um filtrado num arquétipo
(Champions, Need Attention, At Risk, Loyal), métrica `jogadores`, com
comparação de período de 7 dias ligada para aparecer a seta.

---

## 3b. Como reproduzir o layout de referência

O layout está publicado como página de referência (link no README). Bloco a
bloco, o componente equivalente:

| Bloco no layout | No Looker Studio | Observações |
|---|---|---|
| Cartão escuro com borda | Retângulo (Inserir → Forma) atrás dos componentes | Preenchimento `#1A1F2E`, borda `#2c2c2a` 1px, cantos arredondados |
| Número grande do KPI | Scorecard | Estilo → fonte 32px, negrito |
| Seta de variação verde/vermelha | Scorecard → Comparação: "Período anterior" | Ver a ressalva abaixo |
| Minigráfico dentro do cartão | Gráfico de **Sparkline** logo abaixo do scorecard | Scorecard não embute gráfico; posicione um sob o outro dentro do mesmo retângulo |
| Barra de composição | Barras empilhadas 100%, horizontal | Dim. detalhamento `archetype`, ordenar por `archetype_rank` |
| Gráfico de evolução | Série temporal | Métrica `indice_base_100`, eixo Y 85–115 |
| Rótulos no fim das linhas | Legenda à direita | O Looker não rotula a ponta de cada série; a legenda lateral é o mais próximo |
| Tabela de variação | Tabela | Formatação condicional por `variacao_orientada_7d` |
| Barrinhas de share na tabela | Tabela → coluna → Tipo "Barra" | Já é nativo, não precisa de imagem |
| Regra sob o nome do arquétipo | Campo calculado com `CASE` devolvendo o texto | Ou uma segunda linha de texto fixa |

### A ressalva das setas de variação

A comparação de período nativa do scorecard colore **verde quando o número
sobe**, sempre. Para "Need Attention" e "Lost", subir é ruim — então os
cartões desses dois arquétipos vão sair com a cor invertida.

Três saídas:

1. **Desligar a cor** da comparação nesses cartões (Estilo → Comparação →
   cor fixa cinza) e deixar o texto do cartão dizer o sentido: "crescer aqui é
   ruim". É o que o layout de referência faz, e é a saída mais simples.
2. **Usar tabela em vez de scorecard** para esses arquétipos, com formatação
   condicional em `variacao_orientada_7d` — aí a cor sai certa.
3. Um scorecard com métrica `variacao_orientada_7d` direto, formatada como
   porcentagem. Mostra o sentido correto, mas o número deixa de bater com o que
   as pessoas esperam ver.

Recomendo a 1. A cor errada num cartão é o tipo de detalhe que ninguém
questiona e todo mundo interpreta.

### O que não traduz

- **Gradientes e sombras dos cartões** — o Looker tem preenchimento sólido e
  borda. A diferença é estética e não muda a leitura.
- **Tooltip com os sete arquétipos de uma vez** — o do Looker mostra a série
  sob o cursor. Não há como reproduzir o crosshair completo.
- **Rótulo direto na ponta da linha** — só legenda.

Nada disso muda o que o dashboard responde. Se em algum ponto a versão do
Looker ficar mais pobre do que a página de referência, é aqui.

---

## 4. Se aparecer "No data"

Quase sempre é o **intervalo de datas padrão do relatório** não cobrindo os
snapshots. Ajuste para "Automático" ou um período que inclua as datas.

Se persistir, confira se a consulta personalizada roda sozinha no console do
BigQuery — erro de SQL no Looker aparece como "No data", não como erro.

---

## 5. Antes de compartilhar

- [ ] O cartão de frescor está na primeira posição e a formatação condicional funciona
- [ ] Todo gráfico com `archetype` está ordenado por `archetype_rank`, não pelo nome
- [ ] As setas de variação usam `variacao_orientada_7d`, não `delta_pct_7d`
- [ ] Nenhum gráfico usa eixo Y duplo
- [ ] A evolução está em dois gráficos, ou em escala log com o rótulo dizendo isso
- [ ] Aberto no celular — a tabela e a composição são as que costumam quebrar
- [ ] Compartilhado em modo **Visualizar**, não Editar

---

## 6. O que este relatório não responde

Vale deixar explícito para não virar cobrança depois. Com 7 linhas por dia é
impossível saber:

- **Para onde as pessoas foram.** "At Risk caiu 8,7% e Lost subiu" pode ser
  duas coisas opostas — os At Risk se recuperaram e outra gente caiu em Lost,
  ou os próprios At Risk viraram Lost. Sem dado por jogador não há como saber.
- **Quanto vale cada arquétipo.** A tabela conta cabeças, não reais.
- **Se as campanhas funcionam.** Exige cruzar quem foi tocado com quem se
  recuperou, jogador a jogador.

Os três dependem do modelo por jogador — o `looker-blueprint.md`, fase 2.
