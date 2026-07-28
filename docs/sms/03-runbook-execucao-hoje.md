# Runbook — executar a Wave 0 hoje (28/07/2026)

Ordem de execução. Os passos **P0** são bloqueadores: sem eles não sai disparo.
Alvo de disparo da Faixa 1: **19h**.

---

## P0 · Bloqueadores (≈ 3h, podem correr em paralelo)

### P0.1 — Rotacionar a credencial da Zenvia ⚠️ segurança

O token da API Zenvia está **em texto claro** no header do template webhook 6967 (campanha 558 `[TESTE] Zenvia SMS`). Consequências: qualquer pessoa com acesso ao workspace lê o token; ele sai em qualquer duplicação ou export do template; e ele já circulou fora do cofre.

**Ação hoje:**
1. Revogar o token atual no painel da Zenvia e emitir um novo.
2. Guardar o novo token no cofre de segredos do time.
3. No Customer.io, referenciar o segredo em vez de colar o valor — se o workspace não tiver variável de ambiente disponível para header de webhook, colar o novo valor mas **restringir quem tem acesso de edição ao workspace** e registrar isso como dívida técnica no roadmap de 30 dias.
4. Não duplicar o template 6967. Criar template novo.

> Isto vale mesmo que o piloto seja adiado. É o item mais urgente do documento.

### P0.2 — Trocar o remetente

O template de teste usa `"from": "pix.na.hora"`. Um remetente com cara de serviço financeiro numa mensagem de aposta é problema duplo: risco de publicidade enganosa (art. 37 do CDC) e alvo fácil de filtro antispam de operadora.

**Ação:** confirmar com a Zenvia qual short code / sender ID homologado está disponível **para a marca Aposta1** e usá-lo. Se não houver, iniciar a homologação hoje — sem remetente da marca, o piloto não deveria sair.

### P0.3 — Fazer o opt-out funcionar

Hoje o segmento `[SUP] SMS Opt-out Zenvia` (2011) tem **0 pessoas**. Nunca houve caminho de volta de "SAIR" para o Customer.io. Disparar volume sem isso é risco de LGPD.

**Solução para hoje (funciona em horas):**
1. Pedir à Zenvia para **ativar opt-out por palavra-chave** (`SAIR`, `PARAR`, `SAIR APOSTA1`) no short code. Isso já garante que quem pedir para sair para de receber, na camada da Zenvia — que é a obrigação legal.
2. Exportar diariamente a lista de opt-out da Zenvia e importar no segmento estático 2011.
3. Adicionar o segmento 2011 como exclusão em toda campanha de SMS.

**Solução definitiva (roadmap 30 dias):** webhook de mensagem recebida (MO) da Zenvia → serviço intermediário que resolve telefone → `id` do jogador → Track API do Customer.io gravando `sms_optout = true`. Aí o opt-out é em tempo real.

### P0.4 — Template de envio de verdade

O template atual tem `to` fixo num número de teste e texto fixo. Criar **template novo** (não duplicar o 6967 — ver P0.1) com:

- **URL:** `https://api.zenvia.com/v2/channels/sms/messages`
- **Método:** `POST`
- **Headers:** `Content-Type: application/json` + `X-API-TOKEN: <novo token>`
- **Body:**

```json
{
  "from": "<SENDER_ID_APOSTA1>",
  "to": "{{ customer.Phone | replace: '+', '' }}",
  "contents": [
    {
      "type": "text",
      "text": "Aposta1: seu Freebet de R$20 vence amanha. Ative com deposito de R$20: a1.bet.br/fb?utm_source=sms&utm_medium=crm&utm_campaign=wave0&utm_content=a\n+18 Ministério da Fazenda adverte: Aposta não é investimento. SAIR p/ nao receber"
    }
  ]
}
```

Notas:
- A Zenvia espera o MSISDN **sem** o `+` — daí o `replace`.
- O `text` é JSON: qualquer aspas dupla dentro do texto precisa ser escapada. Evite aspas na copy.
- Não usar acento no corpo comercial não muda o encoding (a advertência já força UCS-2), mas mantenha o padrão para não estourar caracteres à toa.

---

## P1 · Segmentos (≈ 45 min)

### P1.1 — `[SMS] Elegível — Base`

Segmento dinâmico, reaproveitável em todas as campanhas de SMS:

**Inclui:** `Phone` casa com `^\+55\d{2}9\d{8}$` · `PlayerStatusString` = `Active`
**Exclui:** `IsBlocked` = `true` · autoexcluídos SIGAP · `Blocked Players - Beneficiary Programs` · `Blocked player list due to social Beneficiary validation` · membros de `[SUP] SMS Opt-out Zenvia` (2011) · `sms_optout` = `true` · menores de 18

Anotar a contagem resultante — é o tamanho real do canal SMS na Aposta1, número que hoje ninguém sabe.

### P1.2 — `[SMS] Wave0 — Elegível`

`[RFM] 🔶 At Risk` (1956) ∩ `[SMS] Elegível — Base`

Partindo de 12.786 na `At Risk`, esperar algo entre 9.000 e 11.500 após filtros. **Se sobrar menos de 8.500, reduzir as células proporcionalmente** mantendo a proporção 4:4:2,5 — não reduza o holdout primeiro.

### P1.3 — Sorteio das células

Gravar `sms_wave0_cell` = `a` | `b` | `c` no perfil, aleatoriamente, respeitando 4.000 / 4.000 / 2.500.

Duas formas, ambas válidas:
- **Preferida:** exportar a lista, sortear fora (planilha ou script), reimportar como atributo.
- **Rápida:** usar o split A/B nativo do Customer.io com braço de holdout, mas **grave o resultado como atributo** — sem isso a leitura de D+3 não é auditável.

Depois disso, os públicos de disparo são simplesmente `sms_wave0_cell = a` e `sms_wave0_cell = b`.

---

## P2 · Campanhas (≈ 45 min)

### P2.1 — Faixa 1 (reativação)

Duas campanhas, uma por célula (mais simples de ler que uma campanha com split):

- Gatilho: entrada no segmento `sms_wave0_cell = a` (e `= b`)
- Ação: webhook Zenvia com o template da célula
- Conversão: `DepositSuccessEvent`, janela **72h** (259200s)
- Frequency cap: ligado
- Janela de envio: seg–sáb, 09h–21h
- **Sem** re-entrada

> A ação nativa `twilio_action` que existe na campanha 558 **não funciona** — não há provedor de SMS conectado (`sms_providers` está vazio). Use só a ação de webhook. Remova a ação Twilio para ninguém se confundir.

### P2.2 — Faixa 2 (depósito falho)

- Gatilho: `DepositFailedEvent`
- Espera: 30 min
- Condição de saída: `DepositSuccessEvent` ocorreu → sai sem enviar
- Ação: webhook Zenvia, texto de serviço (1 segmento, sem acento, sem oferta)
- Pré-condição: `[SMS] Elegível — Base`
- Conversão: `DepositSuccessEvent` em 24h
- Cap: 1 por pessoa a cada 24h

Aproveitar a campanha 527 (`[MK] Flow Recovery DepositFailed — Email`, hoje em draft) acrescentando o passo de SMS, em vez de criar do zero.

---

## P3 · Teste antes do disparo (≈ 30 min) — não pular

1. **Seed list:** 5 a 10 celulares do time (Vivo, Claro, TIM e Oi — pelo menos uma linha de cada operadora).
2. Disparar as 3 peças para a seed list.
3. Conferir em cada aparelho:
   - [ ] chegou, e em quanto tempo
   - [ ] remetente aparece como Aposta1 (não `pix.na.hora`)
   - [ ] **não quebrou em mensagens separadas fora de ordem** (concatenação de 3 segmentos)
   - [ ] acentos corretos — `dependência`, `não`, `Ministério` sem caractere estranho
   - [ ] link abre e o UTM chega no analytics
   - [ ] responder `SAIR` realmente bloqueia o número
4. Checar na Zenvia: status de entrega, e se algo caiu na análise antispam.
5. Conferir no Customer.io: a conversão está apontando para `DepositSuccessEvent`.

**Se qualquer item falhar, o disparo não sai hoje.** Adiar um dia custa muito menos do que queimar a base ou virar caso de Procon.

---

## P4 · Aprovação (≈ 30 min)

Compliance/jurídico precisa aprovar por escrito as 3 peças, verificando:
- [ ] advertência do Ministério da Fazenda presente nas peças publicitárias (Portaria SPA/MF 1.964/2026, em vigor desde 17/07)
- [ ] condição da oferta explícita no corpo do SMS
- [ ] `+18` presente
- [ ] sem promessa de ganho, renda ou investimento
- [ ] opt-out presente e funcional
- [ ] público restrito a cadastrados, com supressões aplicadas

---

## P5 · Disparo — 19h

- Enviar célula A e célula B. Célula C não recebe nada.
- Registrar horário exato do disparo (a janela de 72h conta a partir dele).
- Acompanhar os primeiros 30 minutos: taxa de entrega e qualquer rejeição em bloco.

---

## P6 · Leitura

**D+1 (29/07, manhã)** — saúde operacional:
- taxa de entrega por operadora
- opt-outs
- rejeições por telefone inválido → alimenta a correção do `Check TELEFONE DDI`
- qualquer reclamação

**D+3 (31/07)** — resultado:

| Célula | n | Depósitos 72h | Taxa | Lift vs C | Custo | Custo/dep. incremental |
|---|---|---|---|---|---|---|
| A (oferta) | 4.000 | | | | | |
| B (lembrete) | 4.000 | | | | | |
| C (holdout) | 2.500 | | — | — | R$ 0 | — |

**03/08** — decisão:
- **A ≫ C e A > B** → oferta paga o próprio custo. Escalar A para `Hibernating` na Wave 1.
- **B ≈ A** → o SMS funciona como lembrete e o bônus está sendo dado à toa. Escalar B (bem mais barato) e cortar o custo de bônus.
- **A ≈ C e B ≈ C** → SMS não reativa dormente nesta base. Encerrar a Faixa 1, manter só as faixas de serviço (depósito falho, saque falho, liquidação de aposta), que custam 1/3 e têm intenção real.

---

## Checklist consolidado

**Bloqueadores**
- [ ] P0.1 token da Zenvia rotacionado e fora do template antigo
- [ ] P0.2 remetente da marca Aposta1 confirmado
- [ ] P0.3 opt-out por palavra-chave ativo na Zenvia + segmento 2011 alimentado
- [ ] P0.4 template novo com Liquid, sem número fixo

**Construção**
- [ ] P1.1 `[SMS] Elegível — Base` criado (anotar contagem: ______)
- [ ] P1.2 `[SMS] Wave0 — Elegível` criado (contagem: ______)
- [ ] P1.3 `sms_wave0_cell` gravado — a: ____ b: ____ c: ____
- [ ] P2.1 campanhas das células A e B configuradas
- [ ] P2.2 fluxo de depósito falho com SMS

**Antes de apertar o botão**
- [ ] P3 teste em seed list nas 4 operadoras, tudo verde
- [ ] P4 aprovação escrita de compliance
- [ ] Kill switch combinado e responsável definido

**Depois**
- [ ] P5 disparo 19h, horário registrado
- [ ] P6 leitura D+1 e D+3, decisão 03/08
