function showArea(area) {
 const panel=document.querySelector(`[data-panel="${area}"]`);
 if(!panel)return;
 document.querySelectorAll('[data-panel]').forEach(item=>item.hidden=item!==panel);
 document.querySelectorAll('[data-area]').forEach(button=>{
  if(button.dataset.area===area)button.setAttribute('aria-current','page');
  else button.removeAttribute('aria-current');
 });
}
window.addEventListener('DOMContentLoaded',()=>{
 document.querySelectorAll('[data-area]').forEach(button=>button.onclick=()=>showArea(button.dataset.area));
});
