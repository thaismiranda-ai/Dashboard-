# Piloto de SMS — Aposta1

Análise de mercado e piloto executável para o canal SMS. Julho/2026.

| Documento | Para quê |
|---|---|
| [01 — Análise de mercado e regulatória](01-analise-mercado.md) | O que outras casas fazem com SMS, o que a regra brasileira exige desde 17/07/2026, e o diagnóstico do nosso setup no Customer.io |
| [02 — Piloto Wave 0](02-piloto-wave0.md) | Desenho do experimento: públicos, células, holdout, copy, medição e orçamento |
| [03 — Runbook de execução](03-runbook-execucao-hoje.md) | Passo a passo para colocar no ar hoje, com checklist |

## Resumo em 6 linhas

- O mercado usa SMS quase só para bônus em massa ("texto-foguete"). É o pior uso do canal e é onde todo mundo está.
- O espaço real está em **alta intenção** (falha de depósito, pré-jogo, liquidação de aposta) e em **reativação com holdout**.
- Desde **17/07/2026** todo SMS com oferta precisa carregar a advertência do Ministério da Fazenda (Portaria SPA/MF 1.964/2026).
- Detalhe técnico que muda o orçamento: a advertência tem acento fora do alfabeto GSM-7, então **todo SMS promocional custa ~3 segmentos**; SMS de serviço sem acento custa 1.
- Nosso setup tem 4 bloqueadores antes de qualquer disparo — o mais urgente é **o token da Zenvia em texto claro** no template do Customer.io.
- Wave 0: `[RFM] At Risk` (12.786), três células (oferta / lembrete / holdout), ~R$ 2,1 mil, decisão em 03/08.
