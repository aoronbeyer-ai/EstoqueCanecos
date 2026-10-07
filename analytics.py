"""Read-only queries of recorded stock data. No generated SQL or external service."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import re
import unicodedata
try:
    from zoneinfo import ZoneInfo
    LOCAL_ZONE = ZoneInfo('America/Sao_Paulo')
except (ImportError, KeyError):
    LOCAL_ZONE = timezone(timedelta(hours=-3))

MONTHS = ['janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
EXAMPLES = [
    'Quantos canecos preciso vender para empatar com o custo?',
    'Qual loja vendeu mais?',
    'Qual produto tem melhor rentabilidade?',
    'Liste os canecos vendidos em 07/10/2026',
    'Qual mês mais vendeu?',
    'Quanto já recebemos e quanto falta receber das lojas?',
    'Quantos canecos temos em estoque?',
    'Quanto foi gasto com brindes?',
]

def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))


def local_date(timestamp):
    return datetime.fromisoformat(timestamp.replace('Z', '+00:00')).astimezone(LOCAL_ZONE).date()


def date_value(value):
    try:
        if '/' in value:
            return datetime.strptime(value, '%d/%m/%Y').date()
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('Data inválida. Use DD/MM/AAAA ou os campos de período.')


def response(title, summary, columns=None, rows=None, metrics=None, notes=None, supported=True):
    return dict(title=title, summary=summary, columns=columns or [], rows=rows or [], metrics=metrics or [], notes=notes or [], supported=supported, examples=EXAMPLES)


def scope(state, text, filters, today):
    start = date_value(filters['start']) if filters.get('start') else None
    end = date_value(filters['end']) if filters.get('end') else None
    tokens = re.findall(r'\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b', text)
    if len(tokens) > 2:
        raise ValueError('Informe uma data ou um intervalo com duas datas.')
    if not start and not end:
        if tokens:
            start, end = date_value(tokens[0]), date_value(tokens[-1])
        elif 'anteontem' in text:
            start = end = today - timedelta(days=2)
        elif 'ontem' in text:
            start = end = today - timedelta(days=1)
        elif 'hoje' in text:
            start = end = today
        elif re.search(r'ultimos?\s+\d+\s+dias?', text):
            n = int(re.search(r'ultimos?\s+(\d+)\s+dias?', text)[1])
            if n < 1 or n > 3660: raise ValueError('Informe entre 1 e 3660 dias.')
            start, end = today - timedelta(days=n-1), today
        elif 'semana passada' in text:
            end = today - timedelta(days=today.weekday()+1)
            start = end - timedelta(days=6)
        elif 'esta semana' in text or 'essa semana' in text:
            start, end = today - timedelta(days=today.weekday()), today
        elif 'mes passado' in text:
            end = today.replace(day=1) - timedelta(days=1)
            start = end.replace(day=1)
        elif any(phrase in text for phrase in ['este mes','nesse mes','esse mes']):
            start, end = today.replace(day=1), today
        elif 'este ano' in text or 'esse ano' in text:
            start, end = today.replace(month=1, day=1), today
        else:
            written_day = re.search(r'\b(\d{1,2})(?:\s+de)?\s+(' + '|'.join(MONTHS) + r')(?:\s+de)?\s+(\d{4})\b', text)
            if written_day:
                try: start = end = date(int(written_day[3]),MONTHS.index(written_day[2])+1,int(written_day[1]))
                except ValueError: raise ValueError('Data inválida.')
            month_match = re.search(r'\b(' + '|'.join(MONTHS) + r')(?:\s+de)?\s+(\d{4})\b', text)
            numeric_month = re.search(r'\b(\d{1,2})/(\d{4})\b', text)
            if written_day:
                pass
            elif month_match or numeric_month:
                month = MONTHS.index(month_match[1])+1 if month_match else int(numeric_month[1])
                year = int(month_match[2] if month_match else numeric_month[2])
                try:
                    start = date(year, month, 1)
                    end = (date(year+1, 1, 1) if month == 12 else date(year, month+1, 1)) - timedelta(days=1)
                except ValueError: raise ValueError('Mês ou ano inválido.')
            elif re.search(r'\b(?:em|de|ano de)\s+(\d{4})\b', text):
                year = int(re.search(r'\b(?:em|de|ano de)\s+(\d{4})\b', text)[1])
                try: start, end = date(year,1,1), date(year,12,31)
                except ValueError: raise ValueError('Ano inválido.')
            elif any(re.search(r'\b'+m+r'\b', text) for m in MONTHS) or re.search(r'\b\d{1,2}/\d{1,2}\b', text):
                raise ValueError('Informe também o ano da data ou do mês desejado.')
    if start and end and start > end: raise ValueError('A data inicial deve ser anterior ou igual à final.')
    product_id = filters.get('product_id')
    store_id = filters.get('store_id')
    for key, collection in [('product_id', 'products'), ('store_id', 'stores')]:
        selected = filters.get(key)
        if selected not in (None, '') and not any(str(p['id']) == str(selected) for p in state[collection]):
            raise ValueError('Produto ou loja do filtro não foi encontrado.')
    # Exact complete names in the question work without requiring a filter selection.
    for collection, selected in [('products', product_id), ('stores', store_id)]:
        if not selected:
            matches = [p for p in state[collection] if re.search(r'(?<!\w)'+re.escape(normalize(p['name']))+r'(?!\w)',text)]
            if len(matches) > 1: raise ValueError('Há mais de um nome correspondente. Selecione o produto ou a loja nos filtros.')
            if matches:
                if collection == 'products': product_id = matches[0]['id']
                else: store_id = matches[0]['id']
    channel = filters.get('channel') or None
    if channel not in (None, 'public', 'choir', 'store'): raise ValueError('Canal de venda inválido.')
    if not channel:
        if re.search(r'\bcoral\b', text): channel = 'choir'
        elif 'publico' in text: channel = 'public'
    def within(row):
        day = local_date(row['created_at'])
        return (not start or day >= start) and (not end or day <= end)
    caption = 'Todo o histórico'
    if start or end: caption = f"Período: {start.strftime('%d/%m/%Y') if start else 'início'} a {end.strftime('%d/%m/%Y') if end else 'hoje'}"
    names = []
    for collection, selected in [('products',product_id),('stores',store_id)]:
        if selected: names.append(next(p['name'] for p in state[collection] if str(p['id']) == str(selected)))
    if names: caption += ' · ' + ' · '.join(names)
    if channel: caption += ' · ' + {'public':'Público','choir':'Coral','store':'Lojas'}[channel]
    return dict(start=start,end=end,product_id=product_id,store_id=store_id,channel=channel,within=within,caption=caption)


def transactions(state):
    result = []
    for m in state['movements']:
        if m['kind'] in ('public', 'choir', 'gift'):
            result.append(dict(created_at=m['created_at'], product_id=m['product_id'], product=m['name'], store_id=None, store='—', channel=m['kind'], quantity=m['quantity'], revenue=m['price']*m['quantity'], cost=m['cost']*m['quantity']))
    consignments = {c['id']:c for c in state['consignments']}
    for e in state['store_events']:
        if e['kind'] in ('sale','gift'):
            c = consignments[e['consignment_id']]
            result.append(dict(created_at=e['created_at'],product_id=c['product_id'],product=c['name'],store_id=e['store_id'],store=e['store_name'],channel='store' if e['kind']=='sale' else 'gift',quantity=e['quantity'],revenue=e['amount'],cost=e['unit_cost']*e['quantity']))
    return result


def filtered(rows, context):
    return [r for r in rows if context['within'](r) and (not context['product_id'] or str(r['product_id'])==str(context['product_id'])) and (not context['store_id'] or str(r['store_id'])==str(context['store_id'])) and (not context['channel'] or (r['channel']==context['channel'] or context['channel']=='store' and r['channel']=='gift' and r['store_id'] is not None))]


def columns(*specs):
    return [dict(label=label, type=kind) for label,kind in specs]


def metric(label, value, kind='money'):
    return dict(label=label,value=value,type=kind)


def answer_question(state, question, filters=None, today=None):
    if not isinstance(question,str) or not question.strip(): raise ValueError('Escreva uma pergunta sobre os dados.')
    if len(question) > 2000: raise ValueError('A pergunta deve ter até 2000 caracteres.')
    if filters is None: filters = {}
    if not isinstance(filters,dict): raise ValueError('Filtros inválidos.')
    text = normalize(question).replace('vedid', 'vendid')
    context = scope(state,text,filters,today or datetime.now(LOCAL_ZONE).date())
    all_transactions = transactions(state)
    sales = filtered([r for r in all_transactions if r['channel']!='gift'],context)
    gifts = filtered([r for r in all_transactions if r['channel']=='gift'],context)
    notes = [context['caption'], 'Datas no fuso de Brasília (America/Sao_Paulo). São datas de registro; vendas consignadas usam a data da confirmação.']
    if any(word in text for word in ['equilibrio','empatar','recuperar investimento','recuperar o investimento','cobrir o custo','cobrir os custos']):
        return break_even(state,context,notes)
    if any(word in text for word in ['rentabilidade','rentavel','margem','lucrativo','lucro por','melhor lucro','mais lucro']):
        by_store = 'loja' in text
        groups = defaultdict(lambda:dict(quantity=0,revenue=0,cost=0))
        for r in sales:
            if by_store and not r['store_id']: continue
            group = groups[r['store_id'] if by_store else r['product_id']]
            group['name'] = r['store'] if by_store else r['product']
            for key in ('quantity','revenue','cost'): group[key] += r[key]
        result = [[g['name'],g['quantity'],g['revenue'],g['cost'],g['revenue']-g['cost'],round((g['revenue']-g['cost'])/g['revenue']*100,2) if g['revenue'] else None] for g in groups.values()]
        rank_profit = 'lucro total' in text or 'mais lucro' in text
        result.sort(key=lambda r:(r[4] if rank_profit else r[5] if r[5] is not None else float('-inf')),reverse=True)
        title = 'Rentabilidade por loja' if by_store else 'Rentabilidade por produto'
        summary = 'Nenhuma venda registrada para calcular a rentabilidade.' if not result else ('Comparação por lucro bruto total.' if rank_profit else 'Comparação pela margem bruta das vendas: (receita − custo vendido) ÷ receita. Margem maior significa melhor rentabilidade percentual.')
        return response(title,summary,columns(('Loja' if by_store else 'Produto','text'),('Vendido','units'),('Receita','money'),('Custo vendido','money'),('Lucro bruto','money'),('Margem','percent')),result,notes=notes+['Não rateia fretes nem brindes entre produtos ou lojas. Receita confirmada pode ainda não ter sido recebida.'])
    if 'loja' in text and any(word in text for word in ['mais vendeu','vendeu mais','mais vende','mais fatur','ranking','maior venda','mais vendas','venderam mais','mais venderam']):
        groups = defaultdict(lambda:dict(quantity=0,revenue=0,cost=0))
        for r in sales:
            if r['store_id']:
                for key in ('quantity','revenue','cost'): groups[r['store_id']][key] += r[key]
                groups[r['store_id']]['name'] = r['store']
        result = [[g['name'],g['quantity'],g['revenue'],g['revenue']-g['cost']] for g in groups.values()]
        by_revenue = any(word in text for word in ['fatur','receita','valor'])
        result.sort(key=lambda r:r[2] if by_revenue else r[1],reverse=True)
        summary = 'Não há vendas confirmadas de lojas neste período.'
        if result:
            score = result[0][2 if by_revenue else 1]
            leaders = [r[0] for r in result if r[2 if by_revenue else 1]==score]
            summary = ('Empate na liderança: ' if len(leaders)>1 else 'Loja que mais vendeu: ') + ', '.join(leaders) + ('. Ranking por receita.' if by_revenue else '. Ranking por quantidade de canecos vendidos.')
        return response('Vendas das lojas',summary,columns(('Loja','text'),('Vendido','units'),('Receita confirmada','money'),('Lucro bruto','money')),result,notes=notes+['Envios e brindes não contam como vendas. Pagamentos são acompanhados separadamente.'])
    if any(word in text for word in ['produto','caneco','modelo']) and any(word in text for word in ['mais vende','vendeu mais','mais vendas','maior venda','ranking','mais fatur']):
        groups = defaultdict(lambda:dict(quantity=0,revenue=0,cost=0))
        for row in sales:
            group = groups[row['product_id']]
            group['name'] = row['product']
            for key in ('quantity','revenue','cost'): group[key] += row[key]
        rows = [[g['name'],g['quantity'],g['revenue'],g['revenue']-g['cost']] for g in groups.values()]
        rows.sort(key=lambda row:row[2] if 'fatur' in text else row[1],reverse=True)
        return response('Produtos mais vendidos','Ranking por receita.' if 'fatur' in text else 'Ranking por quantidade de canecos vendidos.',columns(('Produto','text'),('Vendido','units'),('Receita','money'),('Lucro bruto','money')),rows,notes=notes)
    if any(word in text for word in ['periodo','dia','semana','mes']) and any(word in text for word in ['mais vendeu','vendeu mais','mais vend','maior venda','melhor periodo','melhor mes']):
        bucket = 'month' if 'mes' in text else 'week' if 'semana' in text else 'day'
        groups = defaultdict(lambda:[0,0])
        for r in sales:
            d = local_date(r['created_at'])
            key = d.strftime('%Y-%m') if bucket=='month' else d.strftime('%G-S%V') if bucket=='week' else d.isoformat()
            groups[key][0] += r['quantity']; groups[key][1] += r['revenue']
        result = [[key,v[0],v[1]] for key,v in groups.items()]
        result.sort(key=lambda r:(-r[1],r[0]))
        summary = 'Não há vendas no período informado.'
        if result:
            leaders = [r[0] for r in result if r[1]==result[0][1]]
            summary = 'Maior quantidade vendida: ' + ', '.join(leaders) + '.'
        return response('Período com mais vendas',summary,columns(('Mês' if bucket=='month' else 'Semana ISO' if bucket=='week' else 'Dia','text'),('Vendido','units'),('Receita','money')),result,notes=notes+['Agrupamento por '+{'month':'mês','week':'semana ISO (segunda a domingo)','day':'dia'}[bucket]+'. Ranking por quantidade, com todos os empates apresentados.'])
    if any(word in text for word in ['brinde','presente']):
        rows = [[local_date(r['created_at']).strftime('%d/%m/%Y'),r['product'],r['store'],r['quantity'],r['cost']] for r in sorted(gifts,key=lambda r:r['created_at'],reverse=True)]
        return response('Brindes', 'Brindes registrados, sem cobrança ao destinatário.',columns(('Data','text'),('Produto','text'),('Loja','text'),('Quantidade','units'),('Custo','money')),rows,[metric('Canecos em brindes',sum(r['quantity'] for r in gifts),'units'),metric('Custo dos brindes',sum(r['cost'] for r in gifts))],notes)
    if any(word in text for word in ['estoque','consignad','disponiv','nas lojas']):
        if context['start'] or context['end']: return response('Estoque atual','O estoque disponível é atual. Não calculo estoque retroativo; remova o filtro de datas.',notes=notes,supported=False)
        rows=[]
        for product in state['products']:
            if context['product_id'] and str(product['id'])!=str(context['product_id']): continue
            consigned = sum(c['remaining'] for c in state['consignments'] if c['product_id']==product['id'] and (not context['store_id'] or str(c['store_id'])==str(context['store_id'])))
            available = product['stock'] if not context['store_id'] else 0
            rows.append([product['name'],available,consigned,available+consigned])
        return response('Estoque por produto','Canecos disponíveis e em consignação, separados por produto.',columns(('Produto','text'),('Disponível','units'),('Nas lojas','units'),('Total','units')),rows,notes=notes)
    if any(word in text for word in ['recebid','recebemos','pagamento','pagou','pago','receber','devendo','deve','saldo','gast','frete','despesa','investido']):
        if context['product_id'] or context['channel']: return response('Consulta financeira','Pagamentos e fretes são gerais e não são distribuídos por produto ou canal. Remova esses filtros para consultar o caixa.',notes=notes,supported=False)
        direct = sum(r['revenue'] for r in sales if not r['store_id'])
        payments = [e for e in state['store_events'] if e['kind']=='payment' and context['within'](e) and (not context['store_id'] or str(e['store_id'])==str(context['store_id']))]
        received = direct + sum(e['amount'] for e in payments)
        purchases = sum(m['cost']*m['quantity'] for m in state['movements'] if m['kind']=='entry' and context['within'](m)) if not context['store_id'] else 0
        freight = sum(e['amount'] for e in state['expenses'] if context['within'](e)) if not context['store_id'] else 0
        stores = [s for s in state['stores'] if not context['store_id'] or str(s['id'])==str(context['store_id'])]
        rows = [[s['name'],s['charged'],s['paid'],s['balance']] for s in stores]
        return response('Dinheiro e conta corrente','Entradas e saídas de dinheiro no período, com saldo atual das lojas.',columns(('Loja','text'),('Cobrado acumulado','money'),('Pago acumulado','money'),('Saldo atual','money')),rows,[metric('Gasto com compras',purchases),metric('Fretes',freight),metric('Total gasto',purchases+freight),metric('Dinheiro recebido',received),metric('Recebido menos gasto',received-purchases-freight)],notes+['Os indicadores de caixa respeitam o período; a tabela de saldos das lojas mostra o histórico completo até agora. Compras são consideradas pagas na entrada.'])
    if any(word in text for word in ['vend','venda','fatur','receita','lucro','resultado']):
        rows=[[local_date(r['created_at']).strftime('%d/%m/%Y'),r['product'],{'public':'Público','choir':'Coral','store':'Loja'}[r['channel']],r['store'],r['quantity'],r['revenue'],r['cost'],r['revenue']-r['cost']] for r in sorted(sales,key=lambda r:r['created_at'],reverse=True)]
        return response('Vendas registradas','Lista de vendas diretas e confirmadas pelas lojas no período selecionado.',columns(('Data','text'),('Produto','text'),('Canal','text'),('Loja','text'),('Quantidade','units'),('Receita','money'),('Custo vendido','money'),('Lucro bruto','money')),rows,[metric('Canecos vendidos',sum(r['quantity'] for r in sales),'units'),metric('Receita',sum(r['revenue'] for r in sales)),metric('Lucro bruto',sum(r['revenue']-r['cost'] for r in sales))],notes+['Receita de lojas pode ainda estar pendente de pagamento. Lucro bruto não desconta fretes ou brindes.'])
    return response('Preciso de uma pergunta mais específica','Consigo consultar vendas, estoque, lojas, margem, brindes, caixa e recuperação do investimento. Tente um dos exemplos ou use os filtros. Esta versão local não interpreta qualquer pergunta livre.',notes=notes,supported=False)


def break_even(state,context,notes):
    if context['start'] or context['end'] or context['store_id']:
        return response('Recuperação do investimento','Este cálculo usa o caixa total atual. Remova o filtro de datas e de loja; use o produto apenas para simular o preço das próximas vendas.',notes=notes,supported=False)
    spent = sum(m['cost']*m['quantity'] for m in state['movements'] if m['kind']=='entry') + sum(e['amount'] for e in state['expenses'])
    received = sum(m['price']*m['quantity'] for m in state['movements'] if m['kind'] in ('public','choir')) + sum(e['amount'] for e in state['store_events'] if e['kind']=='payment')
    gap = max(0,spent-received)
    rows=[]
    channels=['public','choir'] if not context['channel'] else [context['channel']]
    if 'store' in channels:
        return response('Recuperação do investimento','Os preços variam por remessa nas lojas. Selecione público ou coral para simular uma venda com preço cadastrado.',notes=notes,supported=False)
    for product in state['products']:
        if context['product_id'] and str(product['id'])!=str(context['product_id']): continue
        for channel in channels:
            price=product['public_price'] if channel=='public' else product['choir_price']
            required=0 if gap==0 else (gap+price-1)//price if price else None
            available=product['stock']
            rows.append([product['name'],'Público' if channel=='public' else 'Coral',price,required,available,'Já recuperado' if not gap else 'Preço zero: sem previsão' if required is None else 'Suficiente' if required<=available else 'Estoque disponível insuficiente'])
    return response('Quantos vender para recuperar o dinheiro gasto?', 'O dinheiro recebido já cobriu o gasto registrado.' if not gap else 'Cada linha simula vender apenas aquele produto e canal, pelo preço cadastrado, até cobrir o dinheiro que ainda falta recuperar. As linhas são alternativas; não some as quantidades.',columns(('Produto','text'),('Canal','text'),('Preço unitário','money'),('Faltam vender','units'),('Disponível','units'),('Viabilidade','text')),rows,[metric('Total gasto',spent),metric('Dinheiro recebido',received),metric('Falta recuperar',gap)],notes+['Falta recuperar = compras + fretes − dinheiro recebido, limitado a zero. Arredondamento para cima; vendas simuladas são recebidas integralmente, sem novas compras ou fretes.', 'Este é o equilíbrio de caixa do estoque já comprado. O ponto de equilíbrio contábil (custos fixos ÷ margem de contribuição) exigiria cadastrar despesas fixas e variáveis adicionais.'])
