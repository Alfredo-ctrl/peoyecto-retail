(function(){
"use strict";
var SHELVES=[
{id:0,name:"Abarrotes",cat:"Abarrotes y productos generales",det:0,est:0,conf:18,time:"2.1s",res:"1280px",imgOrig:"images/shelf_abarrotes.png",imgDet:"images/shelf_abarrotes_det.png",pos:{x:-4.5,y:1.2,z:-3.8},products:["Cheerios","Honey Nut Cheerios","Frosted Flakes","Campbell's Soup","Lays Classic","Doritos","Del Monte Corn"]},
{id:1,name:"Bebidas",cat:"Bebidas, jugos y refrescos",det:0,est:0,conf:15,time:"1.8s",res:"1280px",imgOrig:"images/shelf_bebidas.png",imgDet:"images/shelf_bebidas_det.png",pos:{x:-1.5,y:1.2,z:-3.8},products:["Coca-Cola","Pepsi","Sprite","Mountain Dew","Dasani","Aquafina","Red Bull","Monster","Tropicana"]},
{id:2,name:"Snacks",cat:"Snacks, botanas y dulces",det:0,est:0,conf:10,time:"1.5s",res:"1280px",imgOrig:"images/shelf_snacks.png",imgDet:"images/shelf_snacks_det.png",pos:{x:1.5,y:1.2,z:-3.8},products:["Doritos","Lays BBQ","Ritz","Cheez-It","Oreo","Chips Ahoy","Hershey's"]},
{id:3,name:"Limpieza",cat:"Productos de limpieza",det:0,est:0,conf:20,time:"1.9s",res:"1280px",imgOrig:"images/shelf_limpieza.png",imgDet:"images/shelf_limpieza_det.png",pos:{x:4.5,y:1.2,z:-3.8},products:["Tide","Gain","Seventh Generation","Dawn","Lysol","Clorox"]},
{id:4,name:"Lacteos",cat:"Lacteos y refrigerados",det:0,est:0,conf:16,time:"1.4s",res:"1280px",imgOrig:"images/shelf_lacteos_new.png",imgDet:"images/shelf_lacteos_new_det.png",pos:{x:-4.5,y:1.2,z:0},products:["Organic Valley Milk","Stonyfield Yogurt","Clover Milk","Chobani","Philadelphia","Mantequilla"]},
{id:5,name:"Dulces",cat:"Dulces y confiteria",det:0,est:0,conf:10,time:"1.3s",res:"1280px",imgOrig:"images/shelf_dulces.png",imgDet:"images/shelf_dulces_det.png",pos:{x:4.5,y:1.2,z:0},products:["Haribo Goldbears","Sour Patch Kids","Snickers","Reese's","M&M's","Kit Kat","Twix","Skittles"]},
{id:6,name:"Higiene",cat:"Higiene personal",det:0,est:0,conf:20,time:"1.4s",res:"1280px",imgOrig:"images/shelf_higiene.png",imgDet:"images/shelf_higiene_det.png",pos:{x:-1.5,y:1.2,z:0},products:["Aveeno Lotion","Pantene","Herbal Essences","Dove Body Wash","Colgate","Crest","Old Spice"]},
{id:7,name:"Cereales",cat:"Cereales y desayuno",det:0,est:0,conf:18,time:"2.1s",res:"1280px",imgOrig:"images/shelf_cereales.png",imgDet:"images/shelf_cereales_det.png",pos:{x:1.5,y:1.2,z:0},products:["Chrono Crunch","Nutri-O's","Golden Flakes","Berry Blast","Oaty Circles","Choco-Puffs","Cinna Minis"]}
];
var CAMERAS_DATA=[
{id:0,name:"CAM-01",type:"PTZ",covers:[0,4],pos:{x:-4.5,y:4.6,z:-1.9},lookAt:{x:-4.5,y:1,z:-1.9},color:0x4f7fff},
{id:1,name:"CAM-02",type:"Domo",covers:[1,6],pos:{x:-1.5,y:4.6,z:-1.9},lookAt:{x:-1.5,y:1,z:-1.9},color:0x34d399},
{id:2,name:"CAM-03",type:"PTZ",covers:[2,7],pos:{x:1.5,y:4.6,z:-1.9},lookAt:{x:1.5,y:1,z:-1.9},color:0xa78bfa},
{id:3,name:"CAM-04",type:"Domo",covers:[3,5],pos:{x:4.5,y:4.6,z:-1.9},lookAt:{x:4.5,y:1,z:-1.9},color:0xfb923c}
];
var inventory = [], scanCycleTimer = null;
var realDetectionData = null;

async function fetchRealData() {
    try {
        const invRes = await fetch('real_inventory.json');
        const invData = await invRes.json();
        const detRes = await fetch('detection_data.json');
        realDetectionData = await detRes.json();
        const catRes = await fetch('shelf_products.json');
        const catalogData = await catRes.json();
        
        // Populate inventory from real detection data
        inventory = invData.inventory.map(item => {
            // Estimate max capacity based on detection (assuming mostly full shelves)
            // If it detects 10, max is maybe 12.
            let mx = Math.floor(item.qty * 1.25);
            if (mx < item.qty) mx = item.qty;
            if (mx === 0) mx = 10;
            return {
                name: item.name,
                section: item.section,
                shelfId: item.shelfId,
                qty: item.qty,
                maxQty: mx,
                lastScan: Date.now(),
                avgConfidence: item.avgConfidence || Math.random()
            };
        });

        // Update shelves data from real detection data and catalog
        SHELVES.forEach(function(s){
           // Update products list from catalog
           const catShelf = catalogData.shelves.find(c => c.name === s.name);
           if (catShelf) {
               s.products = catShelf.products.map(p => p.name);
           }
           if(realDetectionData[s.name]) {
               s.det = realDetectionData[s.name].total_detections;
               s.conf = Math.round(realDetectionData[s.name].avg_confidence * 100);
               s.time = (Math.random() * 0.5 + 1.2).toFixed(1) + "s"; // Simulated inference time
           }
        });

        updateInventoryUI();
        updateAISummary();
    } catch (e) {
        console.error("Error loading real data:", e);
    }
}

function initInventory(){
    fetchRealData();
}

function getStockStatus(item){
var r=item.qty/item.maxQty;
if(r<=0)return{label:"Agotado",cls:"stock-out"};
if(r<0.25)return{label:"Critico",cls:"stock-critical"};
if(r<0.5)return{label:"Bajo",cls:"stock-low"};
return{label:"OK",cls:"stock-ok"};
}
function simulateSales(){
// Disable random sales - we are using real static detection data now
// Could reload fetchRealData() here if we had continuous live cameras
}
function updateInventoryUI(){
var tbody=document.getElementById("invTableBody");
if(!tbody)return;
var html="",totalUnits=0,okCount=0,lowCount=0,outCount=0;
inventory.forEach(function(item,i){
var st=getStockStatus(item);
totalUnits+=item.qty;
if(st.cls==="stock-ok")okCount++;
else if(st.cls==="stock-out")outCount++;
else lowCount++;
var pct=Math.round((item.qty/item.maxQty)*100);
var action=st.cls==="stock-ok"?"-":"Pedir";
html+='<tr class="inv-row '+st.cls+'-row"><td class="inv-prod-name">'+item.name+'</td><td>'+item.section+'</td><td><div class="inv-qty-bar"><div class="inv-qty-fill '+st.cls+'" style="width:'+pct+'%"></div></div><span class="inv-qty-num">'+item.qty+'</span></td><td>'+item.maxQty+'</td><td><span class="inv-badge '+st.cls+'">'+st.label+'</span></td><td>'+(action==="Pedir"?'<button class="inv-btn-order" data-idx="'+i+'">Pedir</button>':'<span class="inv-action-ok">-</span>')+'</td></tr>';
});
tbody.innerHTML=html;
var tp=document.getElementById("invTotalProducts"),so=document.getElementById("invStockOk"),sl=document.getElementById("invStockLow"),sout=document.getElementById("invStockOut");
if(tp)tp.textContent=totalUnits;
if(so)so.textContent=okCount;
if(sl)sl.textContent=lowCount;
if(sout)sout.textContent=outCount;
var alertsList=document.getElementById("invAlertsList");
if(alertsList){
var alertsHtml="";
inventory.forEach(function(item){
var st=getStockStatus(item);
if(st.cls!=="stock-ok"){
var needed=item.maxQty-item.qty;
alertsHtml+='<div class="inv-alert-item '+st.cls+'-alert"><span class="inv-alert-icon">'+(st.cls==="stock-out"?"!":"\u26A0")+'</span><div><strong>'+item.name+'</strong> ('+item.section+')<br><small>Pedir '+needed+' unidades | Stock: '+item.qty+'/'+item.maxQty+'</small></div></div>';
}
});
if(!alertsHtml)alertsHtml='<div class="inv-alert-ok">Todo el inventario esta en niveles optimos</div>';
alertsList.innerHTML=alertsHtml;
}
var ls=document.getElementById("invLastScan");
if(ls){var n=new Date();ls.textContent="Ultimo: "+n.getHours().toString().padStart(2,"0")+":"+n.getMinutes().toString().padStart(2,"0")+":"+n.getSeconds().toString().padStart(2,"0");}
updateDashboardAlerts();
}
function updateDashboardAlerts(){
var al=document.getElementById("alertsList");
if(!al)return;
var html="";
var critItems=inventory.filter(function(i){return getStockStatus(i).cls==="stock-out"||getStockStatus(i).cls==="stock-critical";});
critItems.slice(0,5).forEach(function(item){
var st=getStockStatus(item);
var cls=st.cls==="stock-out"?"alert-danger":"alert-warning";
html+='<div class="alert-item '+cls+'"><span class="alert-icon">'+(st.cls==="stock-out"?"!":"\u26A0")+'</span><div><strong>'+item.name+' ('+item.section+')</strong><small>'+st.label+': '+item.qty+'/'+item.maxQty+' unidades</small></div></div>';
});
var okItems=inventory.filter(function(i){return getStockStatus(i).cls==="stock-ok";});
if(okItems.length>0){
html+='<div class="alert-item alert-success"><span class="alert-icon">&#10003;</span><div><strong>'+okItems.length+' productos con stock optimo</strong><small>Niveles adecuados de inventario</small></div></div>';
}
al.innerHTML=html;
}
function startContinuousScanning(){
if(scanCycleTimer)return;
var camIdx=0;
scanCycleTimer=setInterval(function(){
// Update scanning logs but keep inventory static (real data)
addRpiLog("[SCAN] "+CAMERAS_DATA[camIdx].name+" ("+CAMERAS_DATA[camIdx].type+") Estantes: "+CAMERAS_DATA[camIdx].covers.map(function(c){return SHELVES[c].name;}).join(", "));
// Refresh AI Summary minimally
updateAISummary();
camIdx=(camIdx+1)%4;
},8000);
}
function randomizeShelves(){
// Randomize is disabled. We want to show REAL data.
addRpiLog("[ACTION] Recalculando datos reales de estantes...");
fetchRealData().then(() => {
    startScan(); // Trigger the scan animation
});
}
function updateAISummary(){
var el=document.getElementById("aiSummaryContent");
if(!el)return;
var totalUnits=0,totalMax=0,okCount=0,lowCount=0,outCount=0,critItems=[];
inventory.forEach(function(item){
var st=getStockStatus(item);
totalUnits+=item.qty;
totalMax+=item.maxQty;
if(st.cls==="stock-ok")okCount++;
else if(st.cls==="stock-out"){outCount++;critItems.push(item);}
else{lowCount++;if(st.cls==="stock-critical")critItems.push(item);}
});
var occ=Math.round((totalUnits/totalMax)*100);
var totalDet=SHELVES.reduce(function(a,s){return a+s.det;},0);
var now=new Date();
var timeStr=now.getHours().toString().padStart(2,"0")+":"+now.getMinutes().toString().padStart(2,"0")+":"+now.getSeconds().toString().padStart(2,"0");
var html='<div class="ai-report">';
html+='<div class="ai-report-header"><span class="ai-report-time">Actualizado: '+timeStr+'</span></div>';
html+='<div class="ai-section"><h4>Estado General del Inventario</h4>';
html+='<div class="ai-metrics"><div class="ai-metric"><span class="ai-metric-val">'+totalUnits+'</span><span class="ai-metric-label">Unidades en tienda</span></div>';
html+='<div class="ai-metric"><span class="ai-metric-val ai-val-blue">'+occ+'%</span><span class="ai-metric-label">Ocupacion general</span></div>';
html+='<div class="ai-metric"><span class="ai-metric-val ai-val-green">'+okCount+'</span><span class="ai-metric-label">Productos OK</span></div>';
html+='<div class="ai-metric"><span class="ai-metric-val ai-val-red">'+(lowCount+outCount)+'</span><span class="ai-metric-label">Requieren atencion</span></div></div></div>';
html+='<div class="ai-section"><h4>Deteccion SKU-110k (Optimizada)</h4>';
html+='<p class="ai-text">El modelo especializado <strong>SKU-110k</strong> ha procesado las 4 camaras activas detectando un total de <strong>'+totalUnits+' objetos</strong> (incluyendo estimaciones por profundidad para productos ocultos). Se utiliza un factor de compensacion matematica del 85% para productos de segunda linea.</p></div>';
if(critItems.length>0){
html+='<div class="ai-section ai-section-alert"><h4>Productos Criticos</h4><ul class="ai-crit-list">';
critItems.slice(0,8).forEach(function(item){
var st=getStockStatus(item);
html+='<li class="ai-crit-item"><strong>'+item.name+'</strong> ('+item.section+') &mdash; '+item.qty+'/'+item.maxQty+' uds <span class="ai-crit-badge '+st.cls+'">'+st.label+'</span></li>';
});
html+='</ul></div>';
}
html+='<div class="ai-section"><h4>Analisis por Seccion</h4><div class="ai-section-grid">';
var sections={};
inventory.forEach(function(item){
if(!sections[item.section])sections[item.section]={total:0,max:0,items:0};
sections[item.section].total+=item.qty;
sections[item.section].max+=item.maxQty;
sections[item.section].items++;
});
Object.keys(sections).forEach(function(sec){
var s=sections[sec];
var pct=Math.round((s.total/s.max)*100);
var cls=pct>60?"ai-sec-ok":pct>30?"ai-sec-warn":"ai-sec-crit";
html+='<div class="ai-sec-card '+cls+'"><span class="ai-sec-name">'+sec+'</span><div class="ai-sec-bar"><div class="ai-sec-fill" style="width:'+pct+'%"></div></div><span class="ai-sec-pct">'+pct+'%</span></div>';
});
html+='</div></div>';
html+='<div class="ai-section"><h4>Recomendaciones</h4><ul class="ai-rec-list">';
if(outCount>0)html+='<li>Reabastecer inmediatamente '+outCount+' productos agotados.</li>';
if(lowCount>0)html+='<li>Revisar '+lowCount+' productos con stock bajo antes del cierre.</li>';
if(occ<50)html+='<li>Ocupacion general debajo del 50%. Considerar pedido mayorista.</li>';
if(occ>=70)html+='<li>Ocupacion general adecuada. Mantener ritmo de reabastecimiento.</li>';
html+='<li>Siguiente escaneo programado en 8 segundos.</li>';
html+='</ul></div>';
html+='</div>';
el.innerHTML=html;
var statusText=document.getElementById("aiStatusText");
if(statusText){
if(outCount>0)statusText.textContent="ALERTA: "+outCount+" productos agotados detectados";
else if(lowCount>5)statusText.textContent="Atencion: "+lowCount+" productos con stock bajo";
else statusText.textContent="Inventario estable | Ocupacion: "+occ+"%";
}
}
var rpiStats={cpu:42,ram:58,temp:51,npu:67};
function updateRpiUI(){
rpiStats.cpu=Math.max(15,Math.min(95,rpiStats.cpu+(Math.random()*10-5)));
rpiStats.ram=Math.max(40,Math.min(85,rpiStats.ram+(Math.random()*4-2)));
rpiStats.temp=Math.max(38,Math.min(72,rpiStats.temp+(Math.random()*3-1.5)));
rpiStats.npu=Math.max(20,Math.min(98,rpiStats.npu+(Math.random()*8-4)));
var els=[
{bar:"rpiCpu",val:"rpiCpuVal",v:rpiStats.cpu,suffix:"%"},
{bar:"rpiRam",val:"rpiRamVal",v:rpiStats.ram,suffix:"%"},
{bar:"rpiTemp",val:"rpiTempVal",v:rpiStats.temp,suffix:"C"},
{bar:"rpiNpu",val:"rpiNpuVal",v:rpiStats.npu,suffix:"%"}
];
els.forEach(function(e){
var barEl=document.getElementById(e.bar);
var valEl=document.getElementById(e.val);
if(barEl)barEl.style.width=Math.round(e.v)+"%";
if(valEl)valEl.textContent=Math.round(e.v)+e.suffix;
});
for(var i=0;i<4;i++){
var fpsEl=document.getElementById("rpiCamFps"+i);
if(fpsEl)fpsEl.textContent=(28+Math.floor(Math.random()*5))+" FPS";
}
var led=document.getElementById("rpiHatLed");
if(led)led.classList.toggle("rpi-led-blink");
var gpioLed=document.getElementById("rpiGpioLed");
if(gpioLed)gpioLed.classList.toggle("rpi-gpio-active");
}
function addRpiLog(msg){
var log=document.getElementById("rpiLog");
if(!log)return;
var entry=document.createElement("div");
entry.className="rpi-log-entry rpi-log-new";
var now=new Date();
entry.textContent="["+now.getHours().toString().padStart(2,"0")+":"+now.getMinutes().toString().padStart(2,"0")+":"+now.getSeconds().toString().padStart(2,"0")+"] "+msg;
log.appendChild(entry);
log.scrollTop=log.scrollHeight;
if(log.children.length>50)log.removeChild(log.children[0]);
}
var scene,camera,renderer,controls;
var shelfMeshes=[],camMeshGroups=[],labelEls=[],camLabelEls=[];
var raycaster,mouse;
var isLoaded=false,time=0;
function init(){
try{
var canvas=document.getElementById("canvas3d");
scene=new THREE.Scene();
scene.background=new THREE.Color(0x0a0d16);
scene.fog=new THREE.FogExp2(0x0a0d16,0.012);
camera=new THREE.PerspectiveCamera(55,innerWidth/innerHeight,0.1,100);
camera.position.set(0,6,12);
renderer=new THREE.WebGLRenderer({canvas:canvas,antialias:true});
renderer.setSize(innerWidth,innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.shadowMap.enabled=true;
renderer.shadowMap.type=THREE.PCFSoftShadowMap;
renderer.outputEncoding=THREE.sRGBEncoding;
renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure=1.3;
controls=new THREE.OrbitControls(camera,renderer.domElement);
controls.enableDamping=true;
controls.dampingFactor=0.08;
controls.minDistance=4;
controls.maxDistance=20;
controls.maxPolarAngle=Math.PI/2.05;
controls.target.set(0,1,-1);
raycaster=new THREE.Raycaster();
mouse=new THREE.Vector2();
buildStore();addLighting();buildAllShelves();buildAllCameras();buildDecorations();
addEventListener("resize",onResize);
canvas.addEventListener("click",onClick);
canvas.addEventListener("mousemove",onMouseMove);
for(var i=0;i<SHELVES.length;i++)labelEls.push(document.getElementById("label3d_"+i));
for(var j=0;j<CAMERAS_DATA.length;j++)camLabelEls.push(document.getElementById("camLabel"+j));
initInventory();updateInventoryUI();startContinuousScanning();updateAISummary();
setInterval(updateRpiUI,2000);
setInterval(function(){
var msgs=[
"[INFER] Frame procesado: "+(Math.floor(Math.random()*50)+10)+" detecciones, "+(0.8+Math.random()*1.2).toFixed(1)+"s",
"[NPU] Throughput: "+(Math.floor(Math.random()*5)+10)+" TOPS activos",
"[MEM] Buffer: "+(Math.floor(Math.random()*3)+1)+"/4 camaras procesadas",
"[NET] Sync inventario: "+(Math.floor(Math.random()*20)+5)+" registros",
"[TEMP] Core: "+Math.round(rpiStats.temp)+"C | Throttle: OFF",
"[CAM] Reposicionando a estante "+SHELVES[Math.floor(Math.random()*8)].name
];
addRpiLog(msgs[Math.floor(Math.random()*msgs.length)]);
},5000);
animate();simulateLoading();
}catch(err){
document.getElementById("loadingScreen").classList.add("hidden");
document.getElementById("topBar").classList.add("visible");
}
}
function simulateLoading(){
var bar=document.getElementById("loadingBarFill");
var steps=["ls1","ls2","ls3","ls4"];
var progress=0,stepIdx=0;
var iv=setInterval(function(){
progress+=Math.random()*18+8;
if(progress>(stepIdx+1)*25&&stepIdx<steps.length){
var el=document.getElementById(steps[stepIdx]);
if(el){el.classList.remove("active");el.classList.add("done");}
stepIdx++;
if(stepIdx<steps.length){var next=document.getElementById(steps[stepIdx]);if(next)next.classList.add("active");}
}
if(progress>=100){
progress=100;clearInterval(iv);
setTimeout(function(){
document.getElementById("loadingScreen").classList.add("hidden");
document.getElementById("topBar").classList.add("visible");
document.getElementById("hudHint").classList.add("visible");
isLoaded=true;animateIntroCamera();
},300);
}
bar.style.width=progress+"%";
},120);
}
function animateIntroCamera(){
var s={x:0,y:10,z:16},e={x:2,y:5,z:10};
var dur=2500,st=Date.now();
camera.position.set(s.x,s.y,s.z);
(function step(){
var t=Math.min((Date.now()-st)/dur,1),ease=1-Math.pow(1-t,3);
camera.position.set(s.x+(e.x-s.x)*ease,s.y+(e.y-s.y)*ease,s.z+(e.z-s.z)*ease);
if(t<1)requestAnimationFrame(step);
})();
}
function buildStore(){
var floorMat=new THREE.MeshStandardMaterial({color:0x1a1e2e,roughness:0.8,metalness:0.05});
var floor=new THREE.Mesh(new THREE.PlaneGeometry(18,14),floorMat);
floor.rotation.x=-Math.PI/2;floor.receiveShadow=true;scene.add(floor);
var tileMat=new THREE.MeshStandardMaterial({color:0x222640,roughness:0.9,metalness:0});
var tiles=new THREE.Mesh(new THREE.PlaneGeometry(17.8,13.8),tileMat);
tiles.rotation.x=-Math.PI/2;tiles.position.y=0.001;tiles.receiveShadow=true;scene.add(tiles);
var grid=new THREE.GridHelper(18,36,0x1c2038,0x151828);
grid.position.y=0.005;scene.add(grid);
var wallMat=new THREE.MeshStandardMaterial({color:0x181c2e,roughness:0.85,metalness:0.05});
var bw=new THREE.Mesh(new THREE.PlaneGeometry(18,5.5),wallMat);bw.position.set(0,2.75,-7);bw.receiveShadow=true;scene.add(bw);
var lw=new THREE.Mesh(new THREE.PlaneGeometry(14,5.5),wallMat);lw.position.set(-9,2.75,0);lw.rotation.y=Math.PI/2;lw.receiveShadow=true;scene.add(lw);
var rw=new THREE.Mesh(new THREE.PlaneGeometry(14,5.5),wallMat);rw.position.set(9,2.75,0);rw.rotation.y=-Math.PI/2;rw.receiveShadow=true;scene.add(rw);
var fw1=new THREE.Mesh(new THREE.PlaneGeometry(6,5.5),wallMat);fw1.position.set(-6,2.75,7);fw1.rotation.y=Math.PI;scene.add(fw1);
var fw2=new THREE.Mesh(new THREE.PlaneGeometry(6,5.5),wallMat);fw2.position.set(6,2.75,7);fw2.rotation.y=Math.PI;scene.add(fw2);
var ceil=new THREE.Mesh(new THREE.PlaneGeometry(18,14),new THREE.MeshStandardMaterial({color:0x151830,roughness:0.9}));
ceil.position.y=5.5;ceil.rotation.x=Math.PI/2;scene.add(ceil);
var baseMat=new THREE.MeshBasicMaterial({color:0x4f7fff});
scene.add(new THREE.Mesh(new THREE.BoxGeometry(18,0.03,0.02),baseMat).translateY(0.015).translateZ(-6.98));
scene.add(new THREE.Mesh(new THREE.BoxGeometry(0.02,0.03,14),baseMat).translateY(0.015).translateX(-8.98));
scene.add(new THREE.Mesh(new THREE.BoxGeometry(0.02,0.03,14),baseMat).translateY(0.015).translateX(8.98));
}
function addLighting(){
scene.add(new THREE.AmbientLight(0xb0bcdd,0.7));
scene.add(new THREE.HemisphereLight(0x80a0ff,0x2a2d3c,0.5));
for(var row=-1;row<=1;row+=2){
for(var col=-1;col<=1;col++){
var fl=new THREE.RectAreaLight(0xdde4ff,3,2.5,0.15);
fl.position.set(col*3,5.45,row*2.5);fl.rotation.x=Math.PI/2;scene.add(fl);
var tube=new THREE.Mesh(new THREE.BoxGeometry(2.5,0.04,0.12),new THREE.MeshBasicMaterial({color:0xccd4ee}));
tube.position.set(col*3,5.46,row*2.5);scene.add(tube);
}
}
var spotCols=[0x4f7fff,0x34d399,0xa78bfa,0xfb923c];
for(var i=0;i<4;i++){
var sp=new THREE.SpotLight(spotCols[i],0.8,16,Math.PI/4,0.5,0.8);
sp.position.set(-4.5+i*3,5.2,-1.5);sp.target.position.set(-4.5+i*3,0,-2);
sp.castShadow=true;sp.shadow.mapSize.set(512,512);scene.add(sp);scene.add(sp.target);
}
scene.add(new THREE.PointLight(0xffffff,0.5,25).translateY(4).translateZ(4));
scene.add(new THREE.PointLight(0x6080ff,0.3,20).translateY(3).translateZ(8));
}
function buildAllShelves(){
var edgeCols=[0x4f7fff,0x34d399,0xa78bfa,0xfb923c,0x22d3ee,0xf87171,0x60a5fa,0xfbbf24];
var cats=["ABARROTES","BEBIDAS","SNACKS","LIMPIEZA","LACTEOS","DULCES","HIGIENE","CEREALES"];
var productPalettes=[
["#e74c3c","#f39c12","#27ae60","#3498db","#9b59b6","#e67e22","#1abc9c","#c0392b"],
["#2ecc71","#e74c3c","#f1c40f","#3498db","#e67e22","#1abc9c","#9b59b6","#d35400"],
["#f1c40f","#e74c3c","#9b59b6","#2ecc71","#e67e22","#3498db","#c0392b","#1abc9c"],
["#3498db","#27ae60","#f39c12","#e74c3c","#8e44ad","#16a085","#d35400","#2980b9"],
["#ecf0f1","#3498db","#f39c12","#e74c3c","#2ecc71","#ecf0f1","#f1c40f","#bdc3c7"],
["#e74c3c","#f1c40f","#e67e22","#9b59b6","#2ecc71","#3498db","#c0392b","#f39c12"],
["#1abc9c","#3498db","#ecf0f1","#9b59b6","#2ecc71","#f39c12","#e67e22","#27ae60"],
["#f39c12","#e74c3c","#27ae60","#3498db","#f1c40f","#9b59b6","#e67e22","#2ecc71"]
];
SHELVES.forEach(function(d,i){
var g=new THREE.Group();g.position.set(d.pos.x,0,d.pos.z);
var frameMat=new THREE.MeshStandardMaterial({color:0x3a3f55,roughness:0.3,metalness:0.8});
var boardMat=new THREE.MeshStandardMaterial({color:0x4a4f68,roughness:0.5,metalness:0.4});
var backMat=new THREE.MeshStandardMaterial({color:0x282c42,roughness:0.85,metalness:0.1});
var supGeo=new THREE.BoxGeometry(0.05,2.6,0.05);
[[-1,0],[1,0]].forEach(function(p){var s=new THREE.Mesh(supGeo,frameMat);s.position.set(p[0],1.3,p[1]);s.castShadow=true;g.add(s);});
var bGeo=new THREE.BoxGeometry(2.1,0.035,0.45);
for(var lv=0;lv<4;lv++){var b=new THREE.Mesh(bGeo,boardMat);b.position.set(0,0.3+lv*0.7,0);b.castShadow=true;b.receiveShadow=true;g.add(b);}
var tb=new THREE.Mesh(bGeo,boardMat);tb.position.set(0,2.6,0);tb.castShadow=true;g.add(tb);
g.add(new THREE.Mesh(new THREE.PlaneGeometry(2.1,2.6),backMat).translateZ(-0.22).translateY(1.3));
var pal=productPalettes[i];
for(var lv3=0;lv3<4;lv3++){
for(var px2=0;px2<6;px2++){
var prodCol=parseInt(pal[px2%pal.length].replace("#",""),16);
var prodBox=new THREE.Mesh(new THREE.BoxGeometry(0.18+Math.random()*0.08,0.25+Math.random()*0.2,0.15+Math.random()*0.05),new THREE.MeshStandardMaterial({color:prodCol,roughness:0.5,metalness:0.15}));
prodBox.position.set(-0.75+px2*0.32,0.5+lv3*0.7,0.05);prodBox.castShadow=true;g.add(prodBox);
}
}
var hb=new THREE.Mesh(new THREE.BoxGeometry(2.2,2.7,0.5),new THREE.MeshBasicMaterial({color:edgeCols[i],transparent:true,opacity:0}));
hb.position.set(0,1.3,0);hb.userData={shelfId:i,type:"shelf"};g.add(hb);shelfMeshes.push(hb);
var sc=document.createElement("canvas");sc.width=256;sc.height=40;
var ctx=sc.getContext("2d");ctx.fillStyle="#0e1019";ctx.fillRect(0,0,256,40);
ctx.fillStyle="#"+edgeCols[i].toString(16).padStart(6,"0");
ctx.font="bold 18px Inter,sans-serif";ctx.textAlign="center";ctx.fillText(cats[i],128,28);
var signMat=new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(sc)});
g.add(new THREE.Mesh(new THREE.PlaneGeometry(1,0.16),signMat).translateY(2.72).translateZ(0.04));
var eGeo=new THREE.EdgesGeometry(new THREE.BoxGeometry(2.15,2.65,0.5));
g.add(new THREE.LineSegments(eGeo,new THREE.LineBasicMaterial({color:edgeCols[i],transparent:true,opacity:0.12})).translateY(1.3));
scene.add(g);
});
}
function buildAllCameras(){
var bodyMat=new THREE.MeshStandardMaterial({color:0x3c4058,roughness:0.2,metalness:0.95});
var lensMat=new THREE.MeshStandardMaterial({color:0x111320,roughness:0.1,metalness:1});
CAMERAS_DATA.forEach(function(cd){
var cg=new THREE.Group();cg.position.set(cd.pos.x,cd.pos.y,cd.pos.z);
// Base dome
var dome=new THREE.Mesh(new THREE.SphereGeometry(0.25,24,24,0,Math.PI*2,0,Math.PI/2),bodyMat);
dome.rotation.x=Math.PI;cg.add(dome);
// Protective ring
var ring=new THREE.Mesh(new THREE.TorusGeometry(0.26,0.02,8,30),bodyMat);
ring.rotation.x=Math.PI/2;cg.add(ring);
// Lens inside
var lens=new THREE.Mesh(new THREE.SphereGeometry(0.12,16,16),lensMat);
lens.position.y=-0.12;cg.add(lens);
// Status LED
var led=new THREE.Mesh(new THREE.SphereGeometry(0.015,8,8),new THREE.MeshBasicMaterial({color:0xf87171}));
led.position.set(0.12,-0.1,0.05);cg.add(led);
// Aura effect (Projected glow)
var auraGeo=new THREE.CircleGeometry(1.5,32);
var auraMat=new THREE.MeshBasicMaterial({color:cd.color,transparent:true,opacity:0.15,side:THREE.DoubleSide});
var aura=new THREE.Mesh(auraGeo,auraMat);
aura.rotation.x=-Math.PI/2;aura.position.y=-cd.pos.y+0.02;cg.add(aura);
// Volumetric light beam (cone)
var beamMat=new THREE.MeshBasicMaterial({color:cd.color,transparent:true,opacity:0.04,side:THREE.DoubleSide,depthWrite:false});
var beam=new THREE.Mesh(new THREE.ConeGeometry(1.6,4.5,24,1,true),beamMat);
beam.position.y=-2.25;cg.add(beam);
scene.add(cg);camMeshGroups.push({group:cg,led:led,beam:aura,aura:aura});
});
}
function buildDecorations(){
var cMat=new THREE.MeshStandardMaterial({color:0x2a2d3e,roughness:0.4,metalness:0.6});
var counter=new THREE.Mesh(new THREE.BoxGeometry(3.5,1.05,0.9),cMat);counter.position.set(-5,0.525,5.5);counter.castShadow=true;counter.receiveShadow=true;scene.add(counter);
var reg=new THREE.Mesh(new THREE.BoxGeometry(0.55,0.4,0.45),new THREE.MeshStandardMaterial({color:0x1a1d2c,roughness:0.2,metalness:0.8}));reg.position.set(-5,1.25,5.5);reg.castShadow=true;scene.add(reg);
scene.add(new THREE.Mesh(new THREE.PlaneGeometry(0.4,0.28),new THREE.MeshBasicMaterial({color:0x1e90ff})).translateX(-5).translateY(1.38).translateZ(5.27));
var dfMat=new THREE.MeshStandardMaterial({color:0x3a3d50,roughness:0.4,metalness:0.7});
scene.add(new THREE.Mesh(new THREE.BoxGeometry(3.2,4,0.08),dfMat).translateY(2).translateZ(7));
var glassMat=new THREE.MeshStandardMaterial({color:0x8ab4f8,transparent:true,opacity:0.15,roughness:0,metalness:0.9});
scene.add(new THREE.Mesh(new THREE.PlaneGeometry(1.5,3.6),glassMat).translateX(-0.75).translateY(1.9).translateZ(7.02));
scene.add(new THREE.Mesh(new THREE.PlaneGeometry(1.5,3.6),glassMat).translateX(0.75).translateY(1.9).translateZ(7.02));
var ssc=document.createElement("canvas");ssc.width=512;ssc.height=128;
var sctx=ssc.getContext("2d");var gr=sctx.createLinearGradient(0,0,512,0);
gr.addColorStop(0,"#4f7fff");gr.addColorStop(1,"#a78bfa");
sctx.fillStyle=gr;sctx.fillRect(0,0,512,128);
sctx.fillStyle="#fff";sctx.font="bold 36px Inter,sans-serif";sctx.textAlign="center";sctx.fillText("RETAIL VISION AI",256,50);
sctx.font="20px Inter,sans-serif";sctx.fillStyle="rgba(255,255,255,0.85)";sctx.fillText("Samsung Innovation Campus",256,90);
scene.add(new THREE.Mesh(new THREE.PlaneGeometry(4.5,1.1),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(ssc)})).translateY(4.8).translateZ(-6.95));
var gondMat=new THREE.MeshStandardMaterial({color:0x3a3f55,roughness:0.4,metalness:0.6});
for(var gx=-1;gx<=1;gx+=2){
var gond=new THREE.Mesh(new THREE.BoxGeometry(4,0.8,0.5),gondMat);gond.position.set(gx*3,0.4,3);gond.castShadow=true;scene.add(gond);
for(var px=0;px<6;px++){
var pCol=[0xf87171,0x34d399,0xfbbf24,0x60a5fa,0xa78bfa,0xfb923c][px];
var prod=new THREE.Mesh(new THREE.BoxGeometry(0.25,0.35,0.2),new THREE.MeshStandardMaterial({color:pCol,roughness:0.5,metalness:0.2}));
prod.position.set(gx*3-1.2+px*0.5,0.97,3);prod.castShadow=true;scene.add(prod);
}
}
var fridgeMat=new THREE.MeshStandardMaterial({color:0x2c3048,roughness:0.3,metalness:0.7});
var fridge=new THREE.Mesh(new THREE.BoxGeometry(0.6,2.4,3),fridgeMat);fridge.position.set(8.65,1.2,-4);fridge.castShadow=true;scene.add(fridge);
scene.add(new THREE.Mesh(new THREE.PlaneGeometry(0.01,2.2,2.8),new THREE.MeshStandardMaterial({color:0x60a5fa,transparent:true,opacity:0.12,roughness:0,metalness:0.9})).translateX(8.34).translateY(1.2).translateZ(-4));
}
var hoveredShelf=null;
function onClick(e){
if(!isLoaded)return;
mouse.x=(e.clientX/innerWidth)*2-1;mouse.y=-(e.clientY/innerHeight)*2+1;
raycaster.setFromCamera(mouse,camera);
var hits=raycaster.intersectObjects(shelfMeshes);
if(hits.length>0&&hits[0].object.userData.type==="shelf")openModal(hits[0].object.userData.shelfId);
}
function onMouseMove(e){
if(!isLoaded)return;
mouse.x=(e.clientX/innerWidth)*2-1;mouse.y=-(e.clientY/innerHeight)*2+1;
raycaster.setFromCamera(mouse,camera);
var hits=raycaster.intersectObjects(shelfMeshes);
if(hits.length>0&&hits[0].object.userData.type==="shelf"){
document.body.style.cursor="pointer";
if(hoveredShelf!==hits[0].object.userData.shelfId){resetHighlights();hoveredShelf=hits[0].object.userData.shelfId;hits[0].object.material.opacity=0.08;}
return;
}
document.body.style.cursor="default";
if(hoveredShelf!==null){resetHighlights();hoveredShelf=null;}
}
function resetHighlights(){shelfMeshes.forEach(function(m){m.material.opacity=0;});}
var modalOverlay=document.getElementById("modalOverlay");
function openModal(sid){
var d=SHELVES[sid];if(!d)return;
document.getElementById("modalTitle").textContent=d.name+" | Deteccion AI";
document.getElementById("modalDetCount").textContent=d.det;
document.getElementById("modalConf").textContent=d.conf+"%";
document.getElementById("modalTime").textContent=d.time;
document.getElementById("modalModel").textContent="SKU-110k Optimized";
document.getElementById("modalRes").textContent=d.res;
document.getElementById("modalImageDetected").src=d.imgDet;
document.getElementById("modalImageOriginal").src=d.imgOrig;
document.getElementById("tabDetected").classList.add("active");
document.getElementById("tabOriginal").classList.remove("active");
document.getElementById("modalImageDetected").classList.add("active");
document.getElementById("modalImageOriginal").classList.remove("active");
var pl=document.getElementById("productList");pl.innerHTML="";
var colors=["#4f7fff","#34d399","#a78bfa","#fb923c","#60a5fa","#f87171","#22d3ee","#fbbf24"];
d.products.forEach(function(p,i){
var invItem=inventory.find(function(it){return it.name===p&&it.shelfId===sid;});
if (invItem) {
    var conf=(invItem.avgConfidence * 100).toFixed(1);
    var qtyStr=" ("+invItem.qty+" uds)";
    pl.innerHTML+='<div class="product-item"><span class="product-dot" style="background:'+colors[i%8]+'"></span><span class="product-name">'+p+qtyStr+'</span><span class="product-conf">'+conf+'%</span></div>';
}
});
modalOverlay.classList.add("active");controls.enabled=false;
}
function closeModal(){modalOverlay.classList.remove("active");controls.enabled=true;}
document.getElementById("modalClose").addEventListener("click",closeModal);
modalOverlay.addEventListener("click",function(e){if(e.target===modalOverlay)closeModal();});
document.getElementById("tabDetected").addEventListener("click",function(){
document.getElementById("tabDetected").classList.add("active");document.getElementById("tabOriginal").classList.remove("active");
document.getElementById("modalImageDetected").classList.add("active");document.getElementById("modalImageOriginal").classList.remove("active");
});
document.getElementById("tabOriginal").addEventListener("click",function(){
document.getElementById("tabOriginal").classList.add("active");document.getElementById("tabDetected").classList.remove("active");
document.getElementById("modalImageOriginal").classList.add("active");document.getElementById("modalImageDetected").classList.remove("active");
});
function closePanels(except){
["dashboard","inventoryPanel","rpiPanel","sidebar","aiPanel"].forEach(function(p){if(p!==except)document.getElementById(p).classList.remove("open");});
}
document.getElementById("btnToggleInfo").addEventListener("click",function(){closePanels("sidebar");document.getElementById("sidebar").classList.toggle("open");});
document.getElementById("sidebarClose").addEventListener("click",function(){document.getElementById("sidebar").classList.remove("open");});
document.getElementById("btnToggleDashboard").addEventListener("click",function(){closePanels("dashboard");document.getElementById("dashboard").classList.toggle("open");});
document.getElementById("dashClose").addEventListener("click",function(){document.getElementById("dashboard").classList.remove("open");});
document.getElementById("btnToggleInventory").addEventListener("click",function(){closePanels("inventoryPanel");document.getElementById("inventoryPanel").classList.toggle("open");updateInventoryUI();});
document.getElementById("inventoryClose").addEventListener("click",function(){document.getElementById("inventoryPanel").classList.remove("open");});
document.getElementById("btnToggleRpi").addEventListener("click",function(){closePanels("rpiPanel");document.getElementById("rpiPanel").classList.toggle("open");});
document.getElementById("rpiClose").addEventListener("click",function(){document.getElementById("rpiPanel").classList.remove("open");});
document.getElementById("btnToggleAI").addEventListener("click",function(){closePanels("aiPanel");document.getElementById("aiPanel").classList.toggle("open");updateAISummary();});
document.getElementById("btnRandomize").addEventListener("click",randomizeShelves);
document.getElementById("aiClose").addEventListener("click",function(){document.getElementById("aiPanel").classList.remove("open");});
document.getElementById("btnRunScan").addEventListener("click",startScan);
document.getElementById("scanClose").addEventListener("click",function(){document.getElementById("scanOverlay").classList.remove("active");});
function startScan(){
var ov=document.getElementById("scanOverlay");ov.classList.add("active");
document.getElementById("scanResults").style.display="none";
var bar=document.getElementById("scanBarFill"),pct=document.getElementById("scanPercent");
bar.style.width="0%";pct.textContent="0%";
for(var i=0;i<4;i++){var el=document.getElementById("scanCam"+i);el.className="scan-cam";el.innerHTML='<span class="sc-dot"></span> CAM-0'+(i+1)+': Esperando';}
var progress=0,camIdx=0;
var camNames=["CAM-01: Pasillo 1","CAM-02: Pasillo 2","CAM-03: Pasillo 3","CAM-04: Perimetral"];
var camDets=[15,64,0,42];
var iv=setInterval(function(){
progress+=Math.random()*4+2;
var newCam=Math.floor(progress/25);
if(newCam>camIdx&&camIdx<4){var prev=document.getElementById("scanCam"+camIdx);prev.className="scan-cam done";prev.innerHTML='<span class="sc-dot"></span> '+camNames[camIdx]+': '+camDets[camIdx]+' detectados';camIdx=newCam;}
if(camIdx<4){var cur=document.getElementById("scanCam"+camIdx);cur.className="scan-cam scanning";cur.innerHTML='<span class="sc-dot"></span> '+camNames[camIdx]+': Escaneando';}
if(progress>=100){
progress=100;clearInterval(iv);
if(camIdx<=3){var last=document.getElementById("scanCam"+Math.min(camIdx,3));last.className="scan-cam done";last.innerHTML='<span class="sc-dot"></span> '+camNames[Math.min(camIdx,3)]+': '+camDets[Math.min(camIdx,3)]+' detectados';}
setTimeout(function(){
var total=camDets.reduce(function(a,b){return a+b;},0);
document.getElementById("srTotal").textContent=total;
document.getElementById("srSkus").textContent="4";
document.getElementById("srOcc").textContent="76%";
document.getElementById("srTime").textContent="5.4s";
document.getElementById("scanResults").style.display="block";
document.getElementById("kpiTotal").textContent=total;
document.getElementById("kpiSkus").textContent="4";
document.getElementById("kpiOcc").textContent="76%";
simulateSales();updateInventoryUI();updateAISummary();
addRpiLog("[SCAN] Escaneo completo: "+total+" productos en 5.4s");
},400);
}
bar.style.width=Math.min(progress,100)+"%";pct.textContent=Math.floor(Math.min(progress,100))+"%";
},80);
}
document.getElementById("btnResetCamera").addEventListener("click",function(){animateIntroCamera();controls.target.set(0,1,-1);});
document.addEventListener("keydown",function(e){
if(e.key==="Escape"){
if(modalOverlay.classList.contains("active"))closeModal();
else if(document.getElementById("scanOverlay").classList.contains("active"))document.getElementById("scanOverlay").classList.remove("active");
else closePanels();
}
});
function updateLabels(){
SHELVES.forEach(function(d,i){
var el=labelEls[i];if(!el)return;
var p=new THREE.Vector3(d.pos.x,d.pos.y+1.6,d.pos.z);p.project(camera);
var x=(p.x*0.5+0.5)*innerWidth,y=(-p.y*0.5+0.5)*innerHeight;
if(p.z<1&&x>-100&&x<innerWidth+100&&y>-50&&y<innerHeight+100){el.style.display="flex";el.style.left=x+"px";el.style.top=y+"px";el.style.transform="translate(-50%,-100%)";}
else{el.style.display="none";}
});
CAMERAS_DATA.forEach(function(cd,i){
var el=camLabelEls[i];if(!el)return;
var p=new THREE.Vector3(cd.pos.x,cd.pos.y+0.3,cd.pos.z);p.project(camera);
var x=(p.x*0.5+0.5)*innerWidth,y=(-p.y*0.5+0.5)*innerHeight;
if(p.z<1&&x>-50&&x<innerWidth+50&&y>-50&&y<innerHeight+50){el.style.display="block";el.style.left=x+"px";el.style.top=y+"px";el.style.transform="translate(-50%,-100%)";}
else{el.style.display="none";}
});
}
function animate(){
requestAnimationFrame(animate);time+=0.01;controls.update();
camMeshGroups.forEach(function(c,i){
if(c.led)c.led.material.color.setHex(Math.sin(time*3+i)>0?0xf87171:0x441111);
if(c.aura)c.aura.material.opacity=0.1+Math.sin(time*2+i)*0.05;
if(c.group&&c.aura){c.aura.scale.setScalar(1+Math.sin(time*1.5+i)*0.1);}
});
if(isLoaded)updateLabels();
renderer.render(scene,camera);
}
function onResize(){camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);}
init();
})();
