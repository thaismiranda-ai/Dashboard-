# E-mail de lançamento — Boost Semanal Aposta1 (AP1-1991)

**Configurado no Customer.io** · workspace 112427
One-time send **3694** — `[Esportes] E-mail - Lançamento Boost Semanal` · template **7062** · **rascunho**

HTML-fonte do corpo: [`02-email-lancamento.html`](./02-email-lancamento.html)

---

## Conteúdo (fiel ao briefing)

| Campo | Conteúdo |
|---|---|
| Assunto | Conheça o novo Boost Semanal Aposta1 |
| Preheader | Jogadores elegíveis podem receber automaticamente um Boost toda segunda-feira. |
| Banner (arte) | Toda semana pode ter um Boost esperando por você. / Conheça o novo Boost Semanal Aposta1 |
| CTA | **Conhecer a promoção** |

Corpo: título "Boost Semanal Aposta1", os três parágrafos de abertura, o bloco **Como funciona**
(4 critérios), o bloco **Boost disponível** (35% / 50% / 100%) e a linha "O Boost poderá ser utilizado
em uma única aposta múltipla elegível."

Adicionei ao rodapé do corpo a linha legal obrigatória ("maiores de 18 anos" + advertência do
Ministério da Fazenda) com link para a página da promoção — não estava no texto do briefing do e-mail,
mas consta nos Termos e é padrão regulatório das peças da casa.

## Configuração aplicada

| Item | Valor |
|---|---|
| Canal | `email` |
| Layout | 27 — `LO - 1Real` (mesmo dos e-mails de Esportes) |
| Editor / preprocessor | `html` / `premailer` |
| Remetente | identidade 5 (mesma dos e-mails de Esportes) |
| Personalização | `{% if customer.FirstName %}Fala, {{customer.FirstName}}{% else %}Oi{% endif %}!` |
| Link tracking | ativo |
| Dedupe / limites de mensagem | ativos |
| Enviar para não-inscritos | não |
| Conversão | evento `BetEvent` por clique, janela de 7 dias |

## Audiência — **24.850 perfis**

**Incluir**

| ID | Segmento |
|---|---|
| 1831 | `[AUX] Apostou esportes (lifetime)` — 36.908 perfis, o segmento Sports do workspace (≥ 1 `BetEvent`) |

**Excluir**

| ID | Segmento |
|---|---|
| 1169 | `18-12 - Comunicado - Autoexclusão - SIGAP` |
| 1837 | `Nunca Deve Receber Comunicação Promocional` |
| 1896 | `[SUP] SIGAP - Novo Desenrola Brasil` |
| 1897 | `Bounce/Falha - Excluir de Marketing` |
| 1926 | `[SUP] Hard Bounce — Supressão Permanente` |

Mesmo conjunto de supressões dos disparos de Esportes já em produção, acrescido do 1837 — que a
descrição do próprio segmento marca como **exclusão obrigatória em campanhas de bônus/odds boost**,
o que é exatamente o caso desta peça.

## Pendências

- [ ] Substituir `BANNER_EMAIL_URL` pela arte final (Design)
- [ ] Confirmar a URL da página promocional após publicação no Contentful
- [ ] Enviar teste antes de agendar
- [ ] Agendar/disparar (a peça está em **rascunho**, não agendada)
