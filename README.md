# Estoque de canecos de chopp

Aplicação em português para cadastrar modelos, custo unitário e preços para público e coral. Registra entradas, vendas pagas e brindes, bloqueando baixas acima do estoque disponível. O painel mostra receita por público, custo vendido, lucro e custo dos brindes.

## Executar

Requer Python 3.12 ou superior, sem dependências externas.

```sh
cd /workspace/EstoqueCanecos
python3 app.py
```

A aplicação atende na porta 8000 (`PORT` altera a porta). Os dados ficam em `estoque.sqlite3`; `ESTOQUE_DB` permite escolher outro caminho. Faça backup desse arquivo com a aplicação parada. Dados persistem entre reinicializações.

Cadastre um caneco e registre uma entrada de estoque inicial. Depois registre as vendas para público, coral ou brindes. Cada movimentação preserva o custo e o preço aplicados no momento do registro.

Lucro das vendas = receita menos custo das unidades vendidas. Resultado após brindes desconta também o custo das unidades presenteadas. Não inclui impostos, taxas ou outras despesas. Nesta versão o custo por modelo é fixo, e o painel acumula todo o histórico.

Esta versão inicial não inclui autenticação ou estorno de movimentações. Use em ambiente privado; não exponha o servidor diretamente à internet.

## Testes

```sh
python3 -m unittest discover -s tests -v
```

Os testes usam banco temporário e verificam vendas, brindes, cálculos financeiros, bloqueio de estoque insuficiente e validação dos valores.

## Consignação e conta corrente

Cadastre a loja e registre o envio, com quantidade e preço por unidade combinado. O envio reduz o estoque disponível, mas não gera receita ou dívida. Confirme as unidades vendidas para gerar a cobrança e reconhecer receita e custo. Registre devoluções para repor o estoque. Registre cada pagamento recebido, inclusive parcelas ou antecipações. O extrato por loja mostra os lançamentos e o saldo; saldo negativo indica crédito. Cada remessa preserva seu preço e custo originais.

## Fretes e dinheiro recebido

Registre os fretes pagos no campo geral. O painel mostra compras (entradas × custo unitário), fretes, total gasto, dinheiro recebido e recebido menos gasto. Entradas são consideradas compras pagas; vendas diretas são consideradas recebidas. Para lojas, apenas pagamentos entram no dinheiro recebido. A receita das vendas confirmadas ainda pendentes fica separada do caixa. O resultado após brindes e fretes desconta custos vendidos, brindes e fretes, enquanto o caixa desconta todas as compras, inclusive unidades ainda em estoque. O histórico mostra a data e hora dos registros; esta versão não permite informar datas retroativas.

## Brindes concedidos pelas lojas e caixas

No cadastro da loja, marque **Permitir brindes sem cobrança** quando autorizado. A permissão também pode ser alterada no resumo por loja. Lojas existentes ficam bloqueadas por padrão após a atualização. Na remessa, escolha **Brinde sem cobrança**: as unidades saem da consignação, não geram dívida ou receita e seu custo entra nos brindes e no resultado após brindes e fretes. Desativar a permissão impede novos brindes, preservando o histórico anterior.

As quantidades continuam registradas em canecos e mostram ao lado as caixas completas de 12 e as unidades restantes (por exemplo, 27 unidades = 2 caixas + 3 canecos). A conversão aparece no dashboard, tabelas, históricos, seleção de remessas e durante a digitação de quantidades.

## Editar lojas

Em **Cadastros → Editar loja**, selecione a loja, ajuste o nome e marque **Permitir brindes sem cobrança**, depois clique em **Salvar alterações da loja**. O botão **Editar loja** no resumo também abre esse formulário. A edição preserva as remessas, cobranças e pagamentos.

## Áreas da interface

A aplicação abre em **Movimentações**, com vendas, entradas, brindes, consignações, pagamentos e fretes. **Painel** concentra o estoque por produto e todos os resultados. **Cadastros** reúne os canecos e o cadastro e edição de lojas. **Histórico** reúne as movimentações, fretes e a conta corrente por loja.

Total gasto, dinheiro recebido e recebido menos gasto permanecem visíveis em todas as áreas. Valores negativos são destacados em vermelho; valores monetários são exibidos na mesma linha. Os formulários se adaptam à largura da tela, com uma coluna no celular.

## Perguntas sobre os dados

A aba **Perguntas** permite escrever consultas locais, sem chave de API, sem custo por uso e sem enviar os registros para serviços externos. Há exemplos clicáveis e filtros opcionais de data, produto, loja e canal. As consultas apenas leem os registros atuais.

Exemplos:

- Quantos canecos preciso vender para empatar com o custo?
- Qual loja vendeu mais em outubro de 2026?
- Qual produto tem melhor rentabilidade? Qual loja tem melhor rentabilidade?
- Liste os canecos vendidos em 07/10/2026 ou entre 01/10/2026 e 07/10/2026.
- Qual mês, semana ou dia mais vendeu?
- Quanto já recebemos e quanto falta receber das lojas?
- Quantos canecos temos em estoque? Quanto gastamos com brindes?

**Critérios:** vendas incluem as diretas e as confirmadas pelas lojas; envios, devoluções, brindes e pagamentos não contam como vendas. Rentabilidade compara a margem bruta das vendas usando seus preços e custos históricos, sem ratear fretes ou brindes. Recuperação do investimento calcula compras mais fretes menos dinheiro recebido, e simula quantas unidades adicionais vender por produto e canal, com arredondamento para cima. As simulações são alternativas, consideram apenas estoque disponível e presumem pagamento integral, sem novas compras. Esse equilíbrio de caixa não substitui o cálculo contábil de custos fixos e margem de contribuição.

Datas são interpretadas no fuso de Brasília. As listas usam as datas de registro, e vendas consignadas usam a data da confirmação. São aceitos DD/MM/AAAA, AAAA-MM-DD, meses com ano, hoje, ontem e últimos N dias. Saldo de loja e estoque são atuais; a interface explica quando um indicador não é filtrado retroativamente. Use filtros para indicar sem ambiguidade um produto ou loja.

A interpretação local cobre esses temas e suas variações usuais; não responde a qualquer pergunta irrestrita nem executa instruções para alterar os dados. Perguntas não reconhecidas pedem reformulação.

## Editar quantidades

Use **Editar** ao lado da linha no histórico de movimentações, na conta corrente das lojas ou nas remessas do painel. A janela permite alterar somente a quantidade. Data, produto, tipo, observação, custo e preço unitário permanecem originais. Estoque, receita, custo e saldo da loja são recalculados. Envios editados atualizam a remessa e seu lançamento no extrato juntos. Alterações que deixem estoque negativo ou uma remessa menor que as baixas já registradas são rejeitadas integralmente. Pagamentos e fretes não possuem quantidade e não oferecem essa edição. Quantidade zero não é aceita; esta função não exclui ou estorna registros.
