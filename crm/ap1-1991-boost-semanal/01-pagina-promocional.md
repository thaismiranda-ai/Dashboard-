# Página Promocional — Boost Semanal Aposta1

- **Jira:** [AP1-1991](https://aposta1.atlassian.net/browse/AP1-1991) · Epic [AP1-1989](https://aposta1.atlassian.net/browse/AP1-1989)
- **Briefing:** Boost Semanal Aposta1 — Sportsbook — Ago/26
- **Onde publicar:** Contentful → content type de página promocional (mesmo usado em `/promocoes/*`)
- **URL canônica proposta:** `https://www.aposta1.bet.br/promocoes/boost-semanal`
- **Slug:** `boost-semanal`

> ⚠️ A URL acima é a **fonte oficial das regras** e é para onde todos os CTAs (e-mail, in-app, banners) apontam.
> Ela segue o padrão `/promocoes/<slug>` já usado no site. **Se o slug publicado no Contentful for outro,
> é preciso atualizar os CTAs** — a lista de pontos a alterar está em [`00-links-e-utms.md`](./00-links-e-utms.md).

HTML pronto para colar no campo de rich text/HTML do Contentful: [`01-pagina-promocional.html`](./01-pagina-promocional.html).

---

## Metadados

| Campo | Valor |
|---|---|
| Título (H1) | Boost Semanal Aposta1 |
| Subtítulo / chamada | Toda semana, a Aposta1 reconhece jogadores elegíveis com um Boost para utilizar em uma aposta múltipla. |
| Meta title (SEO) | Boost Semanal Aposta1 — Boost para aposta múltipla toda segunda-feira |
| Meta description (SEO) | Jogadores elegíveis podem receber automaticamente um Boost Semanal de até 100% para usar em uma aposta múltipla. Confira os critérios de qualificação. |
| Categoria | Apostas Esportivas / Sportsbook |
| Vigência | A partir de Ago/26 — promoção recorrente (semanal) |

---

## Conteúdo

### Boost Semanal Aposta1

**Toda semana, a Aposta1 reconhece jogadores elegíveis com um Boost para utilizar em uma aposta múltipla.**

Na Aposta1, os jogadores elegíveis podem receber automaticamente um **Boost Semanal** como reconhecimento pelo atendimento aos critérios desta promoção.

Toda semana, as apostas esportivas realizadas durante o período de qualificação são avaliadas automaticamente. Caso os critérios sejam atendidos, o benefício é disponibilizado na conta do jogador na segunda-feira seguinte.

Não é necessário realizar cadastro, ativar a promoção ou solicitar o benefício.

---

### Como funciona

O período de qualificação ocorre semanalmente, de **segunda-feira às 00h00 até domingo às 23h59 (horário de Brasília).**

Ao término desse período, as apostas elegíveis são avaliadas automaticamente.

Os jogadores elegíveis recebem, na segunda-feira seguinte, um **Boost Semanal** para utilização em **uma única aposta múltipla elegível**, conforme a faixa de qualificação alcançada.

---

### Critérios de qualificação

Durante o período de qualificação, serão consideradas apenas apostas que atendam simultaneamente aos seguintes critérios:

- mínimo de **10 apostas esportivas liquidadas**;
- valor mínimo de **R$ 50,00** por aposta;
- odd mínima de **1,50** por aposta;
- apostas realizadas com saldo em dinheiro real;
- apostas simples e múltiplas são válidas para contabilização.

---

### Apostas não elegíveis

Não serão consideradas para fins de qualificação:

- apostas anuladas;
- apostas canceladas;
- apostas encerradas por Cash Out;
- Free Bets;
- apostas realizadas com saldo de bônus;
- apostas inferiores a R$ 50,00;
- apostas com odds inferiores a 1,50.

---

### Faixas de qualificação

> 🎨 **Design:** o briefing pede esta tabela **em imagem** (responsável: Rick Araújo).
> Até a arte final chegar, a tabela HTML de fallback já está montada no `01-pagina-promocional.html`
> e deve ser substituída pelo `<img>` — o comentário `<!-- SUBSTITUIR POR IMAGEM -->` marca o ponto exato.

| Apostas elegíveis liquidadas | Boost recebido |
|:-:|:-:|
| 10 a 19 apostas | **35%** |
| 20 a 39 apostas | **50%** |
| 40 ou mais apostas | **100%** |

Cada jogador poderá receber apenas **um Boost Semanal**, correspondente à maior faixa alcançada durante o período de qualificação.

---

### Como utilizar o Boost

O Boost Semanal:

- pode ser utilizado apenas uma vez;
- é válido exclusivamente para uma aposta múltipla;
- exige, no mínimo, duas seleções;
- exige odd combinada mínima de **2,50**;
- não pode ser utilizado em conjunto com outras promoções ou benefícios semelhantes;
- deverá ser utilizado dentro do prazo informado na conta do jogador;
- não possui valor em dinheiro e não poderá ser sacado ou convertido em saldo.

O ganho líquido máximo obtido com a utilização do Boost Semanal é de **R$ 3.000,00**.

---

### Termos e Condições

- Promoção válida apenas para **maiores de 18 anos**.
- **O MINISTÉRIO DA FAZENDA ADVERTE: APOSTA NÃO É INVESTIMENTO. JOGUE COM RESPONSABILIDADE.**
- Não é necessário realizar cadastro ou ativar a promoção.
- Aplicam-se os Termos e Condições das Apostas Esportivas da Aposta1 e desta promoção.
- Apenas apostas registradas, aceitas e devidamente liquidadas durante o período de qualificação serão consideradas.
- Mercados excluídos, esportes virtuais, apostas anuladas, canceladas, encerradas por Cash Out, Free Bets, apostas com saldo de bônus, apostas inferiores a R$ 50,00 ou com odds inferiores a 1,50 não serão contabilizados.
- Cada jogador poderá receber apenas **um Boost Semanal** por período de qualificação, correspondente à maior faixa alcançada.
- O Boost é pessoal, intransferível, possui prazo de utilização e não pode ser convertido em dinheiro.
- O benefício é válido para **uma única aposta múltipla elegível**, conforme as regras da promoção.
- O ganho líquido máximo obtido com a utilização do Boost é de **R$ 3.000,00**.
- A qualificação é recalculada semanalmente. Apostas excedentes não são acumuladas para períodos futuros.
- Caso uma aposta seja corrigida, anulada ou liquidada novamente, a qualificação e o benefício poderão ser recalculados, ajustados ou cancelados.
- Em caso de falha técnica, concessão incorreta ou necessidade de verificação da conta, a Aposta1 poderá revisar, suspender, ajustar ou cancelar o benefício.
- A Aposta1 reserva-se o direito de alterar, suspender ou encerrar esta promoção, bem como excluir participantes em casos de fraude, conluio, arbitragem, abuso promocional ou qualquer violação destes Termos e Condições.
- Os registros da Aposta1 serão considerados a referência oficial para apuração das apostas elegíveis, da faixa de qualificação e da utilização do benefício.
- Em caso de disputa, prevalecerá a decisão da Aposta1, observada a regulamentação brasileira aplicável.
- Ao participar da promoção, o jogador declara estar de acordo com estes Termos e Condições.
- Tem alguma dúvida? Consulte nossa página de **[Jogo Responsável](https://www.aposta1.bet.br/jogo-responsavel)**.

---

## Checklist de publicação

- [ ] Página criada no Contentful com o slug `boost-semanal`
- [ ] Arte do banner de topo inserida (Design)
- [ ] Tabela de faixas substituída pela imagem (Rick Araújo)
- [ ] Link de Jogo Responsável validado no ambiente publicado
- [ ] URL final confirmada e propagada para e-mail, in-app e banners (ver `00-links-e-utms.md`)
