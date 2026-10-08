let movementEditState,editingMovement;
function editMovementButton(source,id){return `<button type="button" class="secondary" data-edit-source="${source}" data-edit-id="${id}">Editar</button>`;}
window.addEventListener('DOMContentLoaded',()=>{
 const dialog=document.getElementById('movement-edit-dialog'),input=document.getElementById('movement-edit-quantity'),error=document.getElementById('movement-edit-error');
 const boxes=()=>document.getElementById('movement-edit-boxes').textContent=Number.isInteger(Number(input.value))&&Number(input.value)>0?boxText(Number(input.value)):'';
 document.addEventListener('click',event=>{
  const button=event.target.closest('button[data-edit-source]');if(!button)return;
  const source=button.dataset.editSource,id=Number(button.dataset.editId),collection={movement:'movements',shipment:'consignments',event:'store_events'}[source];
  const row=movementEditState[collection].find(item=>item.id===id);if(!row)return;
  editingMovement={source,id,previous_quantity:row.quantity};input.value=row.quantity;boxes();error.textContent='';
  const name=row.name||row.product_name||'Canecos';
  document.getElementById('movement-edit-description').textContent=`${name}${row.store_name?' · '+row.store_name:''} · ${new Date(row.created_at).toLocaleString('pt-BR')}`;
  dialog.showModal();input.focus();input.select();
 });
 input.oninput=boxes;
 document.getElementById('movement-edit-cancel').onclick=()=>dialog.close();
 document.getElementById('movement-edit-form').onsubmit=async event=>{
  event.preventDefault();const button=document.getElementById('movement-edit-save');button.disabled=true;error.textContent='';
  try{
   const response=await fetch('/api/movements/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...editingMovement,quantity:Number(input.value)})});
   const result=await response.json();if(!response.ok)throw Error(result.error||'Não foi possível salvar.');
   await load();dialog.close();document.getElementById('message').style.color='#246544';document.getElementById('message').textContent='Quantidade atualizada. Data original preservada.';
   document.getElementById('question-answer').hidden=true;
  }catch(err){error.textContent=err.message;}finally{button.disabled=false;}
 };
});
