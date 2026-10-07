function populateQuestionFilters(state) {
 for (const [id, items, label] of [['question-product',state.products,'Todos os produtos'],['question-store',state.stores,'Todas as lojas']]) {
  const select=document.getElementById(id),previous=select.value;
  select.innerHTML=`<option value="">${label}</option>`+items.map(item=>`<option value="${item.id}">${esc(item.name)}</option>`).join('');
  if(items.some(item=>String(item.id)===previous))select.value=previous;
 }
}
function answerValue(value,type) {
 if(value===null||value===undefined)return '—';
 if(type==='money')return money(value);
 if(type==='units')return units(value);
 if(type==='percent')return `<span class="${value<0?'negative':''}">${Number(value).toLocaleString('pt-BR',{maximumFractionDigits:2})}%</span>`;
 return esc(value);
}
window.addEventListener('DOMContentLoaded',()=>{
 const form=document.getElementById('question-form'),status=document.getElementById('question-status'),answer=document.getElementById('question-answer'),button=document.getElementById('ask-button');
 document.querySelectorAll('[data-question]').forEach(example=>example.onclick=()=>{document.getElementById('question-text').value=example.dataset.question;document.getElementById('question-text').focus();});
 document.getElementById('clear-question-filters').onclick=()=>{for(const name of ['start','end','product_id','store_id','channel'])form.elements[name].value='';};
 form.onsubmit=async event=>{
  event.preventDefault();button.disabled=true;button.textContent='Consultando…';status.textContent='Consultando os registros atuais…';answer.hidden=true;
  const question=form.elements.question.value.trim();
  const filters=Object.fromEntries(['start','end','product_id','store_id','channel'].map(name=>[name,form.elements[name].value]));
  try{
   const response=await fetch('/api/questions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,filters})});
   const result=await response.json();if(!response.ok)throw Error(result.error||'Não foi possível consultar os dados.');
   document.getElementById('answer-question').textContent='Pergunta: '+question;
   document.getElementById('answer-title').textContent=result.title;document.getElementById('answer-summary').textContent=result.summary;
   document.getElementById('answer-metrics').innerHTML=result.metrics.map(item=>`<div class="card"><span>${esc(item.label)}</span><strong>${answerValue(item.value,item.type)}</strong></div>`).join('');
   document.getElementById('answer-head').innerHTML=result.columns.length?'<tr>'+result.columns.map(column=>`<th>${esc(column.label)}</th>`).join('')+'</tr>':'';
   document.getElementById('answer-rows').innerHTML=result.rows.length?result.rows.map(row=>'<tr>'+row.map((value,index)=>`<td>${answerValue(value,result.columns[index].type)}</td>`).join('')+'</tr>').join(''):result.columns.length?`<tr><td colspan="${result.columns.length}">Nenhum registro encontrado para esta consulta.</td></tr>`:'';
   document.querySelector('.answer-table').hidden=!result.columns.length;
   document.getElementById('answer-notes').innerHTML=result.notes.map(note=>`<li>${esc(note)}</li>`).join('');
   answer.hidden=false;status.textContent=result.supported?'Consulta concluída.':'Ajuste a pergunta ou os filtros conforme a orientação abaixo.';
  }catch(error){status.textContent=error.message;}
  finally{button.disabled=false;button.textContent='Consultar dados';}
 };
});
