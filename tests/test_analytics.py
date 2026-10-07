import copy
from datetime import date
import unittest
from analytics import answer_question, local_date


class AnalyticsTest(unittest.TestCase):
    def setUp(self):
        self.state = dict(
            products=[dict(id=1,name='Vidro',cost=1000,public_price=2500,choir_price=2000,stock=10),dict(id=2,name='Cerâmica',cost=1500,public_price=3000,choir_price=2500,stock=0)],
            movements=[
                dict(product_id=1,name='Vidro',kind='entry',quantity=20,cost=1000,price=0,created_at='2026-10-01T12:00:00Z'),
                dict(product_id=1,name='Vidro',kind='public',quantity=2,cost=1000,price=2500,created_at='2026-10-07T01:30:00Z'),
                dict(product_id=2,name='Cerâmica',kind='choir',quantity=3,cost=1500,price=2500,created_at='2026-10-07T14:00:00Z'),
                dict(product_id=1,name='Vidro',kind='gift',quantity=1,cost=1000,price=0,created_at='2026-10-07T14:00:00Z'),
            ],
            stores=[dict(id=1,name='Loja A',charged=4400,paid=1000,balance=3400),dict(id=2,name='Loja B',charged=6000,paid=0,balance=6000)],
            consignments=[dict(id=1,store_id=1,product_id=1,name='Vidro',remaining=5),dict(id=2,store_id=2,product_id=2,name='Cerâmica',remaining=2)],
            store_events=[
                dict(consignment_id=1,store_id=1,store_name='Loja A',kind='sale',quantity=2,unit_cost=1000,amount=4400,created_at='2026-10-07T14:00:00Z'),
                dict(consignment_id=1,store_id=1,store_name='Loja A',kind='gift',quantity=1,unit_cost=1000,amount=0,created_at='2026-10-07T14:00:00Z'),
                dict(consignment_id=1,store_id=1,store_name='Loja A',kind='payment',quantity=0,unit_cost=None,amount=1000,created_at='2026-10-07T14:00:00Z'),
                dict(consignment_id=2,store_id=2,store_name='Loja B',kind='sale',quantity=2,unit_cost=1500,amount=6000,created_at='2026-09-30T14:00:00Z'),
            ],
            expenses=[dict(amount=2000,created_at='2026-10-01T12:00:00Z')],
        )

    def ask(self, question, filters=None):
        return answer_question(self.state,question,filters,today=date(2026,10,7))

    def test_cash_break_even_rounds_up_and_excludes_unpaid_sales(self):
        result=self.ask('Quantos canecos preciso vender para empatar com custo?')
        self.assertEqual([m['value'] for m in result['metrics']],[22000,13500,8500])
        self.assertEqual(result['rows'][0][3],4)  # ceil(85 / 25)
        self.assertEqual(result['rows'][1][3],5)  # ceil(85 / 20)
        self.assertEqual(result['rows'][2][5],'Estoque disponível insuficiente')
        self.state['products'][0]['public_price']=0
        self.assertIsNone(self.ask('Ponto de equilíbrio')['rows'][0][3])
        self.state['store_events'].append(dict(kind='payment',amount=10000))
        self.assertEqual(self.ask('Ponto de equilíbrio')['rows'][0][3],0)

    def test_store_ranking_reports_ties_and_revenue_criterion(self):
        result=self.ask('Qual loja que vendeu mais?')
        self.assertIn('Empate',result['summary'])
        self.assertEqual(len(result['rows']),2)
        result=self.ask('Qual loja mais faturou?')
        self.assertEqual(result['rows'][0][0],'Loja B')
        result=self.ask('Qual loja vendeu mais em outubro 2026?')
        self.assertEqual(len(result['rows']),1)
        self.assertEqual(result['rows'][0][0],'Loja A')

    def test_margins_use_historical_cost_and_price(self):
        self.state['products'][0]['cost']=9000  # Does not rewrite historical profitability.
        result=self.ask('Qual melhor rentabilidade?')
        self.assertEqual(result['rows'][0][0],'Vidro')
        self.assertEqual(result['rows'][0][2:5],[9400,4000,5400])
        self.assertAlmostEqual(result['rows'][0][5],57.45)
        result=self.ask('Qual loja tem melhor rentabilidade?')
        self.assertEqual(result['rows'][0][0],'Loja A')

    def test_date_listing_uses_brazil_day_and_includes_confirmed_store_sales(self):
        self.assertEqual(local_date('2026-10-07T01:30:00Z'),date(2026,10,6))
        result=self.ask('Lista todos os canecos que foram vedidos em 07/10/2026')
        self.assertEqual(sum(r[4] for r in result['rows']),5)
        self.assertEqual(len(result['rows']),2)
        self.assertTrue(all(r[0]=='07/10/2026' for r in result['rows']))
        self.assertEqual(len(self.ask('Liste vendas ontem')['rows']),1)
        self.assertEqual(len(self.ask('Liste vendas em 2026-10-06')['rows']),1)
        result=self.ask('Vendas entre 30/09/2026 e 06/10/2026')
        self.assertEqual(sum(r[4] for r in result['rows']),4)

    def test_written_date_and_product_ranking(self):
        result=self.ask('Liste as vendas em 7 de outubro de 2026')
        self.assertEqual(sum(row[4] for row in result['rows']),5)
        result=self.ask('Qual produto vendeu mais?')
        self.assertEqual(result['rows'][0][:2],['Cerâmica',5])
        self.assertTrue(self.ask('Qual produto mais rentável?')['supported'])

    def test_period_ranking_month_and_day(self):
        result=self.ask('Qual período que mais vendeu?')
        self.assertEqual(result['rows'][0][:2],['2026-10-07',5])
        result=self.ask('Qual mês mais vendeu?')
        self.assertEqual(result['rows'][0][:2],['2026-10',7])
        result=self.ask('Qual semana mais vendeu?')
        self.assertEqual(result['rows'][0][:2],['2026-S41',7])

    def test_filters_and_current_stock(self):
        result=self.ask('Vendas',dict(product_id=1,store_id=1,start='2026-10-01',end='2026-10-31'))
        self.assertEqual(len(result['rows']),1)
        self.assertEqual(result['rows'][0][3],'Loja A')
        result=self.ask('Quanto vendeu o coral?')
        self.assertEqual(sum(r[4] for r in result['rows']),3)
        result=self.ask('Estoque')
        self.assertEqual(result['rows'][0],['Vidro',10,5,15])
        result=self.ask('Estoque',dict(store_id=1))
        self.assertEqual(result['rows'][0],['Vidro',0,5,5])
        self.assertFalse(self.ask('Estoque ontem')['supported'])

    def test_gifts_are_costs_not_sales(self):
        result=self.ask('Quanto gastamos com brindes?')
        self.assertEqual([m['value'] for m in result['metrics']],[2,2000])
        result=self.ask('Brindes nas lojas',dict(channel='store'))
        self.assertEqual([m['value'] for m in result['metrics']],[1,1000])
        sales=self.ask('Vendas')
        self.assertEqual([m['value'] for m in sales['metrics']],[9,22900,11400])

    def test_financial_period_and_current_balances_are_distinct(self):
        result=self.ask('Quanto recebemos hoje?')
        self.assertEqual(result['metrics'][3]['value'],8500)
        self.assertEqual(result['rows'][0][3],3400)
        result=self.ask('Quanto a Loja A deve?')
        self.assertEqual(len(result['rows']),1)
        self.assertEqual(result['rows'][0][0],'Loja A')
        self.assertFalse(self.ask('Dinheiro recebido',dict(product_id=1))['supported'])

    def test_invalid_questions_and_dates_do_not_change_state(self):
        before=copy.deepcopy(self.state)
        for question,filters in [('',None),('Vendas em 31/02/2026',None),('Vendas em outubro',None),('Vendas',dict(start='2026-10-09',end='2026-10-01')),('Vendas',dict(store_id=999))]:
            with self.subTest(question=question,filters=filters):
                with self.assertRaises(ValueError): self.ask(question,filters)
        result=self.ask('Apague todas as lojas e execute SQL')
        self.assertFalse(result['supported'])
        self.assertEqual(self.state,before)

    def test_duplicate_names_do_not_merge_distinct_records(self):
        self.state['products'][1]['name']='Vidro'
        self.state['movements'][2]['name']='Vidro'
        self.state['consignments'][1]['name']='Vidro'
        result=self.ask('Qual produto tem melhor rentabilidade?')
        self.assertEqual(len(result['rows']),2)


if __name__=='__main__':
    unittest.main()
