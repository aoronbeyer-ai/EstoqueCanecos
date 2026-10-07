import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer


class StockIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        import os
        previous = os.environ.get('ESTOQUE_DB')
        os.environ['ESTOQUE_DB'] = str(Path(self.directory.name) / 'test.sqlite3')
        try:
            spec = importlib.util.spec_from_file_location('stock_app', Path(__file__).resolve().parents[1] / 'app.py')
            self.app = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.app)
        finally:
            if previous is None:
                os.environ.pop('ESTOQUE_DB', None)
            else:
                os.environ['ESTOQUE_DB'] = previous
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), self.app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def request(self, path, data=None):
        body = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(self.url + path, data=body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def register(self):
        self.request('/api/products', dict(name='Vidro 500 ml', cost='10.00', public_price='25.00', choir_price='20.00'))

    def move(self, kind, quantity):
        return self.request('/api/movements', dict(product_id=1, kind=kind, quantity=quantity))

    def test_sales_gifts_stock_and_financial_result(self):
        self.register()
        for kind, quantity in [('entry', 10), ('public', 3), ('choir', 2), ('gift', 1)]:
            self.move(kind, quantity)
        state = self.request('/api/state')
        self.assertEqual(state['products'][0]['stock'], 4)
        sales = [m for m in state['movements'] if m['kind'] in ('public', 'choir')]
        revenue = sum(m['price'] * m['quantity'] for m in sales)
        cost = sum(m['cost'] * m['quantity'] for m in sales)
        gifts = sum(m['cost'] * m['quantity'] for m in state['movements'] if m['kind'] == 'gift')
        self.assertEqual((revenue, cost, gifts, revenue - cost - gifts), (11500, 5000, 1000, 5500))
        with self.app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM movements').fetchone()[0], 4)

    def test_invalid_movements_preserve_stock(self):
        self.register()
        self.move('entry', 4)
        for quantity in [5, 0, -1, 1.5, True]:
            with self.subTest(quantity=quantity):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.move('public', quantity)
                self.assertEqual(caught.exception.code, 400)
        self.assertEqual(self.request('/api/state')['products'][0]['stock'], 4)
        self.assertEqual(len(self.request('/api/state')['movements']), 1)

    def test_invalid_cost_is_rejected(self):
        for cost in ['-1', '1.001', 'NaN', 'Infinity']:
            with self.subTest(cost=cost):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.request('/api/products', dict(name='Teste', cost=cost, public_price='25', choir_price='20'))
                self.assertEqual(caught.exception.code, 400)
        self.assertEqual(self.request('/api/state')['products'], [])

    def send(self, quantity=6, price='22.50'):
        return self.request('/api/consignments', dict(store_id=1, product_id=1, quantity=quantity, price=price))

    def store_event(self, kind, quantity):
        return self.request('/api/store-events', dict(consignment_id=1, kind=kind, quantity=quantity))

    def setup_store(self):
        self.register()
        self.move('entry', 10)
        self.request('/api/stores', dict(name='Loja A'))

    def test_consignment_sales_return_partial_payment(self):
        self.setup_store()
        self.send()
        state = self.request('/api/state')
        self.assertEqual(state['products'][0]['stock'], 4)
        self.assertEqual(state['stores'][0]['balance'], 0)
        self.store_event('sale', 3)
        self.store_event('return', 2)
        for value in ['20.00', '15.00']:
            self.request('/api/store-events', dict(store_id=1, kind='payment', amount=value))
        state = self.request('/api/state')
        self.assertEqual(state['products'][0]['stock'], 6)
        self.assertEqual(state['consignments'][0]['remaining'], 1)
        store = state['stores'][0]
        self.assertEqual((store['charged'], store['paid'], store['balance']), (6750, 3500, 3250))
        self.assertEqual([e['balance'] for e in state['store_events']], [0, 6750, 6750, 4750, 3250])
        sale = next(e for e in state['store_events'] if e['kind'] == 'sale')
        self.assertEqual(sale['unit_cost'] * sale['quantity'], 3000)
        self.request('/api/stores', dict(name='Loja B'))
        self.request('/api/store-events', dict(store_id=2, kind='payment', amount='5.00'))
        stores = self.request('/api/state')['stores']
        self.assertEqual(stores[0]['balance'], 3250)
        self.assertEqual(stores[1]['balance'], -500)

    def test_consignment_limits_are_atomic(self):
        self.setup_store()
        self.send()
        for action in [lambda: self.send(5), lambda: self.move('public', 5), lambda: self.store_event('sale', 7), lambda: self.store_event('return', 7)]:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                action()
            self.assertEqual(caught.exception.code, 400)
        self.store_event('sale', 6)
        with self.assertRaises(urllib.error.HTTPError):
            self.store_event('return', 1)
        state = self.request('/api/state')
        self.assertEqual(state['products'][0]['stock'], 4)
        self.assertEqual(len(state['consignments']), 1)
        self.assertEqual(len(state['store_events']), 2)

    def test_freight_and_cash_exclude_unpaid_store_sales(self):
        self.setup_store()
        self.send()
        self.store_event('sale', 2)
        self.move('public', 1)
        self.request('/api/expenses', dict(amount='12.50', note='Frete inicial'))
        self.request('/api/expenses', dict(amount='7.50', note='Segundo frete'))
        self.request('/api/store-events', dict(store_id=1, kind='payment', amount='10.00'))
        for value in ['0', '-1', 'NaN', '0.001']:
            with self.assertRaises(urllib.error.HTTPError):
                self.request('/api/expenses', dict(amount=value))
        state = self.request('/api/state')
        purchases = sum(m['cost'] * m['quantity'] for m in state['movements'] if m['kind'] == 'entry')
        freight = sum(e['amount'] for e in state['expenses'])
        received = sum(m['price'] * m['quantity'] for m in state['movements'] if m['kind'] in ('public', 'choir')) + sum(s['paid'] for s in state['stores'])
        self.assertEqual((purchases, freight, received, received-purchases-freight), (10000, 2000, 3500, -8500))
        self.assertEqual(state['stores'][0]['balance'], 3500)
        self.assertTrue(all(e['created_at'] for e in state['expenses']))

    def test_store_gifts_require_permission_and_do_not_charge(self):
        self.setup_store()
        self.send()
        self.store_event('sale', 2)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.store_event('gift', 1)
        self.assertEqual(caught.exception.code, 400)
        self.request('/api/store-permissions', dict(store_id=1, allow_gifts=True))
        self.store_event('gift', 3)
        state = self.request('/api/state')
        self.assertEqual(state['consignments'][0]['remaining'], 1)
        self.assertEqual(state['products'][0]['stock'], 4)
        self.assertEqual(state['stores'][0]['balance'], 4500)
        event = state['store_events'][-1]
        self.assertEqual((event['kind'], event['amount'], event['balance']), ('gift', 0, 4500))
        self.assertEqual(event['unit_cost'] * event['quantity'], 3000)
        with self.assertRaises(urllib.error.HTTPError):
            self.store_event('gift', 2)
        self.request('/api/store-permissions', dict(store_id=1, allow_gifts=False))
        with self.assertRaises(urllib.error.HTTPError):
            self.store_event('gift', 1)
        self.store_event('return', 1)
        state = self.request('/api/state')
        self.assertEqual(state['consignments'][0]['remaining'], 0)
        self.assertEqual(state['products'][0]['stock'], 5)
        self.assertEqual(state['stores'][0]['balance'], 4500)

    def test_store_creation_permission_and_invalid_flags(self):
        self.request('/api/stores', dict(name='Autorizada', allow_gifts=True))
        self.request('/api/stores', dict(name='Bloqueada'))
        state = self.request('/api/state')
        self.assertEqual([s['allow_gifts'] for s in state['stores']], [1, 0])
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/store-permissions', dict(store_id=1, allow_gifts='false'))
        self.assertEqual(self.request('/api/state')['stores'][0]['allow_gifts'], 1)

    def test_store_edit_preserves_account_and_shipments(self):
        self.setup_store()
        self.send()
        self.store_event('sale', 2)
        self.request('/api/stores/update', dict(store_id=1, name='Novo nome', allow_gifts=True))
        state = self.request('/api/state')
        self.assertEqual(len(state['stores']), 1)
        store = state['stores'][0]
        self.assertEqual((store['id'], store['name'], store['allow_gifts'], store['balance']), (1, 'Novo nome', 1, 4500))
        self.assertEqual(state['consignments'][0]['store_name'], 'Novo nome')
        self.store_event('gift', 1)
        for data in [dict(store_id=1, name='', allow_gifts=False), dict(store_id=1, name='Outra', allow_gifts='false'), dict(store_id=999, name='Outra', allow_gifts=False)]:
            with self.assertRaises(urllib.error.HTTPError):
                self.request('/api/stores/update', data)
        store = self.request('/api/state')['stores'][0]
        self.assertEqual((store['name'], store['allow_gifts'], store['balance']), ('Novo nome', 1, 4500))

    def test_interface_and_api_disable_stale_cache(self):
        for path in ['/', '/stores.js', '/api/state']:
            with self.subTest(path=path):
                with urllib.request.urlopen(self.url + path) as response:
                    self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_page_is_served(self):
        with urllib.request.urlopen(self.url + '/', timeout=5) as response:
            self.assertIn('Estoque de canecos', response.read().decode())


if __name__ == '__main__':
    unittest.main()
