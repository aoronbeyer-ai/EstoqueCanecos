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
