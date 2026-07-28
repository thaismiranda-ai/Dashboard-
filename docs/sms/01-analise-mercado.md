# SMS em casas de apostas — análise de mercado e regulatória

**Data:** 28/07/2026 · **Autor:** CRM Aposta1 · **Escopo:** o que outras casas fazem com SMS, o que a regra brasileira permite, e o que dá para copiar sem risco.

---

## 1. Por que SMS, e por que agora

SMS não compete com e-mail — compete com push. É o único canal que alcança o jogador que:

- desinstalou o app (perdemos push);
- nunca abriu e-mail (temos `Hard bounced Email Users who deposited at least once` e `Inativos - Sem abertura 90 dias` na base);
- não está logado.

Em contrapartida é o canal mais caro por mensagem, o mais intrusivo e o de maior risco regulatório. Por isso a tese do piloto não é "ligar SMS", é **descobrir em quais 2 ou 3 gatilhos o SMS paga o próprio custo** — e desligar o resto.

### Benchmarks públicos (e o quanto confiar neles)

| Métrica | Número divulgado | Fonte | Leitura |
|---|---|---|---|
| Taxa de abertura SMS | ~90%+ | fornecedores de SMS iGaming | Inflado e pouco útil: "abertura" de SMS é praticamente "entrega". Ignorar. |
| CTR SMS | >20% | fornecedores | Números de vendor, sem holdout. Usar como teto teórico, não como meta. |
| Retenção D30 iGaming | 15–25% média / 30–40% best-in-class | Xtremepush | Referência de retenção, não de SMS. |
| Lift de SMS sobre e-mail+push | +25% engajamento, +15% depósitos | case publicado | Sem grupo de controle divulgado. |

**Conclusão prática:** nenhum desses números serve de meta. O piloto precisa de **holdout próprio** — é a única forma de saber quanto do depósito pós-SMS aconteceria de qualquer jeito. Todo o desenho da seção de piloto gira em torno disso.

---

## 2. O que as casas fazem hoje no Brasil

Levantamento a partir de imprensa setorial, material de fornecedores de CRM de iGaming e reclamações públicas.

### 2.1 O padrão dominante: "texto-foguete"

A imprensa batizou de **"texto-foguete"** a prática corrente: mensagens curtas e frequentes (SMS e e-mail) com bônus, rodadas grátis e missões, disparadas para a base cadastrada. Bet365 e KTO são citadas nominalmente pelos clubes de fidelidade que alimentam essas mensagens — quem aposta mais recebe mais.

Duas características importantes:

1. **Promoção só vai para cadastrado.** Não é escolha de marketing, é a Lei 14.790/2023: oferta promocional não pode ser dirigida a público não cadastrado. Isso empurra o setor inteiro para CRM em vez de mídia de aquisição promocional.
2. **A frequência é alta e o conteúdo é quase sempre bônus.** É o ponto fraco do mercado: todo mundo manda a mesma coisa, então a mensagem de bônus virou ruído. Espaço competitivo real está em SMS *não promocional* (serviço, resultado, conta) — que ninguém está usando bem.

### 2.2 Casos de uso mapeados (ordenados por sinal de intenção)

| # | Caso de uso | Gatilho | Intenção | Temos o evento? |
|---|---|---|---|---|
| 1 | **Falha/abandono de depósito** | depósito falhou e não houve sucesso em X min | Altíssima | ✅ `DepositFailedEvent` + `DepositSuccessEvent` |
| 2 | **Falha de saque / problema na conta** | evento de saque falho | Alta (serviço) | ✅ `WithdrawFailedEvent` (campanha 554 já roda) |
| 3 | **Pré-jogo de evento relevante** | janela de 2–4h antes do jogo | Alta e efêmera | ✅ já fazemos por e-mail/in-app (Brasil x Japão, Fla x Pal) |
| 4 | **Liquidação de aposta (bet settlement)** | aposta resolvida | Média-alta, alto valor percebido | ✅ `BETEVENT` |
| 5 | **Reativação por recência** | dormência 30/60/90/120d | Média | ✅ RFM já classificado |
| 6 | **Marco de fidelidade / VIP** | mudança de tier | Média | Parcial |
| 7 | **Aniversário** | data | Baixa-média | ✅ segmentos `[MK] Birthday` |
| 8 | **Bônus/missão semanal em massa** | calendário | Baixa | ✅ (é o que já fazemos por e-mail) |

O consenso dos fornecedores de CRM de iGaming, e é consistente com o nosso próprio funil: **1, 2 e 3 pagam o SMS; 8 não paga** — massa promocional por SMS custa caro, gera opt-out e canibaliza o e-mail que já entrega isso de graça.

### 2.3 O que NÃO copiar

O mercado brasileiro de SMS de apostas está contaminado, e isso é um ativo para quem fizer diferente:

- **Bets ilegais disparam SMS promocional com links de malware** para números aleatórios. Resultado: operadoras filtram agressivamente, e o consumidor já trata SMS de aposta com link como golpe. Consequência direta para nós: link encurtado genérico (bit.ly e similares) é péssima ideia — sobe risco de bloqueio na operadora e de o jogador não clicar.
- **"Grátis" que não é grátis.** Há reclamação pública contra operadora por SMS de rodadas grátis que exigiam depósito para liberar. Isso é publicidade enganosa (art. 37 do CDC) — a condição precisa estar **na própria mensagem**, não só na landing page.
- **Disparo para não cadastrado.** Além de vedado pela Lei 14.790, é violação de LGPD.
- **Alta frequência indiscriminada.** Procons de todo o país já estão monitorando o setor por superendividamento; volume de SMS promocional é exatamente o tipo de prova que aparece em processo.

---

## 3. Regulatório — o que muda o texto do nosso SMS

### 3.1 Advertência obrigatória (mudou há 11 dias)

A **Portaria SPA/MF nº 1.964/2026** (publicada em 10/07, **em vigor desde 17/07/2026**) alterou a Portaria SPA/MF nº 1.231/2024 e tornou obrigatória, em peça publicitária de aposta, uma destas três frases:

- `Ministério da Fazenda adverte: Apostar pode causar dependência.`
- `Ministério da Fazenda adverte: Apostar faz você perder dinheiro.`
- `Ministério da Fazenda adverte: Aposta não é investimento.`

Requisitos de forma: a advertência deve ocupar **no mínimo 10% do tamanho ou comprimento da peça**, em disposição horizontal, clara, legível e proporcional aos demais elementos.

A **Portaria Interministerial MF/SECOM/MJSP nº 73/2026** estendeu a responsabilidade a toda a cadeia de veiculação e formalizou a atuação conjunta com a Senacon. Multas divulgadas chegam a **R$ 14 milhões** para publicidade irregular.

> **Impacto direto no nosso SMS:** um SMS com oferta é peça publicitária. A frase precisa estar dentro do SMS. Em uma mensagem de ~190 caracteres, a frase (57–64 caracteres) representa ~30% — folgadamente acima do mínimo de 10%. O custo não é jurídico, é de caracteres — ver seção 3.4.

### 3.2 Restrições de conteúdo (Portaria 1.231/2024, mantidas)

Vedado, entre outros:

- apresentar aposta como forma de obter renda, sucesso financeiro ou como investimento;
- promessa de ganho fácil ou certo;
- elementos que atraiam menores de 18 anos;
- estimular aposta compulsiva ou apresentar o jogo como prioridade de vida;
- oferta promocional a público não cadastrado.

### 3.3 LGPD, Anatel e prática de mercado

- **Base legal:** consentimento prévio, livre, informado e revogável — ou legítimo interesse com opt-out fácil e documentado. Sanção da ANPD: até 2% do faturamento, teto de R$ 50 mi por infração.
- **Opt-out obrigatório e funcional** em toda mensagem de marketing.
- **Janela de envio** (prática consolidada de mercado, não lei federal específica): seg–sáb, 9h–22h. Limite prático usado pelo mercado: **7 mensagens/semana** — vamos operar muito abaixo disso.
- **Short code homologado** junto a Anatel/operadoras é o que separa "SMS de empresa" de "SMS bloqueado como spam". A Zenvia faz análise antispam própria e bloqueia conteúdo suspeito — inclusive link encurtado desconhecido.

### 3.4 A pegadinha técnica que ninguém lembra: encoding

Este é o achado mais operacional da análise.

SMS usa GSM-7 (160 caracteres/segmento). **O alfabeto GSM-7 não contém `ã`, `ê`, `â`, `ô`, `í`, `ú`, `á`, `ó`.** Basta um desses caracteres para a mensagem inteira virar UCS-2 — e cair para **70 caracteres por segmento (67 quando concatenada)**.

As três frases obrigatórias contêm `ê` (dependência, você) ou `ã` (não). **Toda advertência força UCS-2.** Ou seja:

| Tipo de SMS | Encoding | Caracteres úteis | Segmentos típicos | Custo relativo |
|---|---|---|---|---|
| Serviço, sem acento e sem oferta | GSM-7 | 160 | **1** | 1x |
| Marketing com advertência | UCS-2 | 67/segmento | **3** | **3x** |

**Consequências para o piloto:**

1. Um SMS promocional custa ~3x o preço de tabela por mensagem. O orçamento tem que ser calculado em segmentos, não em disparos.
2. SMS de **serviço puro** (sem oferta, sem bônus) — "seu depósito não foi concluído" — não é peça publicitária, não carrega advertência, e escrito sem acento cabe em **1 segmento**. É 3x mais barato e tem a maior intenção do funil. É por isso que o piloto trata isso como faixa separada.
3. Remover os acentos da frase oficial para economizar caracteres **não é opção** — alteraria o texto legal exigido.

---

## 4. Diagnóstico do nosso setup (Customer.io, workspace 112427)

Levantado direto na API em 28/07. Isto é o que existe hoje, não o que deveria existir.

### O que já está pronto

- **Base e eventos:** `DepositSuccessEvent`, `DepositFailedEvent`, `WithdrawFailedEvent`, `BETEVENT`, `BonusActivatedsEvent`, `CreateBonusRequestEvent`.
- **Atributo `Phone` em E.164** (`+55DDD9XXXXXXXX`) confirmado em perfil de amostra.
- **RFM já classificado e rodando** (campanha 541 `[SYS] Classifier RFM`), com segmentos dinâmicos prontos:

  | Segmento | ID | Definição | Tamanho |
  |---|---|---|---|
  | `[RFM] Base · Já depositou` | 1941 | — | **153.688** |
  | `[RFM] 🔶 At Risk` | 1956 | depositou ≤90d, **não** depositou ≤30d | **12.786** |
  | `[RFM] ⚠️ Need Attention` | 1955 | — | **10.478** |
  | `[RFM] 😴 Hibernating` | 1957 | depositou ≤180d, **não** depositou ≤90d | **31.285** |

- **Fluxo de recuperação de depósito falho meio construído:** campanha 527 (`[MK] Flow Recovery DepositFailed — Email`, draft) e segmento 1886.
- **Compliance de supressão já existe na base:** `Blocked Players - Beneficiary Programs` (Bolsa Família/BPC), `18-12 - Comunicado - Autoexclusão - SIGAP`, atributo `IsBlocked`, `PlayerStatus`.
- **Teste de conectividade com a Zenvia funcionando** (campanha 558 `[TESTE] Zenvia SMS`, draft).

### O que está quebrado ou faltando — bloqueadores do piloto

| # | Problema | Evidência | Severidade |
|---|---|---|---|
| **B1** | **Nenhum provedor de SMS conectado no Customer.io.** `GET /sms_providers` retorna `{"connections":[]}` | A ação nativa `twilio_action` da campanha 558 **não envia**. O único caminho que funciona hoje é o `webhook_action` chamando `api.zenvia.com` | 🔴 Bloqueia |
| **B2** | **Token da API Zenvia em texto claro** no header do template 6967 | Visível para qualquer pessoa com acesso ao workspace, e sai em qualquer export/duplicação de template | 🔴 Segurança |
| **B3** | **Template hardcoded:** `"to"` fixo num número de teste e texto fixo de teste | Não há Liquid, não personaliza, não envia para a base | 🔴 Bloqueia |
| **B4** | **Sender ID `pix.na.hora`** no template | Remetente não é da marca Aposta1 e sugere serviço financeiro numa mensagem de aposta — risco de art. 37 do CDC e de bloqueio antispam | 🔴 Bloqueia |
| **B5** | **Opt-out de SMS nunca foi capturado.** Segmento `[SUP] SMS Opt-out Zenvia` (2011) tem **0 pessoas** | Não existe caminho de volta de "SAIR" da Zenvia para o Customer.io. Sem isso não se dispara volume | 🔴 Bloqueia |
| **B6** | Indício de inconsistência de DDI — segmento `Check TELEFONE DDI` (1766) monitora `PhoneDDI` != `+55` | Precisa de filtro de validade de telefone antes do disparo | 🟠 Alto |
| **B7** | Sem provedor nativo, **não há métrica de entrega/clique dentro do Customer.io** | Nenhum `send_to_unsubscribed`, nenhum controle nativo de assinatura, nenhum relatório de canal | 🟠 Alto |
| **B8** | Só existe 1 subscription topic (`Atualizações da Conta`) e **0 subscription channels** | Não há tópico de marketing nem canal SMS na central de preferências | 🟠 Alto |

**Nota histórica:** existe o segmento estático `Free spin - Fortune Tiger - SMS 21/07` (150 pessoas). Já houve um disparo pequeno de SMS em 21/07 — vale puxar o resultado dele com a Zenvia antes do piloto, é a única baseline real que temos.

### Decisão de arquitetura

Conectar provedor nativo (Twilio) exige conta, homologação de remetente e dias de prazo. **Para hoje, o piloto vai por webhook → Zenvia.** Provedor nativo entra no roadmap de 30 dias, porque ele resolve B5, B7 e B8 de uma vez.

---

## 5. Síntese — as cinco decisões que saem desta análise

1. **Não usar SMS para massa promocional.** É o que o mercado faz e é o pior uso do canal. E-mail já cobre.
2. **Priorizar gatilho de alta intenção** (falha de depósito) e **reativação com holdout** (At Risk). Nessa ordem de confiança.
3. **Separar mensagem de serviço de mensagem publicitária** — muda o texto, muda o custo (1 vs 3 segmentos) e muda a obrigação legal.
4. **Advertência do Ministério da Fazenda dentro do SMS promocional**, rotacionando as três frases. Não negociável desde 17/07.
5. **Nada dispara antes de fechar B2, B4 e B5** (token, remetente e opt-out). São horas de trabalho, não dias.

---

## Fontes

- [Bets usam 'texto-foguete' e promoções restritas para reter jogadores — Jornal de Brasília](https://jornaldebrasilia.com.br/noticias/economia/bets-usam-texto-foguete-e-promocoes-restritas-para-reter-jogadores-e-captar-clientes-fieis/)
- [Sites de apostas usam "textos-foguete" e promoções para reter jogadores — BNLData](https://bnldata.com.br/sites-de-apostas-usam-textos-foguete-e-promocoes-para-reter-jogadores/)
- [Portarias SPA/MF nº 1.964/2026 e Interministerial nº 73/2026 — GSGA](https://gsga.com.br/pt/informativo/portarias-spamf-n-19642026-e-interministerial-n-732026-novas-regras-para-a-publicidade-de-apostas-de-quota-fixa)
- [Governo amplia restrições à publicidade de bets e exige alertas — Migalhas](https://www.migalhas.com.br/quentes/460340/governo-amplia-restricoes-a-publicidade-de-bets-e-exige-alertas)
- [Começam a vigorar hoje regras que exigem alertas em anúncios de bets — Agência Brasil](https://agenciabrasil.ebc.com.br/politica/noticia/2026-07/comecam-vigorar-hoje-regras-que-exigem-alertas-em-anuncios-de-bets)
- [Publicidade de Apostas: novidades da Portaria SPA/MF n. 1.231/2024 — Baptista Luz](https://baptistaluz.com.br/publicidade-de-apostas-novidades-da-portaria-spa-mf-n-1-231-2024/)
- [Portaria SPA/MF Nº 1.231 DE 31/07/2024 — LegisWeb](https://www.legisweb.com.br/legislacao/?id=462714)
- [Com multas de até R$ 14 milhões, novas regras proíbem publicidade de bets com promessa de ganho fácil — Gaz](https://www.gaz.com.br/com-multas-de-ate-r-14-milhoes-novas-regras-proibem-publicidade-de-bets-com-promessa-de-ganho-facil/)
- [Bets não autorizadas enviam SMS de promoções com links que contêm malwares — Canaltech](https://canaltech.com.br/seguranca/bets-nao-autorizadas-enviam-sms-de-promocoes-com-links-que-contem-malwares/)
- [Superendividamento e apostas online preocupam Procons de todo o país — PROCON-SP](https://www.procon.sp.gov.br/superendividamento-e-apostas-online-preocupam-procons-de-todo-o-pais/)
- [SMS Regulations Brazil: LGPD Guide — Mailpro](https://www.mailpro.com/faq/sms-regulations-brazil)
- [Conheça as regras para envio de SMS Marketing — Zenvia](https://zenvia.com/blog/regras-envio-sms/)
- [Bloqueio de SMS por análise de spam — Zenvia](https://zenvia.movidesk.com/kb/pt-br/article/569712/bloqueio-de-sms-por-analise-de-spam)
- [Casino SMS Marketing That Improves Retention — OptiKPI](https://www.optikpi.com/casino-sms-marketing/)
- [Guide to player engagement for iGaming and casinos — Customer.io](https://customer.io/learn/lifecycle-marketing/igaming-customer-engagement)
- [Gamification Benchmarks 2026 — Xtremepush](https://www.xtremepush.com/blog/gamification-benchmarks-2026-whats-a-good-retention-rate-engagement-score-and-tier-progression)
- [iGaming Player Reactivation: 7 Strategies + Churn Timing — Intarget](https://intarget.space/blog/7-player-reactivation-strategies-for-igaming/)
