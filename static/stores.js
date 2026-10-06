let storeState;
function renderStores(state) {
  storeState = state;
  const options = state.stores.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
  document.querySelectorAll('.store-select').forEach(select => { const previous=select.value; select.innerHTML=options || '<option value="">Cadastre uma loja</option>'; if(state.stores.some(s=>String(s.id)===previous))select.value=previous; });
  document.querySelector('.product-select').innerHTML=state.products.map(p=>`<option value="${p.id}">${esc(p.name)} (${p.stock} disponíveis)</option>`).join('') || '<option value="">Cadastre um caneco</option>';
  document.querySelector('#shipments').innerHTML=state.consignments.filter(c=>c.remaining>0).map(c=>`<option value="${c.id}">#${c.id} · ${esc(c.store_name)} · ${esc(c.name)} · ${c.remaining} un. · ${money(c.price)}/un.</option>`).join('') || '<option value="">Nenhuma remessa disponível</option>';
  document.querySelector('#store-summary').innerHTML=state.stores.map(s=>`<tr><td>${esc(s.name)}</td><td>${s.consigned}</td><td>${money(s.charged)}</td><td>${money(s.paid)}</td><td>${money(s.balance)}</td></tr>`).join('') || '<tr><td colspan="5">Nenhuma loja cadastrada.</td></tr>';
  document.querySelector('#consigned-stock').innerHTML=state.consignments.map(c=>`<tr><td>#${c.id}</td><td>${esc(c.store_name)}</td><td>${esc(c.name)}</td><td>${c.quantity}</td><td>${c.remaining}</td><td>${money(c.price)}</td></tr>`).join('') || '<tr><td colspan="6">Nenhum envio registrado.</td></tr>';
  const filter=document.querySelector('#ledger-store'), previous=filter.value;
  filter.innerHTML='<option value="">Todas as lojas</option>'+options;filter.value=previous;
  filter.onchange=renderLedger;renderLedger();
}
function renderLedger(){
 const selected=document.querySelector('#ledger-store').value;
 const names={send:'Envio',sale:'Venda / cobrança',return:'Devolução',payment:'Pagamento'};
 document.querySelector('#ledger').innerHTML=storeState.store_events.filter(e=>!selected||String(e.store_id)===selected).slice().reverse().map(e=>`<tr><td>${new Date(e.created_at).toLocaleString('pt-BR')}</td><td>${esc(e.store_name)}</td><td>${names[e.kind]}</td><td>${e.consignment_id ? esc(e.product_name)+' / #'+e.consignment_id : '—'}</td><td>${e.quantity||'—'}</td><td>${money(e.kind==='sale'?e.amount:0)}</td><td>${money(e.kind==='payment'?e.amount:0)}</td><td>${money(e.balance)}</td><td>${esc(e.note)}</td></tr>`).join('') || '<tr><td colspan="9">Nenhum lançamento.</td></tr>';
}
window.addEventListener('DOMContentLoaded',()=>{
 for(const [id,path] of [['freight','expenses'],['store','stores'],['send','consignments'],['settle','store-events'],['payment','store-events']]){
  document.getElementById(id).onsubmit=async event=>{
   event.preventDefault();const form=event.target,button=form.querySelector('button'),data=Object.fromEntries(new FormData(form));
   for(const key of ['store_id','product_id','consignment_id','quantity'])if(key in data)data[key]=Number(data[key]);
   if(id==='payment')data.kind='payment';button.disabled=true;
   try{const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error);form.reset();await load();document.querySelector('#message').style.color='#246544';document.querySelector('#message').textContent='Registro salvo com sucesso.';}
   catch(error){document.querySelector('#message').style.color='#a42a25';document.querySelector('#message').textContent=error.message;}
   finally{button.disabled=false;}
  };
 }
});

function renderCash(state) {
 const purchases=state.movements.filter(m=>m.kind==='entry').reduce((sum,m)=>sum+m.cost*m.quantity,0);
 const freight=state.expenses.reduce((sum,e)=>sum+e.amount,0);
 const direct=state.movements.filter(m=>['public','choir'].includes(m.kind)).reduce((sum,m)=>sum+m.price*m.quantity,0);
 const received=direct+state.stores.reduce((sum,s)=>sum+s.paid,0);
 const soldCost=state.movements.filter(m=>['public','choir','gift'].includes(m.kind)).reduce((sum,m)=>sum+m.cost*m.quantity,0)+state.store_events.filter(e=>e.kind==='sale').reduce((sum,e)=>sum+e.unit_cost*e.quantity,0);
 const revenue=direct+state.stores.reduce((sum,s)=>sum+s.charged,0);
 document.querySelector('#cash-cards').innerHTML=[['Gasto com compras',purchases],['Gasto com fretes',freight],['Total gasto',purchases+freight],['Dinheiro recebido',received],['Recebido menos gasto',received-purchases-freight],['Resultado após brindes e fretes',revenue-soldCost-freight]].map(([label,value])=>`<div class="card"><span>${label}</span><strong>${money(value)}</strong></div>`).join('');
 document.querySelector('#freights').innerHTML=state.expenses.map(e=>`<tr><td>${new Date(e.created_at).toLocaleString('pt-BR')}</td><td>${money(e.amount)}</td><td>${esc(e.note)}</td></tr>`).join('')||'<tr><td colspan="3">Nenhum frete registrado.</td></tr>';
}
