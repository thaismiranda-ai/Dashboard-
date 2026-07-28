# O que já está montado — estado real em 28/07/2026

Registro do que foi criado no Customer.io (workspace 112427) e do que mudou em relação ao plano dos documentos 02 e 03. **Onde este documento divergir dos anteriores, vale este.**

---

## Arquitetura final: o disparo em lote sai pela Zenvia

Decisão tomada depois do levantamento: as duas faixas do piloto seguem caminhos diferentes, porque as necessidades são diferentes.

| Faixa | Onde roda | Por quê |
|---|---|---|
| **Reativação (lote)** | Lista exportada → subida direto na **Zenvia** | A Zenvia entrega métrica de entrega e opt-out nativo por palavra-chave. O Customer.io não tem provedor de SMS conectado, então o webhook enviaria às cegas. |
| **Depósito falho (gatilho)** | **Customer.io**, webhook → Zenvia | É disparo em tempo real, 30 min após o evento. Não existe em lote. |

Isso resolve na prática os bloqueadores B2 (sem provedor nativo) e B4 (opt-out nunca capturado) para a faixa de maior volume — sem esperar a homologação de um provedor nativo.

---

## Segmentos criados

### `[SMS] Elegível — Base` · id **2013** · dinâmico

Base reaproveitável para qualquer disparo de SMS, agora e depois.

- **Inclui:** `Phone` existe · `PlayerStatusString` **não** é `blocked`, `closed` nem `suspended`
- **Exclui:** `[SUP] Excluir de Marketing — Bloqueados e SIGAP` (1667) · `Blocked Players - Beneficiary Programs` (1069) · `Blocked player list due to social Beneficiary validation` (1196) · `[SUP] SMS Opt-out Zenvia` (2011)

**Resultado: 267.719 pessoas.** Esse é o tamanho real do canal SMS na Aposta1 — número que não existia antes.

> A validação estrita de E.164 **não** está no segmento, de propósito. O Customer.io não tem operador de regex, e um filtro frouxo (`contains "+55"`) descartaria silenciosamente quem tem o telefone gravado em outro formato. A validação acontece na exportação, onde dá para ver e reportar quantos caíram e por quê.

### `[SMS] Wave0 — At Risk Elegível` · id **2014** · dinâmico

`[RFM] 🔶 At Risk` (1956) cruzado com os mesmos critérios acima.

**Resultado: 10.703 pessoas** — de 12.786 no At Risk, 2.083 removidos pelas supressões (16%).

> As condições estão repetidas de forma plana em vez de referenciar o segmento 2013. Não é descuido: o Customer.io só permite referenciar segmentos-folha (profundidade máxima 1), e o 2013 já referencia outros segmentos. Ao mexer em um, mexer no outro.

---

## Campanha criada

### `[SMS] Recuperação de Depósito Falho — Zenvia` · id **560** · **draft**

| | |
|---|---|
| Tipo | transactional (disparada por evento) |
| Gatilho | `DepositFailedEvent` |
| Filtro | `[SMS] Elegível — Base` (2013) |
| Fluxo | espera 30 min (ação 6401) → webhook Zenvia (ação 6402) → saída |
| Conversão | `DepositSuccessEvent`, janela de 24h |
| Saída antecipada | **ligada** — quem concluir o depósito durante os 30 min sai do fluxo sem receber SMS |
| Validação | sem warnings |

**Mensagem** (template 6987) — serviço puro, sem oferta e sem acento:

```
Aposta1: seu deposito nao foi concluido. Nada foi cobrado. Tentar de novo: a1.bet.br/d?utm_source=sms&utm_campaign=dep_falho
```

`GSM-7 · 124 caracteres · 1 segmento`

Aqui as UTMs cabem sem custo, porque a mensagem é curta e continua em 1 segmento. Nas mensagens promocionais não cabem — ver abaixo.

**Placeholders que precisam ser trocados antes de ativar** (há um post-it vermelho no canvas com isso):

- `X-API-TOKEN` → o token **novo** da Zenvia. O antigo estava em texto claro no template de teste e precisa ser revogado.
- `REMETENTE_APOSTA1` → o short code homologado da marca.

Deixei os placeholders de propósito: propagar o token vazado para uma segunda campanha só aumentaria a superfície do problema.

---

## Separador de células (roda no navegador)

**https://claude.ai/code/artifact/5cecbc20-afaf-4192-b84a-816ed4bd7c61**

A exportação pela API está bloqueada para a credencial de serviço (403 tanto em `customers/exports` quanto em `exports/segment_memberships`), então o CSV sai pela UI do Customer.io. O sorteio das células continua sendo obrigatório — sem ele não há holdout, e sem holdout o piloto não mede nada.

A ferramenta recebe o CSV exportado e faz, tudo local, sem enviar nada:

1. valida E.164 de celular brasileiro — DDD existente, nono dígito, e normaliza variantes (sem `+`, sem `55`, número de 11 dígitos);
2. remove telefones repetidos;
3. sorteia com semente fixa e visível, para o sorteio ser reproduzível e auditável;
4. gera `wave0_celula_A.csv`, `wave0_celula_B.csv`, `wave0_holdout_C.csv` e `wave0_alocacao_completa.csv`;
5. mostra o contador de segmentos de cada peça.

**Fluxo:** exportar o segmento 2014 (com `id`, `Phone`, `FirstName`) → soltar na ferramenta → subir A e B na Zenvia → guardar a alocação completa.

> O arquivo de alocação completa é o que permite ler o resultado no D+3. Sem ele, o holdout vira uma lista sem função. Vale importar a coluna `sms_wave0_cell` de volta no Customer.io como atributo.

---

## Correções ao plano original

### Link curto em vez de UTM na mensagem

Medido na hora de escrever a copy final: colar `?utm_source=sms&utm_campaign=wave0&utm_content=a` no SMS custa 48 caracteres. Em UCS-2 isso empurra a célula A de **3 para 4 segmentos** e a B de **2 para 3** — um terço a mais de custo por mensagem, sem nenhum ganho de medição.

Solução: links curtos `a1.bet.br/fb-a` e `a1.bet.br/j-b`, com as UTMs aplicadas no redirect. **Pedir dois redirects ao time de web antes do disparo.**

Copy final, já com link curto:

| Célula | Encoding | Caracteres | Segmentos |
|---|---|---|---|
| A — com oferta | UCS-2 | 167 | **3** |
| B — lembrete | UCS-2 | 131 | **2** |
| Serviço — depósito falho | GSM-7 | 124 | **1** |

O orçamento do documento 02 continua valendo.

### Tamanho das células

Com 10.703 elegíveis, o desenho de 4.000 / 4.000 / 2.500 cabe, sobrando ~200 de reserva — bem mais apertado do que os ~2.000 previstos. Se quiser reserva maior para a Wave 1, cortar A e B para 3.500 cada mantém o holdout intacto e deixa ~1.200 de folga, com MDE pouco pior (~1,5 p.p.).

---

## O que ainda falta (nenhum destes eu consigo fazer)

- [ ] **Revogar e rotacionar o token da Zenvia** — segue sendo o item mais urgente, independente do piloto
- [ ] Confirmar o **short code / sender ID da marca Aposta1** com a Zenvia
- [ ] Ativar **opt-out por palavra-chave** (SAIR / PARAR) no short code
- [ ] Criar os dois **redirects curtos** com UTM
- [ ] Exportar o segmento 2014 e rodar o separador
- [ ] Preencher os placeholders da campanha 560 e tirar do draft
- [ ] **Teste em seed list nas quatro operadoras**
- [ ] Aprovação escrita de compliance nas três peças
