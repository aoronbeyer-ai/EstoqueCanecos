function boxText(n) {
 const boxes=Math.floor(n/12), rest=n%12;
 return `${boxes} ${boxes===1?'caixa':'caixas'}`+(rest?` + ${rest} ${rest===1?'caneco':'canecos'}`:'');
}
function units(n) { return `${n} un.<small class="boxes">(${boxText(n)})</small>`; }
function updateGiftOption() {
 const shipment=storeState?.consignments.find(c=>String(c.id)===document.querySelector('#shipments').value);
 const allowed=storeState?.stores.find(s=>s.id===shipment?.store_id)?.allow_gifts;
 const option=document.querySelector('#store-gift-option');if(!option)return;option.disabled=!allowed;
 const select=document.querySelector('#settle select[name="kind"]');
 if(!allowed && select.value==='gift')select.value='sale';
}
let storeState;
function renderStores(state) {
  storeState = state;
  const options = state.stores.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
  document.querySelectorAll('.store-select').forEach(select => { const previous=select.value; select.innerHTML=options || '<option value="">Cadastre uma loja</option>'; if(state.stores.some(s=>String(s.id)===previous))select.value=previous; });
  document.querySelector('.product-select').innerHTML=state.products.map(p=>`<option value="${p.id}">${esc(p.name)} (${p.stock} disponíveis · ${boxText(p.stock)})</option>`).join('') || '<option value="">Cadastre um caneco</option>';
  document.querySelector('#shipments').innerHTML=state.consignments.filter(c=>c.remaining>0).map(c=>`<option value="${c.id}">#${c.id} · ${esc(c.store_name)} · ${esc(c.name)} · ${c.remaining} un. (${boxText(c.remaining)}) · ${money(c.price)}/un.</option>`).join('') || '<option value="">Nenhuma remessa disponível</option>';
  document.querySelector('#store-summary').innerHTML=state.stores.map(s=>`<tr><td>${esc(s.name)}</td><td>${units(s.consigned)}</td><td>${money(s.charged)}</td><td>${money(s.paid)}</td><td>${money(s.balance)}</td><td><button type="button" data-store="${s.id}" data-edit-store="${s.id}">${s.allow_gifts ? "Brindes permitidos" : "Brindes bloqueados"} — Editar loja</button></td></tr>`).join('') || '<tr><td colspan="6">Nenhuma loja cadastrada.</td></tr>';
  document.querySelector('#consigned-stock').innerHTML=state.consignments.map(c=>`<tr><td>#${c.id}</td><td>${esc(c.store_name)}</td><td>${esc(c.name)}</td><td>${units(c.quantity)}</td><td>${units(c.remaining)}</td><td>${money(c.price)}</td></tr>`).join('') || '<tr><td colspan="6">Nenhum envio registrado.</td></tr>';
  const filter=document.querySelector('#ledger-store'), previous=filter.value;
  filter.innerHTML='<option value="">Todas as lojas</option>'+options;filter.value=previous;
  const editSelect=document.querySelector('#edit-store-select'), editing=editSelect.value;editSelect.innerHTML=options||'<option value="">Cadastre uma loja primeiro</option>';if(state.stores.some(s=>String(s.id)===editing))editSelect.value=editing;editSelect.onchange=fillStoreEditor;fillStoreEditor();
  filter.onchange=renderLedger;renderLedger();document.querySelector('#shipments').onchange=updateGiftOption;updateGiftOption();
}
function renderLedger(){
 const selected=document.querySelector('#ledger-store').value;
 const names={send:'Envio',sale:'Venda / cobrança',return:'Devolução',payment:'Pagamento',gift:'Brinde sem cobrança'};
 document.querySelector('#ledger').innerHTML=storeState.store_events.filter(e=>!selected||String(e.store_id)===selected).slice().reverse().map(e=>`<tr><td>${new Date(e.created_at).toLocaleString('pt-BR')}</td><td>${esc(e.store_name)}</td><td>${names[e.kind]}</td><td>${e.consignment_id ? esc(e.product_name)+' / #'+e.consignment_id : '—'}</td><td>${e.quantity?units(e.quantity):'—'}</td><td>${money(e.kind==='sale'?e.amount:0)}</td><td>${money(e.kind==='payment'?e.amount:0)}</td><td>${money(e.balance)}</td><td>${esc(e.note)}</td></tr>`).join('') || '<tr><td colspan="9">Nenhum lançamento.</td></tr>';
}
window.addEventListener('DOMContentLoaded',()=>{
 for(const [id,path] of [['freight','expenses'],['store','stores'],['store-edit','stores/update'],['send','consignments'],['settle','store-events'],['payment','store-events']]){
  document.getElementById(id).onsubmit=async event=>{
   event.preventDefault();const form=event.target,button=form.querySelector('button'),data=Object.fromEntries(new FormData(form));
   for(const key of ['store_id','product_id','consignment_id','quantity'])if(key in data)data[key]=Number(data[key]);
   if(id==='store'||id==='store-edit')data.allow_gifts=form.elements.allow_gifts.checked;
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
 const soldCost=state.movements.filter(m=>['public','choir','gift'].includes(m.kind)).reduce((sum,m)=>sum+m.cost*m.quantity,0)+state.store_events.filter(e=>['sale','gift'].includes(e.kind)).reduce((sum,e)=>sum+e.unit_cost*e.quantity,0);
 const revenue=direct+state.stores.reduce((sum,s)=>sum+s.charged,0);
 document.querySelector('#cash-cards').innerHTML=[['Gasto com compras',purchases],['Gasto com fretes',freight],['Total gasto',purchases+freight],['Dinheiro recebido',received],['Recebido menos gasto',received-purchases-freight],['Resultado após brindes e fretes',revenue-soldCost-freight]].map(([label,value])=>`<div class="card"><span>${label}</span><strong>${money(value)}</strong></div>`).join('');
 document.querySelector('#freights').innerHTML=state.expenses.map(e=>`<tr><td>${new Date(e.created_at).toLocaleString('pt-BR')}</td><td>${money(e.amount)}</td><td>${esc(e.note)}</td></tr>`).join('')||'<tr><td colspan="3">Nenhum frete registrado.</td></tr>';
}

function renderProductStock(state) {
 const consignedByProduct = new Map();
 for (const shipment of state.consignments) {
  consignedByProduct.set(shipment.product_id, (consignedByProduct.get(shipment.product_id) || 0) + shipment.remaining);
 }
 document.querySelector('#product-cards').innerHTML = state.products.map(product => {
  const consigned = consignedByProduct.get(product.id) || 0;
  return `<article class="card"><h3>${esc(product.name)}</h3><span>Disponível para venda</span><strong>${units(product.stock)}</strong><p>Nas lojas (consignado): ${units(consigned)}</p><span>Total em estoque: ${units(product.stock + consigned)}</span></article>`;
 }).join('') || '<p class="empty">Nenhum produto cadastrado. Cadastre um tipo de caneco para acompanhar seu estoque aqui.</p>';
}

window.addEventListener('DOMContentLoaded',()=>{
 document.querySelectorAll('input[name="quantity"]').forEach(input=>{
  input.oninput=()=>{const n=Number(input.value);input.nextElementSibling.textContent=Number.isInteger(n)&&n>=0?boxText(n):'Informe uma quantidade inteira';};
 });
 document.querySelector('#store-summary').onclick=event=>{
  const button=event.target.closest('button[data-edit-store]');if(!button)return;
  document.querySelector('#edit-store-select').value=button.dataset.editStore;fillStoreEditor();
  document.querySelector('#store-edit').scrollIntoView({behavior:'smooth',block:'center'});
  document.querySelector('#edit-store-gifts').focus({preventScroll:true});
 };
});
function fillStoreEditor(){
 const select=document.querySelector('#edit-store-select');
 const store=storeState.stores.find(s=>String(s.id)===select.value);
 document.querySelector('#edit-store-name').value=store?.name||'';
 document.querySelector('#edit-store-gifts').checked=Boolean(store?.allow_gifts);
 document.querySelector('#edit-store-save').disabled=!store;
}
