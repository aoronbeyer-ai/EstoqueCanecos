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

Esta versão inicial não inclui autenticação, edição ou estorno de movimentações. Use em ambiente privado; não exponha o servidor diretamente à internet.

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
