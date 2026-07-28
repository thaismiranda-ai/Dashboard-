# Projeto Power BI — INCOMPLETO, NÃO ABRA AINDA

Este projeto foi interrompido no meio. **Falta a pasta de visuais**
(`RFM-Health.Report/definition/pages/pagina-rfm/visuals/`), então o relatório
abre vazio na melhor das hipóteses.

Deixei versionado em vez de apagar porque a parte trabalhosa está pronta e
serve tanto para retomar quanto para copiar à mão.

## O que já está pronto

| Arquivo | Estado |
|---|---|
| `RFM-Health.SemanticModel/definition/tables/rfm_snapshots.tmdl` | Completo — conexão com o BigQuery, colunas, ordenação do arquétipo e 14 medidas DAX |
| `RFM-Health.Report/StaticResources/RegisteredResources/rfm-theme.json` | Completo — paleta validada, fundo escuro |
| `RFM-Health.Report/definition/report.json`, `pages.json`, `page.json` | Completos |
| Visuais (cards, barra, linha, tabela) | **Faltando** |

## O que não foi verificado

Nada disto foi aberto no Power BI Desktop — ele não roda em Linux, e a rede
deste ambiente bloqueia o site da Microsoft, então também não deu para validar
os arquivos contra os schemas oficiais do PBIR. Foi escrito de memória.
Trate como rascunho, não como entregável.

## A parte que vale mesmo sem o projeto

As medidas DAX em `tables/rfm_snapshots.tmdl` são copiáveis para qualquer
arquivo do Power BI. As três que resolvem problemas reais:

- **`Variação orientada 7d`** — multiplica a variação pelo sinal do arquétipo,
  então positivo é sempre movimento bom. Use na formatação condicional de cor,
  senão "Lost +0,9%" aparece verde e em Lost subir é ruim.
- **`Índice base 100`** — Lost (89 mil) e Promising (790) no mesmo eixo achatam
  cinco séries numa reta colada no zero. Indexado, o gráfico volta a mostrar
  crescimento relativo, que é a pergunta dele.
- **`Aviso de atualização`** — devolve a frase pronta ("⚠️ Parado há 3 dias").
  O pipeline roda no PC e só com você logada, então data solta engana: todo
  mundo lê como "está atualizado" sem fazer a conta.

E o `rfm-theme.json` é a paleta inteira num arquivo — importável em
**Exibição → Temas → Procurar temas**, sem precisar de nada mais deste projeto.

## Se for retomar

O caminho que estava em andamento era escrever um `visual.json` por visual em
`definition/pages/pagina-rfm/visuals/<id>/`. Antes de escrever qualquer coisa,
baixe os schemas oficiais do PBIR de uma rede sem bloqueio — escrever de
memória foi o que travou aqui.
