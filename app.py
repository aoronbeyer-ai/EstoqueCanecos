import json, sqlite3, os
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from analytics import answer_question

DB = os.environ.get('ESTOQUE_DB', 'estoque.sqlite3')
def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db
with connect() as db:
    db.executescript('''CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT NOT NULL, cost INTEGER NOT NULL, public_price INTEGER NOT NULL, choir_price INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), kind TEXT NOT NULL, quantity INTEGER NOT NULL, cost INTEGER NOT NULL, price INTEGER NOT NULL, note TEXT NOT NULL, created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
    CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, amount INTEGER NOT NULL, note TEXT NOT NULL, created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
    CREATE TABLE IF NOT EXISTS stores(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS consignments(id INTEGER PRIMARY KEY, store_id INTEGER NOT NULL REFERENCES stores(id), product_id INTEGER NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL, cost INTEGER NOT NULL, price INTEGER NOT NULL, note TEXT NOT NULL, created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
    CREATE TABLE IF NOT EXISTS store_events(id INTEGER PRIMARY KEY, store_id INTEGER NOT NULL REFERENCES stores(id), consignment_id INTEGER REFERENCES consignments(id), kind TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 0, amount INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL, created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));''')
    if 'allow_gifts' not in {row['name'] for row in db.execute('PRAGMA table_info(stores)')}:
        db.execute('ALTER TABLE stores ADD COLUMN allow_gifts INTEGER NOT NULL DEFAULT 0')
def permission(value):
    if not isinstance(value, bool): raise ValueError('Permissão de brindes deve ser sim ou não.')
    return int(value)
def amount(value):
    from decimal import Decimal, InvalidOperation
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0 or n * 100 != (n * 100).to_integral_value(): raise ValueError()
        return int(n * 100)
    except (InvalidOperation, ValueError): raise ValueError('Informe um valor positivo com até duas casas decimais.')
def quantity(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0: raise ValueError('Quantidade deve ser um número inteiro maior que zero.')
    return value
def available(db, product_id):
    local = db.execute("SELECT COALESCE(SUM(CASE WHEN kind='entry' THEN quantity ELSE -quantity END),0) FROM movements WHERE product_id=?", (product_id,)).fetchone()[0]
    sent = db.execute('SELECT COALESCE(SUM(quantity),0) FROM consignments WHERE product_id=?', (product_id,)).fetchone()[0]
    returned = db.execute("SELECT COALESCE(SUM(e.quantity),0) FROM store_events e JOIN consignments c ON c.id=e.consignment_id WHERE c.product_id=? AND e.kind='return'", (product_id,)).fetchone()[0]
    return local - sent + returned

def read_state():
    with connect() as db:
        db.execute('BEGIN')
        products = [dict(r) for r in db.execute("SELECT p.*, COALESCE(SUM(CASE WHEN m.kind='entry' THEN m.quantity ELSE -m.quantity END),0) stock FROM products p LEFT JOIN movements m ON p.id=m.product_id GROUP BY p.id ORDER BY p.name")]
        movements = [dict(r) for r in db.execute('SELECT m.*, p.name FROM movements m JOIN products p ON p.id=m.product_id ORDER BY m.id DESC')]
        expenses = [dict(r) for r in db.execute('SELECT * FROM expenses ORDER BY id DESC')]
        for product in products:
            product['stock'] = available(db, product['id'])
        stores = [dict(r) for r in db.execute('SELECT * FROM stores ORDER BY name')]
        consignments = [dict(r) for r in db.execute('SELECT c.*, p.name, s.name store_name FROM consignments c JOIN products p ON p.id=c.product_id JOIN stores s ON s.id=c.store_id ORDER BY c.id DESC')]
        events = [dict(r) for r in db.execute('SELECT e.*, s.name store_name, p.name product_name, c.cost unit_cost FROM store_events e JOIN stores s ON s.id=e.store_id LEFT JOIN consignments c ON c.id=e.consignment_id LEFT JOIN products p ON p.id=c.product_id ORDER BY e.id')]
        for shipment in consignments:
            shipment['remaining'] = shipment['quantity'] - sum(e['quantity'] for e in events if e['consignment_id'] == shipment['id'] and e['kind'] in ('sale', 'return', 'gift'))
        for store in stores:
            ledger = [e for e in events if e['store_id'] == store['id']]
            store['charged'] = sum(e['amount'] for e in ledger if e['kind'] == 'sale')
            store['paid'] = sum(e['amount'] for e in ledger if e['kind'] == 'payment')
            store['balance'] = store['charged'] - store['paid']
            store['consigned'] = sum(c['remaining'] for c in consignments if c['store_id'] == store['id'])
            balance = 0
            for event in ledger:
                balance += event['amount'] if event['kind'] == 'sale' else -event['amount'] if event['kind'] == 'payment' else 0
                event['balance'] = balance
    return dict(products=products,movements=movements,stores=stores,consignments=consignments,store_events=events,expenses=expenses)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(Path(__file__).parent / 'static'), **kwargs)
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def reply(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path != '/api/state': return super().do_GET()
        self.reply(read_state())
    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
            if self.path == '/api/questions':
                return self.reply(answer_question(read_state(), data.get('question', ''), data.get('filters', {})))
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if self.path == '/api/products':
                    name = str(data.get('name','')).strip()
                    if not name: raise ValueError('Informe o nome do caneco.')
                    db.execute('INSERT INTO products(name,cost,public_price,choir_price) VALUES(?,?,?,?)',(name,amount(data['cost']),amount(data['public_price']),amount(data['choir_price'])))
                elif self.path == '/api/expenses':
                    value = amount(data['amount'])
                    if value <= 0: raise ValueError('Frete deve ser maior que zero.')
                    db.execute('INSERT INTO expenses(amount,note) VALUES(?,?)', (value, str(data.get('note', '')).strip()))
                elif self.path == '/api/stores':
                    name = str(data.get('name', '')).strip()
                    if not name: raise ValueError('Informe o nome da loja.')
                    db.execute('INSERT INTO stores(name,allow_gifts) VALUES(?,?)', (name, permission(data.get('allow_gifts', False))))
                elif self.path == '/api/stores/update':
                    name = str(data.get('name', '')).strip()
                    if not name: raise ValueError('Informe o nome da loja.')
                    allowed = permission(data['allow_gifts'])
                    if not db.execute('SELECT id FROM stores WHERE id=?', (data['store_id'],)).fetchone(): raise ValueError('Loja não encontrada.')
                    db.execute('UPDATE stores SET name=?,allow_gifts=? WHERE id=?', (name, allowed, data['store_id']))
                elif self.path == '/api/store-permissions':
                    allowed = permission(data['allow_gifts'])
                    if not db.execute('SELECT id FROM stores WHERE id=?', (data['store_id'],)).fetchone(): raise ValueError('Loja não encontrada.')
                    db.execute('UPDATE stores SET allow_gifts=? WHERE id=?', (allowed, data['store_id']))
                elif self.path == '/api/consignments':
                    store = db.execute('SELECT id FROM stores WHERE id=?', (data['store_id'],)).fetchone()
                    product = db.execute('SELECT * FROM products WHERE id=?', (data['product_id'],)).fetchone()
                    if not store or not product: raise ValueError('Loja ou caneco não encontrado.')
                    q = quantity(data['quantity']); price = amount(data['price'])
                    if q > available(db, product['id']): raise ValueError('Estoque insuficiente para consignação.')
                    note = str(data.get('note', '')).strip()
                    shipment = db.execute('INSERT INTO consignments(store_id,product_id,quantity,cost,price,note) VALUES(?,?,?,?,?,?)', (store['id'], product['id'], q, product['cost'], price, note)).lastrowid
                    db.execute("INSERT INTO store_events(store_id,consignment_id,kind,quantity,note) VALUES(?,?,'send',?,?)", (store['id'], shipment, q, note))
                elif self.path == '/api/store-events':
                    kind = data['kind']; note = str(data.get('note', '')).strip()
                    if kind == 'payment':
                        store = db.execute('SELECT id FROM stores WHERE id=?', (data['store_id'],)).fetchone()
                        if not store: raise ValueError('Loja não encontrada.')
                        paid = amount(data['amount'])
                        if paid <= 0: raise ValueError('Pagamento deve ser maior que zero.')
                        db.execute("INSERT INTO store_events(store_id,kind,amount,note) VALUES(?,'payment',?,?)", (store['id'], paid, note))
                    elif kind in ('sale', 'return', 'gift'):
                        c = db.execute('SELECT * FROM consignments WHERE id=?', (data['consignment_id'],)).fetchone()
                        if not c: raise ValueError('Remessa não encontrada.')
                        if kind == 'gift' and not db.execute('SELECT allow_gifts FROM stores WHERE id=?', (c['store_id'],)).fetchone()[0]:
                            raise ValueError('Esta loja não está autorizada a conceder brindes.')
                        q = quantity(data['quantity'])
                        consumed = db.execute("SELECT COALESCE(SUM(quantity),0) FROM store_events WHERE consignment_id=? AND kind IN ('sale','return','gift')", (c['id'],)).fetchone()[0]
                        if q > c['quantity'] - consumed: raise ValueError('Quantidade superior aos canecos disponíveis nesta remessa.')
                        charge = q * c['price'] if kind == 'sale' else 0
                        db.execute('INSERT INTO store_events(store_id,consignment_id,kind,quantity,amount,note) VALUES(?,?,?,?,?,?)', (c['store_id'], c['id'], kind, q, charge, note))
                    else: raise ValueError('Operação da loja inválida.')
                elif self.path == '/api/movements':
                    p = db.execute('SELECT * FROM products WHERE id=?',(data['product_id'],)).fetchone()
                    if not p: raise ValueError('Caneco não encontrado.')
                    kind = data['kind']; q = quantity(data['quantity'])
                    if kind not in ('entry','public','choir','gift'): raise ValueError('Tipo de movimentação inválido.')
                    stock = available(db, p['id'])
                    if kind != 'entry' and q > stock: raise ValueError('Estoque insuficiente para esta baixa.')
                    cost = p['cost']; price = p['public_price'] if kind == 'public' else p['choir_price'] if kind == 'choir' else 0
                    db.execute('INSERT INTO movements(product_id,kind,quantity,cost,price,note) VALUES(?,?,?,?,?,?)',(p['id'],kind,q,cost,price,str(data.get('note','')).strip()))
                else: return self.reply({'error':'Rota não encontrada.'},404)
            self.reply({'ok':True},201)
        except (ValueError, KeyError, TypeError) as e: self.reply({'error':str(e) if isinstance(e,ValueError) else 'Dados inválidos.'},400)
if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8000'))),Handler).serve_forever()
