# In-App de lançamento — Boost Semanal Aposta1 (AP1-1991)

**Configurado no Customer.io** · workspace 112427
One-time send **3695** — `[Esportes] In-App - Lançamento Boost Semanal` · template **7063** · **rascunho**

---

## Conteúdo (fiel ao briefing)

| Campo | Conteúdo |
|---|---|
| Banner (arte) | **BOOST SEMANAL APOSTA1** |
| Texto | Agora, jogadores elegíveis podem receber automaticamente um **Boost** para utilizar em uma aposta múltipla. |
| Texto de apoio | Não é necessário ativar a promoção. |
| CTA | **Clique e Saiba Mais** |

## Configuração aplicada

| Item | Valor |
|---|---|
| Canal | `in_app` |
| Formato | Modal, centralizado, largura 420px |
| Prioridade | 10 |
| Dismiss ao clicar fora | desativado (`exit_click: false`) |
| Expiração | relativa, 7 dias (604800s) |
| Comportamento do CTA | `openUrl` + `new-tab` |
| Destino do CTA | `https://www.aposta1.bet.br/promocoes/boost-semanal?utm_source=customer.io&utm_medium=in_app&utm_campaign=boost_semanal&utm_content=lancamento_sports` |
| Audiência | 24.850 perfis |

### Route rules

| Plataforma | Regra |
|---|---|
| web | contém `https://www.aposta1.bet.br/esportes` |
| ios | contém `https://app.aposta1.bet.br/esportes` |
| android | contém `https://app.aposta1.bet.br/esportes` |

Mesmo padrão dos in-apps de Esportes já em produção no workspace.

## Markup (carta_content)

```html
<x-base><x-message display-type='modal' display-modal-position='center' :display-max-width='420' padding='24px' background='#ffffff' border-radius='16px' font-family='Helvetica' :font-size='16' :line-height='1.5' color='#272C33' name='Step 1'><x-image src='BANNER_INAPP_URL' border-radius='12px' /><x-spacer></x-spacer><x-heading-2 text-align='center' color='#7010FF' :font-size='23' margin='16px 0px 8px'>BOOST SEMANAL APOSTA1</x-heading-2><x-spacer></x-spacer><x-paragraph text-align='center' margin='0px 0px 12px' :font-size="17">Agora, jogadores elegíveis podem receber automaticamente um <strong>Boost</strong> para utilizar em uma aposta múltipla.</x-paragraph><x-paragraph text-align='center' margin='0px 0px 16px' :font-size="15">Não é necessário ativar a promoção.</x-paragraph><x-spacer></x-spacer><x-cta behavior='openUrl' href='https://www.aposta1.bet.br/promocoes/boost-semanal?utm_source=customer.io&utm_medium=in_app&utm_campaign=boost_semanal&utm_content=lancamento_sports' :new-tab='true' background='#00DA6D' color='#ffffff' align='center' :font-size="17"><strong>Clique e Saiba Mais</strong></x-cta></x-message></x-base>
```

> **Ao editar o markup:** o `body` compilado e o `body_json` são campos independentes no Customer.io.
> É preciso recompilar via `POST /previews/carta_content` e salvar **os dois** juntos, senão a mensagem
> renderiza em branco. Use `&` puro na URL do `href` — `&amp;` é escapado duas vezes e quebra o link.

## Pendências

- [ ] Substituir `BANNER_INAPP_URL` pela arte final (Design)
- [ ] Confirmar a URL da página promocional após publicação no Contentful
- [ ] Enviar teste antes de agendar
- [ ] Agendar/disparar (a peça está em **rascunho**, não agendada)
