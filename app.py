import json, sqlite3, os
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

DB = os.environ.get('ESTOQUE_DB', 'estoque.sqlite3')
def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db
with connect() as db:
    db.executescript('''CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT NOT NULL, cost INTEGER NOT NULL, public_price INTEGER NOT NULL, choir_price INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), kind TEXT NOT NULL, quantity INTEGER NOT NULL, cost INTEGER NOT NULL, price INTEGER NOT NULL, note TEXT NOT NULL, created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));''')
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
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(Path(__file__).parent / 'static'), **kwargs)
    def reply(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path != '/api/state': return super().do_GET()
        with connect() as db:
            products = [dict(r) for r in db.execute("SELECT p.*, COALESCE(SUM(CASE WHEN m.kind='entry' THEN m.quantity ELSE -m.quantity END),0) stock FROM products p LEFT JOIN movements m ON p.id=m.product_id GROUP BY p.id ORDER BY p.name")]
            movements = [dict(r) for r in db.execute('SELECT m.*, p.name FROM movements m JOIN products p ON p.id=m.product_id ORDER BY m.id DESC')]
        self.reply(dict(products=products,movements=movements))
    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if self.path == '/api/products':
                    name = str(data.get('name','')).strip()
                    if not name: raise ValueError('Informe o nome do caneco.')
                    db.execute('INSERT INTO products(name,cost,public_price,choir_price) VALUES(?,?,?,?)',(name,amount(data['cost']),amount(data['public_price']),amount(data['choir_price'])))
                elif self.path == '/api/movements':
                    p = db.execute('SELECT * FROM products WHERE id=?',(data['product_id'],)).fetchone()
                    if not p: raise ValueError('Caneco não encontrado.')
                    kind = data['kind']; q = quantity(data['quantity'])
                    if kind not in ('entry','public','choir','gift'): raise ValueError('Tipo de movimentação inválido.')
                    stock = db.execute("SELECT COALESCE(SUM(CASE WHEN kind='entry' THEN quantity ELSE -quantity END),0) FROM movements WHERE product_id=?",(p['id'],)).fetchone()[0]
                    if kind != 'entry' and q > stock: raise ValueError('Estoque insuficiente para esta baixa.')
                    cost = p['cost']; price = p['public_price'] if kind == 'public' else p['choir_price'] if kind == 'choir' else 0
                    db.execute('INSERT INTO movements(product_id,kind,quantity,cost,price,note) VALUES(?,?,?,?,?,?)',(p['id'],kind,q,cost,price,str(data.get('note','')).strip()))
                else: return self.reply({'error':'Rota não encontrada.'},404)
            self.reply({'ok':True},201)
        except (ValueError, KeyError, TypeError) as e: self.reply({'error':str(e) if isinstance(e,ValueError) else 'Dados inválidos.'},400)
if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8000'))),Handler).serve_forever()
