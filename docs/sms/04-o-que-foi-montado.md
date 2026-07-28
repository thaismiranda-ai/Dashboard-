# O que já está montado — estado real em 28/07/2026

Registro do que foi criado no Customer.io (workspace 112427) e do que mudou em relação ao plano dos documentos 02 e 03. **Onde este documento divergir dos anteriores, vale este.**

---

## A decisão que mudou: o piloto inteiro roda no Customer.io

O plano original era exportar a lista, sortear as células fora e subir na Zenvia. **Não é possível hoje**, por três motivos que só apareceram na execução:

1. **A exportação pela API retorna 403** para a credencial de serviço — tanto `customers/exports` quanto `exports/segment_memberships`. É permissão, não bug.
2. **A exportação pela UI também não está disponível** para o usuário.
3. **Paginar a base na mão não escala:** a listagem de perfis é travada em **50 por página** (testado com `limit`, `size`, `per_page`, `page_size` e `count` — todos ignorados) e a auto-paginação da ferramenta está quebrada, falhando até com 150 pessoas. Seriam 215 chamadas para 10.703 pessoas.

Solução: **o sorteio e o disparo passam a acontecer dentro do Customer.io**, usando o split aleatório nativo. O envio continua saindo pela Zenvia via webhook — ou seja, **a entrega continua aparecendo no painel da Zenvia**, que era o motivo de querer passar por lá.

O que se perde em relação ao plano da planilha: nada relevante. O que se ganha: o sorteio fica auditável dentro da ferramenta, a alocação vira atributo no perfil, e ninguém precisa manipular um CSV com 10 mil telefones.

> **Se alguém do time tiver permissão de export**, o caminho antigo volta a funcionar e a ferramenta de sorteio continua publicada: https://claude.ai/code/artifact/5cecbc20-afaf-4192-b84a-816ed4bd7c61 — ela valida E.164, remove duplicados e sorteia as células, tudo local no navegador. Vale pedir a permissão ao admin do workspace de qualquer forma: sem ela, análise fora da ferramenta fica sempre travada.

---

## Segmentos

### `[SMS] Elegível — Base` · id **2013** · dinâmico

Base reaproveitável para qualquer disparo de SMS, agora e depois.

- **Inclui:** `Phone` existe · `PlayerStatusString` **não** é `blocked`, `closed` nem `suspended`
- **Exclui:** `[SUP] Excluir de Marketing — Bloqueados e SIGAP` (1667) · `Blocked Players - Beneficiary Programs` (1069) · `Blocked player list due to social Beneficiary validation` (1196) · `[SUP] SMS Opt-out Zenvia` (2011)

**Resultado: 267.719 pessoas.** Esse é o tamanho real do canal SMS na Aposta1 — número que não existia antes.

> A validação estrita de E.164 **não** está no segmento, de propósito: o Customer.io não tem operador de regex, e um filtro frouxo descartaria silenciosamente quem tem o telefone gravado em outro formato. Com o disparo passando pelo Customer.io, quem estiver com telefone inválido vai falhar no envio e aparecer como erro na Zenvia — o que dá a medida real do problema no D+1. Isso alimenta a correção do `Check TELEFONE DDI` (1766).

### `[SMS] Wave0 — At Risk Elegível` · id **2014** · dinâmico

`[RFM] 🔶 At Risk` (1956) cruzado com os mesmos critérios acima.

**Resultado: 10.703 pessoas** — de 12.786 no At Risk, 2.083 removidos pelas supressões (16%).

> As condições estão repetidas de forma plana em vez de referenciar o 2013. Não é descuido: o Customer.io só permite referenciar segmentos-folha (profundidade máxima 1), e o 2013 já referencia outros segmentos. Ao mexer em um, mexer no outro.

### Segmentos de leitura

| Segmento | id | Serve para |
|---|---|---|
| `[SMS] Wave0 · A · base` | 2016 | denominador da célula A |
| `[SMS] Wave0 · B · base` | 2017 | denominador da célula B |
| `[SMS] Wave0 · C · base (holdout)` | 2018 | denominador do holdout |
| `[SMS] Wave0 · A · depositou 72h` | 2019 | numerador da célula A |
| `[SMS] Wave0 · B · depositou 72h` | 2020 | numerador da célula B |
| `[SMS] Wave0 · C · depositou 72h (holdout)` | 2021 | numerador do holdout |

⚠️ **A janela de 72h é móvel** — conta para trás a partir do momento em que o segmento é avaliado. Esses seis números precisam ser lidos **no D+3 (31/07)**. Lidos depois, medem outra coisa.

---

## Campanhas

### `[SMS] Wave 0 — Reativação At Risk (A/B/Holdout)` · id **561** · **draft**

| | |
|---|---|
| Tipo | seg_attr (entra quem está no segmento) |
| Gatilho | `[SMS] Wave0 — At Risk Elegível` (2014) |
| Conversão | `DepositSuccessEvent`, janela de 72h |
| Validação | sem warnings |

**Fluxo:**

```
Sorteio Wave 0 (6404) — split aleatório nativo, 375 / 375 / 250
   ├── A — oferta      → carimba célula (6405) → SMS Zenvia (6406) → saída
   ├── B — lembrete    → carimba célula (6407) → SMS Zenvia (6408) → saída
   └── C — holdout     → carimba célula (6409) ────────────────────→ saída
```

Cada perfil recebe o atributo `sms_wave0_cell` = `a` / `b` / `c` **antes** do envio, então a alocação fica registrada no perfil e a leitura do D+3 é auditável. O holdout é carimbado igual, e não recebe mensagem nenhuma.

**Proporções:** 37,5% / 37,5% / 25%. Sobre 10.703 isso dá aproximadamente **4.014 / 4.014 / 2.675** — praticamente o desenho original de 4.000 / 4.000 / 2.500, sem precisar de corte manual.

**Mensagens:**

| Célula | Texto | Encoding | Segmentos |
|---|---|---|---|
| A | `Aposta1: seu Freebet de R$20 vence amanha. Ative com deposito de R$20: a1.bet.br/fb-a` + advertência + `SAIR p/ nao receber` | UCS-2, 167 car. | **3** |
| B | `Aposta1: os jogos de hoje ja estao no ar: a1.bet.br/j-b` + advertência + `SAIR p/ parar` | UCS-2, 131 car. | **2** |

Advertência usada: `+18 Ministério da Fazenda adverte: Aposta não é investimento.`

### `[SMS] Recuperação de Depósito Falho — Zenvia` · id **560** · **draft**

| | |
|---|---|
| Tipo | transactional (disparada por evento) |
| Gatilho | `DepositFailedEvent` |
| Filtro | `[SMS] Elegível — Base` (2013) |
| Fluxo | espera 30 min (6401) → webhook Zenvia (6402) → saída |
| Conversão | `DepositSuccessEvent`, janela de 24h |
| Saída antecipada | **ligada** — quem concluir o depósito nos 30 min sai sem receber SMS |

**Mensagem** — serviço puro, sem oferta e sem acento:

```
Aposta1: seu deposito nao foi concluido. Nada foi cobrado. Tentar de novo: a1.bet.br/d?utm_source=sms&utm_campaign=dep_falho
```

`GSM-7 · 124 caracteres · 1 segmento`

Aqui as UTMs cabem sem custo, porque a mensagem é curta e continua em 1 segmento. Nas promocionais não cabem — ver abaixo.

---

## Correção ao plano: link curto em vez de UTM na mensagem

Medido ao escrever a copy final: colar `?utm_source=sms&utm_campaign=wave0&utm_content=a` no SMS custa 48 caracteres. Em UCS-2 isso empurra a célula A de **3 para 4 segmentos** e a B de **2 para 3** — um terço a mais de custo por mensagem, sem nenhum ganho de medição.

Solução adotada nos templates: links curtos `a1.bet.br/fb-a` e `a1.bet.br/j-b`, com as UTMs aplicadas no redirect. **Os dois redirects precisam existir antes do disparo.**

O orçamento do documento 02 continua valendo.

---

## Placeholders deixados de propósito

Os dois webhooks da campanha 561 e o da 560 estão com:

- `X-API-TOKEN` → `COLE_AQUI_O_NOVO_TOKEN_ZENVIA`
- `from` → `REMETENTE_APOSTA1`

Não preenchi com o token que está no template de teste porque ele precisa ser **revogado**, e copiá-lo para mais três lugares só aumentaria a superfície do problema.

---

## O que falta — nada disto está ao meu alcance

- [ ] **Revogar e rotacionar o token da Zenvia** — segue sendo o item mais urgente, independente do piloto
- [ ] Confirmar o **short code / sender ID da marca Aposta1** com a Zenvia
- [ ] Ativar **opt-out por palavra-chave** (SAIR / PARAR) no short code
- [ ] Criar os redirects **`a1.bet.br/fb-a`**, **`a1.bet.br/j-b`** e **`a1.bet.br/d`** com UTM no destino
- [ ] Preencher os placeholders nas campanhas 560 e 561
- [ ] **Teste em seed list nas quatro operadoras** — Vivo, Claro, TIM e Oi
- [ ] Aprovação escrita de compliance nas três peças
- [ ] Iniciar a campanha 561 **com backfill ligado** (sem isso, só entra quem passar a fazer parte do segmento depois)
- [ ] Ler os seis segmentos de leitura **no D+3, 31/07**
- [ ] Pedir ao admin do workspace a **permissão de exportação** — não é bloqueador do piloto, mas trava qualquer análise fora da ferramenta

---

## Adendo — a lista foi extraída (28/07, fim do dia)

A exportação segue bloqueada (403 na API, indisponível na UI), mas deu para contornar paginando a listagem de perfis, que é travada em **50 por página** e sem auto-paginação funcional.

**O que foi extraído:** **4.955 registros** do segmento 2014, cobrindo toda a faixa de cadastro:

- páginas 1 a 51, contíguas (2.550 pessoas — as mais antigas)
- páginas 53 a 101, uma a cada duas (1.250)
- páginas 103 a 215, uma a cada cinco (1.155)

Depois da validação: 14 telefones descartados (fixo, sem o nono dígito, ou não-celular) e 6 repetidos. **4.935 elegíveis**, sorteados com semente fixa `wave0-2026-07-28`:

| Célula | n | Destino |
|---|---|---|
| A — oferta | 1.850 | sobe na Zenvia |
| B — lembrete | 1.850 | sobe na Zenvia |
| C — holdout | 1.235 | **não sobe** |

### O que isso custa em poder estatístico

A amostra é ~46% do segmento. Com taxa base estimada de 4% de reativação em 72h, o teste passa a detectar um lift de **~2,0 p.p.** contra o holdout (era ~1,4 p.p. com a base inteira) — ou seja, só enxerga um efeito de 50% ou mais em termos relativos.

A validade interna não é afetada: o sorteio A/B/C é aleatório dentro da amostra, então a comparação entre células continua limpa. O que fica menor é o alcance da conclusão — ela vale para a amostra, não automaticamente para os 10.703.

Se o resultado vier ambíguo, a leitura correta é "faltou n", não "SMS não funciona".

### Entregues

`Piloto_SMS_Wave0_Aposta1.xlsx` (abas: leia-me, célula A, célula B, holdout, alocação completa) e os CSVs `wave0_celula_A.csv`, `wave0_celula_B.csv`, `wave0_holdout_C.csv`, `wave0_alocacao_completa.csv`.

Guardar a alocação completa: é ela que permite ler o D+3 cruzando com quem depositou.
