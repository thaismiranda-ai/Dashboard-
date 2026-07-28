# Piloto SMS "Wave 0" — desenho executável

**Janela:** disparo 28/07/2026 (terça) · leitura até 31/07 · decisão 03/08
**Plataforma:** Customer.io (workspace 112427) → webhook → Zenvia
**Orçamento estimado:** ~R$ 1.400 (ver §6)

---

## 1. Objetivo

Não é "testar SMS". É responder **três perguntas** com número, em uma semana:

1. **SMS gera depósito incremental** em jogador dormente, ou só antecipa depósito que aconteceria? → holdout.
2. **A oferta é necessária?** Ou o SMS funciona como lembrete puro, sem custo de bônus? → célula A vs B.
3. **Quanto custa um depósito incremental por SMS**, e isso cabe no CAC de reativação? → custo/conversão incremental.

Tudo que não responde a essas três perguntas fica fora do piloto.

---

## 2. Estrutura — duas faixas independentes

### Faixa 1 — Reativação `At Risk` (o experimento)

Público: **`[RFM] 🔶 At Risk`** (segmento 1956) — depositou nos últimos 90 dias e **não** depositou nos últimos 30. Tamanho bruto: **12.786**.

Por que este e não `Hibernating` (31.285): dormência de 30–90 dias é onde a reativação ainda é barata. Hibernating de 90–180 dias precisa de oferta muito maior para mover e ia contaminar o teste com custo de bônus. Se Wave 0 der certo, Hibernating é a Wave 1.

**Desenho:**

| Célula | n | O que recebe | Pergunta que responde |
|---|---|---|---|
| **A — oferta** | 4.000 | SMS com freebet/rodadas, condição explícita | SMS + incentivo move a agulha? |
| **B — lembrete** | 4.000 | SMS sem oferta, só chamada de volta | O incentivo é necessário? |
| **C — holdout** | 2.500 | **nada** | Quanto voltaria sozinho? |

Sobra (~2.000 após filtros) fica intocada como reserva.

**Alocação:** aleatória e persistente. Gravar o atributo `sms_wave0_cell` = `a` / `b` / `c` no perfil **antes** do disparo, para que a leitura seja auditável depois. Não usar segmento dinâmico que muda de tamanho durante a leitura.

### Faixa 2 — Recuperação de depósito falho (a aposta segura)

Gatilho: `DepositFailedEvent` **sem** `DepositSuccessEvent` nos 30 minutos seguintes.

Roda em paralelo, contínuo, começando hoje. Mensagem de **serviço puro** — sem oferta, sem bônus, sem acento — logo:

- não é peça publicitária → não carrega advertência;
- 1 segmento GSM-7 → **1/3 do custo** do SMS promocional;
- é o ponto de maior intenção do funil inteiro.

Já existe base pronta: campanha 527 (`[MK] Flow Recovery DepositFailed — Email`, draft) e segmento 1886. É acrescentar o passo de SMS.

Esta faixa **não** tem holdout na Wave 0 — o volume diário é baixo demais para gerar leitura em uma semana. Ela entra porque é barata, é útil ao jogador e gera aprendizado operacional (entrega, latência, opt-out) sem risco reputacional.

---

## 3. Filtros e supressões — aplicar a **todas** as faixas

Nenhum SMS sai sem passar por esta lista. Sugestão: montar um segmento `[SMS] Elegível — Base` e usar como pré-condição de toda campanha de SMS, agora e no futuro.

**Inclusão:**
- `Phone` existe e casa com `^\+55\d{2}9\d{8}$` (celular brasileiro, E.164)
- `PlayerStatusString` = `Active`

**Exclusão (bloqueantes):**
- `IsBlocked` = `true`
- autoexcluídos SIGAP (usar a lista que alimentou `18-12 - Comunicado - Autoexclusão - SIGAP`)
- `Blocked Players - Beneficiary Programs` — recebedores de Bolsa Família/BPC (Portaria SPA/MF 2.217/2025 + IN SPA/MF 22/2025)
- `Blocked player list due to social Beneficiary validation`
- `sms_optout` = `true` **e** membros de `[SUP] SMS Opt-out Zenvia` (2011)
- quem recebeu qualquer SMS de marketing nos últimos 7 dias
- menores de 18 (checar `Birthday`; deve ser redundante com KYC, verificar mesmo assim)

**Frequência:** máximo **1 SMS de marketing por pessoa a cada 7 dias** durante o piloto. Bem abaixo do teto de mercado (7/semana) — é piloto, não é volume.

**Janela de envio:** seg–sáb, 09h–21h. Nunca domingo, nunca feriado, nunca depois das 21h. Disparo da Faixa 1: **hoje, 19h**.

---

## 4. Mensagens

### Regras que valem para todo texto

- Advertência do Ministério da Fazenda em **toda** mensagem com oferta, rotacionando as três frases entre células/ondas.
- Condição da oferta **dentro do SMS** — se exige depósito, dizer que exige depósito. Omitir é art. 37 do CDC (há reclamação pública contra concorrente por exatamente isso).
- Nada de "ganhe", "renda extra", "dinheiro fácil", "garantido", "investimento".
- Opt-out visível: `SAIR`.
- `+18`.
- **Link em domínio próprio da Aposta1** (ex.: `a1.bet.br/...`). Nunca bit.ly ou encurtador genérico: a Zenvia bloqueia por análise antispam e as operadoras filtram — o canal está contaminado por bets ilegais que disparam SMS com malware.
- UTM em todo link: `?utm_source=sms&utm_medium=crm&utm_campaign=wave0&utm_content=<celula>`.

### Célula A — com oferta (peça publicitária)

```
Aposta1: seu Freebet de R$20 vence amanha. Ative com deposito de R$20: a1.bet.br/fb
+18 Ministério da Fazenda adverte: Aposta não é investimento. SAIR p/ nao receber
```
`UCS-2 · 165 caracteres · 3 segmentos`

> **Sobre o custo da honestidade:** tirando "com deposito de R$20" a mensagem cai para 134 caracteres = **2 segmentos** (-33% de custo). Não faça isso se a oferta tiver condição — é exatamente a prática que gerou reclamação pública contra concorrente. Se o time de bônus liberar um freebet **sem** condição de depósito, aí sim a versão de 2 segmentos é honesta e mais barata.

### Célula B — sem oferta (ainda é peça publicitária: promove a marca)

```
Aposta1: os jogos de hoje ja estao no ar: a1.bet.br/j
+18 Ministério da Fazenda adverte: Aposta não é investimento. SAIR p/ parar
```
`UCS-2 · 129 caracteres · 2 segmentos`

### Faixa 2 — serviço (não é peça publicitária)

```
Aposta1: seu deposito nao foi concluido. Nada foi cobrado. Tentar de novo: a1.bet.br/d
```
`GSM-7 · 86 caracteres · 1 segmento`

Sem acentos de propósito — é o que mantém em GSM-7 e em 1 segmento. Não incluir oferta nesta mensagem: no momento em que entra bônus, ela vira publicidade, exige advertência e triplica de preço.

### Aprovação

As três peças precisam de OK de compliance/jurídico **antes** do disparo. Reservar 16h–17h hoje.

---

## 5. Medição

### Métrica primária

**Taxa de `DepositSuccessEvent` em 72h após o disparo**, por célula.

Lift incremental = `taxa(A) − taxa(C)` e `taxa(B) − taxa(C)`.

Esta métrica funciona mesmo indo por webhook, porque não depende de métrica de canal — depende de evento que já entra no Customer.io.

### Métricas secundárias

| Métrica | Como obter | Alvo do piloto |
|---|---|---|
| Taxa de entrega | callback de status da Zenvia | ≥ 95% |
| CTR | UTM no GA/BI, por `utm_content` | 3–8% (meta interna conservadora; ignorar os 20% de material de fornecedor) |
| Opt-out | inbound `SAIR` → atributo `sms_optout` | **< 1%** |
| Custo por depósito incremental | custo da célula ÷ depósitos incrementais | < CAC de reativação atual |
| GGR/NGR em 7d por célula | BI | informativo na Wave 0 |

### O que este desenho consegue e não consegue detectar

Assumindo taxa base de reativação em 72h de ~4% na `At Risk`:

- **A ou B vs holdout** (4.000 vs 2.500): detecta lift de **~1,4 p.p. ou mais** (95%, poder 80%). Ou seja, detecta um efeito grande (+35% relativo); **não** detecta um efeito pequeno.
- **A vs B** (4.000 vs 4.000): detecta diferença de **~1,2 p.p.**.

Isso é uma limitação real e deliberada — Wave 0 é para separar "funciona muito" de "não funciona", não para calibrar fino. Se o resultado vier ambíguo, a resposta é aumentar n na Wave 1, não decidir no achismo.

### Leitura

- **D+1 (29/07, manhã):** entrega, opt-out, reclamações, qualquer bloqueio de operadora. Só saúde operacional.
- **D+3 (31/07):** métrica primária fecha.
- **03/08:** decisão go/no-go da Wave 1.

### Kill switch

Parar tudo imediatamente se, a qualquer momento:
- opt-out > 2%
- taxa de entrega < 90%
- qualquer bloqueio por antispam da Zenvia ou de operadora
- qualquer reclamação de Procon/Reclame Aqui ligada ao disparo

---

## 6. Orçamento

Premissa: **R$ 0,09 por segmento** — *confirmar a tarifa real do contrato Zenvia e se a cobrança é por segmento ou por mensagem. É a maior incerteza deste número.*

| Faixa | Envios | Segmentos/msg | Segmentos | Custo |
|---|---|---|---|---|
| Célula A | 4.000 | 3 | 12.000 | R$ 1.080 |
| Célula B | 4.000 | 2 | 8.000 | R$ 720 |
| Célula C (holdout) | 0 | — | 0 | R$ 0 |
| Faixa 2 (7 dias, est. 500/dia) | 3.500 | 1 | 3.500 | R$ 315 |
| **Total** | | | **23.500** | **~R$ 2.115** |

Custo do bônus da célula A entra por fora (4.000 freebets de R$20 com resgate parcial — pedir ao time de bônus a estimativa de take-up e provisionar).

Se o orçamento apertar: cortar a célula A para 3.000 e a B para 3.000 mantém o desenho de pé, com MDE um pouco pior (~1,5 p.p.).

---

## 7. Riscos e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Operadora/Zenvia bloqueia por antispam | Média | Link em domínio próprio, remetente homologado da marca, volume baixo, aquecimento gradual |
| Opt-out alto queima a base | Média | Cap de 1 SMS/7d, holdout, kill switch em 2% |
| Reclamação de publicidade enganosa | Baixa se copy aprovada | Condição da oferta no corpo do SMS, advertência obrigatória, aprovação jurídica antes do disparo |
| Telefone inválido / DDI errado | **Alta** — existe o segmento `Check TELEFONE DDI` monitorando isso | Regex E.164 estrito no filtro; medir taxa de rejeição no D+1 |
| Opt-out não volta para o Customer.io | **Alta hoje** — o segmento de opt-out tem 0 pessoas | Bloqueador B5: resolver **antes** do disparo (ver runbook) |
| Métrica de entrega/clique não existe no Customer.io | Alta | Callback de status da Zenvia → evento; UTM para clique. Resolver de vez conectando provedor nativo no roadmap |

---

## 8. Roadmap pós-piloto (não é para hoje)

**Wave 1 (semana de 04/08), se Wave 0 for verde:**
- Escalar o vencedor para `Hibernating` (31.285) com holdout menor
- SMS pré-jogo em evento relevante — janela de 2–4h antes, alta intenção e efêmera
- Alerta de liquidação de aposta (`BETEVENT`) — serviço, alto valor percebido, custo de 1 segmento

**30 dias — infraestrutura:**
- **Conectar provedor de SMS nativo no Customer.io.** Resolve de uma vez: métrica de entrega e clique nativa, gestão de assinatura, respeito automático a `send_to_unsubscribed`, e frequency cap por canal. Hoje nada disso existe.
- Criar **subscription channel de SMS** e um **subscription topic de marketing** (hoje só existe `Atualizações da Conta`, e zero canais). É o que dá uma central de preferências de verdade em vez de opt-out binário.
- Guardar credencial da Zenvia fora do corpo do template.
