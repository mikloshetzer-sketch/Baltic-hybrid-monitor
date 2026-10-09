(() => {
"use strict";
const url="./data/baltic_dashboard.json";
const coords={Estonia:[58.72,25.5],Latvia:[56.88,24.6],Lithuania:[55.25,24.1],Poland:[52.15,19.1]};
const names={Estonia:"Észtország",Latvia:"Lettország",Lithuania:"Litvánia",Poland:"Lengyelország",Regional:"Regionális"};
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let data=null,map=null,markers={},selected="all";
function render(){
 const countries=data.country_cards||[],filter=$("balticMapCategory").value;
 const cards=Object.fromEntries(countries.map(c=>[c.country,c]));
 const total=countries.filter(c=>c.country!=="Regional").reduce((a,c)=>a+(Number(c.event_count)||0),0);
 const chosen=cards[selected];
 $("balticMapSelectionTitle").textContent=selected==="all"?"Regionális áttekintés":names[selected]||selected;
 $("balticMapSummary").textContent=chosen?`${chosen.event_count} aktuális esemény · ${chosen.incident_count||0} incidens · ${chosen.indicator_count||0} indikátor`:`${data.summary?.event_count??"—"} aktuális esemény a teljes régiós adatállományban; ebből ${total} országhoz elsődlegesen rendelt.`;
 $("balticMapCountries").innerHTML=["Estonia","Latvia","Lithuania","Poland","Regional"].map(n=>{const c=cards[n];return `<button type="button" class="baltic-country-btn ${selected===n?"selected":""}" data-country="${n}"><span>${names[n]}</span><strong>${c?.event_count??0}</strong></button>`}).join("");
 $("balticMapCountries").querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>setCountry(b.dataset.country)));
 const seen=new Set();
 const events=[...(data.top_events||[]),...(data.recent_events||[])].filter(e=>{
  if(seen.has(e.event_id))return false;seen.add(e.event_id);
  const countryMatch=selected==="all"||e.primary_country===selected||(Array.isArray(e.countries)&&e.countries.includes(selected));
  return countryMatch&&(filter==="all"||(e.categories||[]).includes(filter));
 }).slice(0,6);
 $("balticMapEvents").innerHTML=events.length?events.map(e=>{
 const safeUrl=/^https?:\/\//i.test(e.url||"")?e.url:"#";
 return `<a class="baltic-event-link" href="${esc(safeUrl)}" target="_blank" rel="noopener noreferrer">${esc(e.title)}<small>${esc(names[e.primary_country]||e.primary_country||"—")} · ${esc(e.event_subtype||"—")} · ${Number(e.hybrid_threat_score)||0} pont · ${esc(e.confidence||"—")} confidence</small></a>`;
 }).join(""):'<p class="baltic-map-note">Nincs esemény a megjelenített kivonatban ezzel a szűréssel.</p>';
 Object.entries(markers).forEach(([n,m])=>{m.getElement()?.querySelector(".baltic-map-bubble")?.classList.toggle("active",selected===n)});
}
function setCountry(country){
 selected=country;
 $("balticMapCountry").value=country;
 render();
 if(map&&coords[country])map.flyTo(coords[country],6,{duration:.45});
 else if(map)map.flyTo([56.5,23.3],5,{duration:.45});
}
async function init(){
 try{
  const response=await fetch(url,{cache:"no-store"});if(!response.ok)throw new Error("HTTP "+response.status);
  data=await response.json();
  const categories=new Set();
  [...(data.top_events||[]),...(data.recent_events||[])].forEach(e=>(e.categories||[]).forEach(c=>categories.add(c)));
  [...categories].sort().forEach(c=>{const o=document.createElement("option");o.value=c;o.textContent=c.replaceAll("_"," ");$("balticMapCategory").append(o)});
  $("balticMapCountry").addEventListener("change",e=>setCountry(e.target.value));
  $("balticMapCategory").addEventListener("change",render);
  const w=data.current_threat_window;
  if(w)$("balticMapPeriod").textContent=`${w.start_date||"—"} – ${w.end_date||"—"}`;
  if(window.L){
   $("balticGeoMap").innerHTML="";
   map=L.map("balticGeoMap",{scrollWheelZoom:false}).setView([56.5,23.3],5);
   L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:'&copy; OpenStreetMap contributors',maxZoom:12}).addTo(map);
   const cards=Object.fromEntries((data.country_cards||[]).map(c=>[c.country,c]));
   for(const [country,point] of Object.entries(coords)){
    const count=cards[country]?.event_count||0,size=Math.max(31,Math.min(59,30+count*3));
    const icon=L.divIcon({className:"",html:`<div class="baltic-map-bubble" style="width:${size}px;height:${size}px">${count}</div>`,iconSize:[size,size],iconAnchor:[size/2,size/2]});
    markers[country]=L.marker(point,{icon,title:`${names[country]}: ${count} esemény (országos összesítés)`}).addTo(map).on("click",()=>setCountry(country));
   }
  }else $("balticGeoMap").innerHTML='<div class="baltic-map-placeholder">A térképkönyvtár nem töltődött be. Az országos eseménylista továbbra is használható.</div>';
  render();
 }catch(err){$("balticMapSummary").textContent="Nem sikerült betölteni a térképes adatokat: "+err.message;$("balticGeoMap").innerHTML='<div class="baltic-map-placeholder">Az adatbetöltés sikertelen.</div>'}
}
document.addEventListener("DOMContentLoaded",init);
})();
