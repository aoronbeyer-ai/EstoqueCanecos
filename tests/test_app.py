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

    def test_page_is_served(self):
        with urllib.request.urlopen(self.url + '/', timeout=5) as response:
            self.assertIn('Estoque de canecos', response.read().decode())


if __name__ == '__main__':
    unittest.main()
