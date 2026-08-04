# AP1-1991 — Comunicação CRM e página promocional · Boost Semanal

- **Jira:** [AP1-1991](https://aposta1.atlassian.net/browse/AP1-1991) · Epic [AP1-1989](https://aposta1.atlassian.net/browse/AP1-1989) — Boost Semanal - Ap1
- **Briefing:** [Boost Semanal Aposta1 - Sportsbook - Ago/26](https://docs.google.com/document/d/1zncclCbk_88Kx7TatObELIAkmLq9mWZhn7KgFonyuvQ/edit)
- **Workspace Customer.io:** 112427

Toda a copy é reproduzida **integralmente** a partir do briefing aprovado, conforme pedido no ticket.

---

## Status por item do escopo

| # | Item do escopo | Status | Onde |
|---|---|---|---|
| 1 | Criar a Página Promocional no Contentful | **Conteúdo pronto — publicação pendente** | [`01-pagina-promocional.md`](./01-pagina-promocional.md) · [`.html`](./01-pagina-promocional.html) |
| 2 | Configurar o E-mail de lançamento (segmento Sports) | **Configurado em rascunho** | Customer.io one-time send **3694** · [`02-email-lancamento.md`](./02-email-lancamento.md) |
| 3 | Configurar o Banner da Área de Promoções | **Conteúdo pronto — publicação pendente** | [`03-banners.md`](./03-banners.md) |
| 4 | Configurar o In-App de lançamento | **Configurado em rascunho** | Customer.io one-time send **3695** · [`04-in-app-lancamento.md`](./04-in-app-lancamento.md) |
| 5 | CTAs e links para a Página Promocional | **Aplicado nas 4 peças** | [`00-links-e-utms.md`](./00-links-e-utms.md) |

### O que ficou fora e por quê

**Contentful (itens 1 e 3).** Não há conector do Contentful disponível nesta sessão — só Jira,
Customer.io, Google Workspace e Slack. Então a página promocional e os banners estão entregues como
conteúdo final pronto para publicação (copy + HTML + metadados + specs), e não publicados. Quem tiver
acesso ao CMS publica direto a partir destes arquivos.

**Peças em rascunho, não disparadas.** O e-mail e o in-app estão configurados e apontando para a
audiência correta, mas **nenhum dos dois foi agendado ou enviado** — 24.850 jogadores reais receberiam
a peça. O disparo depende das artes finais do Design e da URL definitiva da página. Agendamento é
decisão de quem toca a campanha.

**Item 5 do briefing (comunicação de concessão do Boost).** O briefing traz um segundo e-mail — "Seu
Boost Semanal já está disponível", disparado toda segunda a partir da lista da Altenar (Ivan). Isso
**não está no escopo da AP1-1991**, que cobre só as peças de lançamento. Vale abrir um ticket próprio:
é um fluxo recorrente com dependência de dado externo, não uma peça de lançamento.

---

## Ativos criados no Customer.io

| Tipo | ID | Nome | Estado |
|---|---|---|---|
| One-time send | 3694 | `[Esportes] E-mail - Lançamento Boost Semanal` | rascunho |
| Template (email) | 7062 | `[Esportes] Boost Semanal - Lançamento` | — |
| One-time send | 3695 | `[Esportes] In-App - Lançamento Boost Semanal` | rascunho |
| Template (in-app) | 7063 | `[Esportes] In-App - Lançamento Boost Semanal` | — |

Audiência das duas peças: **24.850 perfis** (segmento 1831 `[AUX] Apostou esportes (lifetime)` menos
as supressões regulatórias e de entregabilidade — detalhe em [`02-email-lancamento.md`](./02-email-lancamento.md)).

---

## Premissa a confirmar

A URL da página promocional foi definida como:

```
https://www.aposta1.bet.br/promocoes/boost-semanal
```

Seguindo o padrão `/promocoes/<slug>` já usado no site, com o domínio `aposta1.bet.br` das comunicações
atuais. **Se o slug publicado no Contentful for outro, atualizar os 4 CTAs** — a lista exata dos pontos
a alterar está em [`00-links-e-utms.md`](./00-links-e-utms.md).

---

## Checklist para colocar no ar

1. [ ] Publicar a página promocional no Contentful e confirmar a URL final
2. [ ] Design entrega as artes (banner da página, tabela de faixas em imagem, banner do e-mail, banner do in-app, banner da Área de Promoções)
3. [ ] Substituir `BANNER_EMAIL_URL` (template 7062) e `BANNER_INAPP_URL` (template 7063)
4. [ ] Publicar o banner da Área de Promoções
5. [ ] Se a URL mudou, atualizar os CTAs das 4 peças
6. [ ] Enviar teste do e-mail e do in-app
7. [ ] Agendar e-mail e in-app
