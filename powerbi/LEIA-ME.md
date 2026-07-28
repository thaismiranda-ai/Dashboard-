# Projeto Power BI — incompleto

Estado: **modelo e tema prontos, visuais não**. Foi interrompido no meio.

O que está feito e é aproveitável mesmo sem o resto:

- `RFM-Health.SemanticModel/definition/tables/rfm_snapshots.tmdl` — conexão com
  o BigQuery e **todas as medidas DAX**: variação orientada pelo sinal do
  arquétipo, índice base 100, aviso de frescor, ordenação correta. É o trabalho
  chato, e vale copiar para qualquer arquivo Power BI novo.
- `RFM-Health.Report/StaticResources/RegisteredResources/rfm-theme.json` — tema
  com a paleta validada. Importável em qualquer relatório
  (Exibir → Temas → Procurar temas).

O que falta: os arquivos `visual.json` das páginas.

## Aviso

Isto foi escrito **sem poder testar**. Não há Power BI Desktop neste ambiente
(é só Windows) e a rede aqui bloqueia o site da Microsoft, então não deu para
validar contra os schemas oficiais do PBIR. Pode não abrir de primeira.

Se o Power BI recusar o projeto, apague a pasta
`RFM-Health.Report/definition/pages/` inteira: o relatório abre vazio, mas o
modelo e as medidas continuam de pé — que é a parte que economiza tempo.
