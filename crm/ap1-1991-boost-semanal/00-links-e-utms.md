# Links e UTMs — Boost Semanal Aposta1 (AP1-1991)

## URL oficial da promoção

```
https://www.aposta1.bet.br/promocoes/boost-semanal
```

Segue o padrão `/promocoes/<slug>` já usado no site (ex.: `/promocoes/operacao-voando-alto`,
`/promocoes/freebet-na-area`), com o domínio `aposta1.bet.br` usado nas comunicações atuais.

> **Todas as comunicações direcionam para esta página como fonte oficial das regras**, conforme
> exigido no escopo da AP1-1991.

## Se o slug publicado no Contentful for diferente

Trocar a URL nestes 4 pontos:

| # | Ativo | Onde | Campo |
|---|---|---|---|
| 1 | E-mail de lançamento | Customer.io → One-time send `[Esportes] E-mail - Lançamento Boost Semanal` | 3 CTAs no corpo HTML (banner topo, botão "Conhecer a promoção", link de regras no rodapé) |
| 2 | In-app de lançamento | Customer.io → One-time send `[Esportes] In-App - Lançamento Boost Semanal` | `href` do `x-cta` "Clique e Saiba Mais" |
| 3 | Banner Home | Contentful / CMS do site | CTA "Saiba mais" |
| 4 | Banner Área de Promoções | Contentful / CMS do site | CTA "Saber Mais" |

Neste repositório os arquivos-fonte correspondentes são `02-email-lancamento.html`,
`04-in-app-lancamento.md` e `03-banners.md`.

## UTMs por canal

| Canal | URL completa |
|---|---|
| E-mail de lançamento | `https://www.aposta1.bet.br/promocoes/boost-semanal?utm_source=customer.io&utm_medium=email&utm_campaign=boost_semanal&utm_content=lancamento_sports` |
| In-app de lançamento | `https://www.aposta1.bet.br/promocoes/boost-semanal?utm_source=customer.io&utm_medium=in_app&utm_campaign=boost_semanal&utm_content=lancamento_sports` |
| Banner Home | `https://www.aposta1.bet.br/promocoes/boost-semanal?utm_source=site&utm_medium=banner&utm_campaign=boost_semanal&utm_content=home` |
| Banner Área de Promoções | `https://www.aposta1.bet.br/promocoes/boost-semanal?utm_source=site&utm_medium=banner&utm_campaign=boost_semanal&utm_content=area_promocoes` |

Padrão de `utm_campaign` (`boost_semanal`) segue o formato snake_case já usado no workspace
(ex.: `utm_campaign=aposta_do_dia`).

## Links de apoio usados nas peças

| Destino | URL |
|---|---|
| Jogo Responsável | `https://www.aposta1.bet.br/jogo-responsavel` |
| Esportes (para uso do Boost) | `https://www.aposta1.bet.br/esportes#/overview` |
| Fale Conosco (rodapé do layout) | `https://www.aposta1.com/fale-conosco` |
