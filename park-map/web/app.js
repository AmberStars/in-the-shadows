'use strict';
const data = JSON.parse(document.getElementById('park-data').textContent);
const $ = id => document.getElementById(id);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const obsById = new Map(data.observations.map(o => [o.id,o]));
const parksById = new Map(data.parks.map(p => [p.id,p]));
const fmt = n => n.toLocaleString();
const observationsLabel = n => `${fmt(n)} observation${n===1?'':'s'}`;
const palette = ['#326545','#956124','#46778b','#805f8b','#8b554d','#4e7561'];
let currentPark = null, currentTaxon = null, selectedObservation = null, photoIndex = 0;
let groups = [], visibleCount = 60, recordsShown = 60;
const sidebarStart = $('sidebar').innerHTML;
const map = L.map('map',{zoomControl:false,preferCanvas:true}).setView(data.center,12);
L.control.zoom({position:'topright'}).addTo(map);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);
const parkLayer = L.featureGroup().addTo(map);
const sightingLayer = L.layerGroup().addTo(map);
let radiusLayer;
$('source-line').textContent = `${data.parks.length} parks within 10 km · ${fmt(data.total_observations)} unique observations · newest ${data.observations_per_park ?? 200} per park · Built ${new Date(data.generated_at).toLocaleDateString()}`;

function button(text,handler,className='back') {
  const el=document.createElement('button');el.textContent=text;el.className=className;el.addEventListener('click',handler);return el;
}
function groupColor(id) {const i=groups.findIndex(g=>g.id===id);return palette[Math.max(i,0)%palette.length];}
function photoMarkup(obs,cls='') {
  const photo=obs?.photos?.[0];
  return photo ? `<img class="${cls}" loading="lazy" src="${escapeHtml(photo.url)}" alt="${escapeHtml(obs.name)} observed by ${escapeHtml(obs.observer)}">` : '<span class="thumb-placeholder">No photo</span>';
}
function setImagesFallback(container) {
  container.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{const span=document.createElement('span');span.className=img.classList.contains('hero')?'hero hero-placeholder':'thumb-placeholder';span.textContent='Photo unavailable';img.replaceWith(span);},{once:true}));
}
function allParks() {
  currentPark=null;currentTaxon=null;selectedObservation=null;
  sightingLayer.clearLayers();parkLayer.clearLayers();if(radiusLayer){map.removeLayer(radiusLayer);radiusLayer=null;}
  $('back').hidden=true;$('eyebrow').hidden=false;$('region').hidden=false;$('map-filter').hidden=true;
  $('title').textContent='Explore the wild.';$('subtitle').textContent='Select a park on the map to meet its wildlife.';
  $('legend-main').textContent='● Parks · select to explore';$('legend-note').textContent='Park boundaries from OpenStreetMap';
  $('sidebar').innerHTML=sidebarStart;
  const picker=$('park-picker');
  data.parks.forEach(p=>{
    const option=document.createElement('option');option.value=p.id;option.textContent=p.name;picker.appendChild(option);
    const shape=L.geoJSON(p.geometry,{style:{color:'#7d9a68',weight:1.5,fillColor:'#cbdcb7',fillOpacity:.55},pointToLayer:(_,latlng)=>L.circleMarker(latlng,{radius:4})}).addTo(parkLayer);
    shape.on('click',()=>selectPark(p.id));
    const marker=L.marker(p.center,{icon:L.divIcon({className:'park-marker',html:'<img src="PARK_MARKER_ASSET" alt="">',iconSize:[36,36],iconAnchor:[18,18]}),title:p.name,alt:p.name,riseOnHover:true}).addTo(parkLayer);
    marker.bindTooltip(escapeHtml(p.name),{direction:'right',offset:[16,0],className:'park-label'});
    marker.on('click',()=>selectPark(p.id));
  });
  picker.addEventListener('change',()=>{if(picker.value)selectPark(picker.value);});
  if(data.parks.length)map.fitBounds(parkLayer.getBounds(),{padding:[40,40],maxZoom:13,animate:false});
}
function selectPark(id) {
  currentPark=parksById.get(id);currentTaxon=null;selectedObservation=null;
  const grouped=new Map();
  currentPark.observations.map(id=>obsById.get(id)).filter(Boolean).forEach(o=>{if(!grouped.has(o.taxon_id))grouped.set(o.taxon_id,{id:o.taxon_id,name:o.name,scientific:o.scientific_name,rank:o.rank,observations:[]});grouped.get(o.taxon_id).observations.push(o);});
  groups=[...grouped.values()].sort((a,b)=>b.observations.length-a.observations.length||a.name.localeCompare(b.name));
  groups.forEach(g=>g.observations.sort((a,b)=>b.date.localeCompare(a.date)));
  $('back').hidden=false;$('eyebrow').hidden=true;$('region').hidden=true;$('map-filter').hidden=false;
  $('title').textContent=currentPark.name;
  parkLayer.clearLayers();
  L.geoJSON(currentPark.geometry,{style:{color:'#96b37e',weight:2,fillColor:'#cbdcb7',fillOpacity:.55}}).addTo(parkLayer);
  if(radiusLayer)map.removeLayer(radiusLayer);
  radiusLayer=L.circle(currentPark.center,{radius:currentPark.radius_m,color:'#7a8e6c',weight:1,dashArray:'5 6',fill:false,interactive:false}).addTo(map);
  map.stop();
  map.fitBounds(radiusLayer.getBounds(),{padding:[65,65],maxZoom:17,animate:false});
  showTaxa();
}
function updateMap() {
  sightingLayer.clearLayers();
  const selected=currentTaxon===null?groups:groups.filter(g=>g.id===currentTaxon);
  const count=selected.reduce((n,g)=>n+g.observations.length,0);
  // Canvas circles keep thousands of observations responsive; small filtered sets use the Figma numbered pins.
  let number=0;
  selected.forEach(g=>g.observations.forEach(o=>{
    const latlng=[o.coordinates[1],o.coordinates[0]];number++;
    const marker=count<=80?L.marker(latlng,{icon:L.divIcon({className:'obs-marker',html:String(number),iconSize:[30,30],iconAnchor:[15,15],bgPos:[0,0]}),title:o.name,alt:o.name}):L.circleMarker(latlng,{radius:5,color:'#fff',weight:1,fillColor:groupColor(g.id),fillOpacity:.85});
    marker.addTo(sightingLayer);
    if(count<=80)marker.getElement().style.background=groupColor(g.id);
    marker.bindTooltip(escapeHtml(`${o.name} · ${o.date}`));
    marker.on('click',()=>showTaxon(g.id,o.id));
  }));
  const name=currentTaxon===null?'All wildlife':groups.find(g=>g.id===currentTaxon).name;
  $('clear-taxon').textContent=`${name} · ${fmt(count)} observations${currentTaxon===null?'':' ×'}`;
  $('subtitle').textContent=`${fmt(count)} observations within the park’s search radius${currentTaxon===null?' · select a taxon to filter the map':''}`;
  $('legend-main').textContent=currentTaxon===null?`${groups.length} taxa · ${fmt(count)} observations`:`${name} · ${fmt(count)} matching observations`;
  $('legend-note').textContent=`Dashed circle: ${Math.round(currentPark.radius_m)} m from park center · may include sightings outside the park`;
}
function showTaxa() {
  currentTaxon=null;selectedObservation=null;visibleCount=60;
  updateMap();
  const p=currentPark;
  $('sidebar').innerHTML=`<div id="side-back"></div><div class="eyebrow">LOCAL PARK</div><h2>${escapeHtml(p.name)}</h2><p class="muted">Mount Pleasant area, Michigan</p><hr class="divider"><h3>Wildlife around this park</h3><p class="muted">${fmt(groups.length)} taxa · ${fmt(p.observations.length)} observations</p><input id="taxon-search" class="search" type="search" placeholder="Search animals, plants, fungi…" aria-label="Search taxa"><div id="taxon-list" class="taxon-list"></div><div id="taxon-more"></div><p class="helper">${p.boundary_available?'Search radius: '+Math.round(p.radius_m)+' m, measured from the park center to its farthest boundary.':'This park has no mapped boundary, so a search radius cannot be calculated.'} ${p.observations_truncated?'Showing up to the newest '+data.observations_per_park+' of '+fmt(p.available_observations)+' available observations.':''}</p><p class="credit">iNaturalist community observations · all quality grades<br>Some public locations are obscured. Sightings are historical.</p>`;
  $('side-back').appendChild(button('← All parks',allParks));
  $('taxon-search').addEventListener('input',()=>{visibleCount=60;renderTaxa();});renderTaxa();$('sidebar').scrollTop=0;
}
function renderTaxa() {
  const q=$('taxon-search').value.trim().toLowerCase();
  const filtered=groups.filter(g=>(g.name+' '+g.scientific).toLowerCase().includes(q));
  $('taxon-list').innerHTML='';$('taxon-more').innerHTML='';
  if(!filtered.length)$('taxon-list').innerHTML=`<p class="empty">${groups.length?'No taxa match your search.':'No public observations were found within this park’s search radius.'}</p>`;
  filtered.slice(0,visibleCount).forEach(g=>{
    const o=g.observations.find(o=>o.photos.length)||g.observations[0];
    const card=button('',()=>showTaxon(g.id),'taxon-card');
    card.innerHTML=`${photoMarkup(o)}<span><strong>${escapeHtml(g.name)}</strong><em>${escapeHtml(g.scientific)}</em><span class="count"><span class="dot" style="background:${groupColor(g.id)}"></span>${observationsLabel(g.observations.length)} →</span></span>`;
    $('taxon-list').appendChild(card);
  });
  if(filtered.length>visibleCount)$('taxon-more').appendChild(button('Show more taxa',()=>{visibleCount+=60;renderTaxa();},'back more'));
  setImagesFallback($('taxon-list'));
}
function showTaxon(id,observationId=null) {
  currentTaxon=id;const g=groups.find(g=>g.id===id);recordsShown=60;
  selectedObservation=g.observations.find(o=>o.id===observationId)||g.observations.find(o=>o.photos.length)||g.observations[0];photoIndex=0;
  updateMap();
  $('sidebar').innerHTML=`<div id="side-back"></div><p class="breadcrumb">${escapeHtml(currentPark.name)}</p><h2>${escapeHtml(g.name)}</h2><p class="scientific">${escapeHtml(g.scientific)}</p><div id="photo-detail"></div><dl class="metadata"><dt>Taxon ID</dt><dd>${g.id||'Unidentified'}</dd><dt>Rank</dt><dd>${escapeHtml(g.rank)}</dd></dl><hr class="divider"><h3>${fmt(g.observations.length)} matching observations</h3><div id="records" class="records"></div><div id="record-more"></div><p class="credit">Photos from the actual observation records. Select a record to see its photos and details.</p>`;
  $('side-back').appendChild(button('← All wildlife',showTaxa));
  renderPhoto();renderRecords();$('sidebar').scrollTop=0;
}
function renderPhoto() {
  const o=selectedObservation,p=o.photos[photoIndex];
  $('photo-detail').innerHTML=(p?`<img class="hero" src="${escapeHtml(p.url)}" alt="${escapeHtml(o.name)} observed by ${escapeHtml(o.observer)}"><div class="credit">${escapeHtml(p.credit||p.license)}</div>`:'<div class="hero hero-placeholder">No photo for this observation</div>')+`<div id="photo-nav" class="photo-nav"></div><p class="muted">Observed ${escapeHtml(o.date)} by ${escapeHtml(o.observer)}<br>${escapeHtml(o.quality.replaceAll('_',' '))}${o.obscured?' · Location obscured':''}</p><a class="observation-link" target="_blank" rel="noopener noreferrer" href="https://www.inaturalist.org/observations/${o.id}">View this observation on iNaturalist ↗</a>`;
  if(o.photos.length>1){$('photo-nav').appendChild(button('←',()=>{photoIndex=(photoIndex-1+o.photos.length)%o.photos.length;renderPhoto();}));const count=document.createElement('span');count.textContent=`Photo ${photoIndex+1} of ${o.photos.length}`;$('photo-nav').appendChild(count);$('photo-nav').appendChild(button('→',()=>{photoIndex=(photoIndex+1)%o.photos.length;renderPhoto();}));}
  setImagesFallback($('photo-detail'));
}
function renderRecords() {
  const g=groups.find(g=>g.id===currentTaxon);$('records').innerHTML='';$('record-more').innerHTML='';
  g.observations.slice(0,recordsShown).forEach((o,i)=>{
    const record=button('',()=>{selectedObservation=o;photoIndex=0;renderPhoto();renderRecords();map.panTo([o.coordinates[1],o.coordinates[0]]);},'record'+(selectedObservation.id===o.id?' selected':''));
    record.innerHTML=`<span class="record-num" style="background:${groupColor(g.id)}">${i+1}</span>${o.photos.length?photoMarkup(o):''}<span><strong>Found by ${escapeHtml(o.observer)}</strong><small>${escapeHtml(o.date)} · #${o.id}${o.obscured?' · obscured':''}</small></span>`;
    $('records').appendChild(record);
  });
  if(g.observations.length>recordsShown)$('record-more').appendChild(button('Show more observations',()=>{recordsShown+=60;renderRecords();},'back more'));
  setImagesFallback($('records'));
}
$('back').addEventListener('click',allParks);
$('clear-taxon').addEventListener('click',()=>{if(currentTaxon!==null)showTaxa();});
window.addEventListener('resize',()=>map.invalidateSize());
allParks();
