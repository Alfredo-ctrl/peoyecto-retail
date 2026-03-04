(function () {
"use strict";

var SHELVES = [
    { id:0, name:"Abarrotes", cat:"Abarrotes y productos generales", det:42, conf:94, time:"2.1s", res:"1280x720",
      imgOrig:"images/shelf_abarrotes.png", imgDet:"images/shelf_abarrotes_det.png",
      pos:{x:-4.5,y:1.2,z:-3.8}, products:["Frijoles","Arroz","Aceite","Atun","Sopa","Sal","Azucar","Harina","Pasta","Salsa"] },
    { id:1, name:"Bebidas", cat:"Bebidas, jugos y refrescos", det:38, conf:96, time:"1.8s", res:"1280x720",
      imgOrig:"images/shelf_bebidas.png", imgDet:"images/shelf_bebidas_det.png",
      pos:{x:-1.5,y:1.2,z:-3.8}, products:["Coca-Cola","Pepsi","Agua","Jugo","Sprite","Fanta","Gatorade","Leche"] },
    { id:2, name:"Snacks", cat:"Snacks, botanas y dulces", det:56, conf:92, time:"2.3s", res:"1280x720",
      imgOrig:"images/shelf_snacks.png", imgDet:"images/shelf_snacks_det.png",
      pos:{x:1.5,y:1.2,z:-3.8}, products:["Doritos","Sabritas","Ruffles","Takis","Oreo","Emperador","Galletas","Cacahuates"] },
    { id:3, name:"Limpieza", cat:"Productos de limpieza", det:31, conf:95, time:"1.9s", res:"1280x720",
      imgOrig:"images/shelf_limpieza.png", imgDet:"images/shelf_limpieza.png",
      pos:{x:4.5,y:1.2,z:-3.8}, products:["Fabuloso","Cloralex","Pinol","Jabon","Detergente","Suavitel","Escoba"] },
    { id:4, name:"Lacteos", cat:"Lacteos y refrigerados", det:28, conf:93, time:"2.0s", res:"1280x720",
      imgOrig:"images/shelf_lacteos.png", imgDet:"images/shelf_lacteos.png",
      pos:{x:-4.5,y:1.2,z:0}, products:["Leche","Yogurt","Queso","Mantequilla","Crema","Huevo"] },
    { id:5, name:"Dulces", cat:"Dulces y confiteria", det:44, conf:91, time:"2.2s", res:"1280x720",
      imgOrig:"images/shelf_snacks.png", imgDet:"images/shelf_snacks_det.png",
      pos:{x:4.5,y:1.2,z:0}, products:["Chocolate","Gomitas","Paletas","Chicles","Mazapan","Lunetas"] },
    { id:6, name:"Higiene", cat:"Higiene personal", det:33, conf:94, time:"1.7s", res:"1280x720",
      imgOrig:"images/shelf_limpieza.png", imgDet:"images/shelf_limpieza.png",
      pos:{x:-1.5,y:1.2,z:0}, products:["Shampoo","Jabon","Pasta dental","Desodorante","Rastrillo","Toallas"] },
    { id:7, name:"Cereales", cat:"Cereales y desayuno", det:25, conf:97, time:"1.5s", res:"1280x720",
      imgOrig:"images/shelf_abarrotes.png", imgDet:"images/shelf_abarrotes_det.png",
      pos:{x:1.5,y:1.2,z:0}, products:["Zucaritas","Corn Flakes","Cheerios","Granola","Avena","Barra"] }
];

var CAMERAS_DATA = [
    { id:0, name:"CAM-01", type:"PTZ", covers:[0,4], pos:{x:-4.5,y:4.6,z:-1.9}, lookAt:{x:-4.5,y:1,z:-1.9}, color:0x4f7fff },
    { id:1, name:"CAM-02", type:"Domo", covers:[1,6], pos:{x:-1.5,y:4.6,z:-1.9}, lookAt:{x:-1.5,y:1,z:-1.9}, color:0x34d399 },
    { id:2, name:"CAM-03", type:"PTZ", covers:[2,7], pos:{x:1.5,y:4.6,z:-1.9}, lookAt:{x:1.5,y:1,z:-1.9}, color:0xa78bfa },
    { id:3, name:"CAM-04", type:"Domo", covers:[3,5], pos:{x:4.5,y:4.6,z:-1.9}, lookAt:{x:4.5,y:1,z:-1.9}, color:0xfb923c }
];

var inventory = [];
var scanCycleTimer = null;
var currentScanCam = -1;

function initInventory() {
    inventory = [];
    SHELVES.forEach(function(shelf) {
        shelf.products.forEach(function(prod) {
            var maxQty = Math.floor(Math.random() * 30) + 20;
            var qty = Math.floor(Math.random() * maxQty * 0.7) + Math.floor(maxQty * 0.2);
            inventory.push({
                name: prod,
                section: shelf.name,
                shelfId: shelf.id,
                qty: qty,
                maxQty: maxQty,
                lastScan: Date.now() - Math.floor(Math.random() * 300000),
                trend: Math.random() > 0.5 ? "down" : "stable"
            });
        });
    });
}

function getStockStatus(item) {
    var ratio = item.qty / item.maxQty;
    if (ratio <= 0) return { label: "Agotado", cls: "stock-out" };
    if (ratio < 0.25) return { label: "Critico", cls: "stock-critical" };
    if (ratio < 0.5) return { label: "Bajo", cls: "stock-low" };
    return { label: "OK", cls: "stock-ok" };
}

function simulateSales() {
    inventory.forEach(function(item) {
        if (Math.random() < 0.3) {
            var sold = Math.floor(Math.random() * 3) + 1;
            item.qty = Math.max(0, item.qty - sold);
        }
        if (Math.random() < 0.08 && item.qty < item.maxQty * 0.3) {
            var restock = Math.floor(Math.random() * 10) + 5;
            item.qty = Math.min(item.maxQty, item.qty + restock);
        }
    });
}

function updateInventoryUI() {
    var tbody = document.getElementById("invTableBody");
    if (!tbody) return;
    var html = "";
    var totalUnits = 0, okCount = 0, lowCount = 0, outCount = 0;

    inventory.forEach(function(item, i) {
        var st = getStockStatus(item);
        totalUnits += item.qty;
        if (st.cls === "stock-ok") okCount++;
        else if (st.cls === "stock-out") outCount++;
        else lowCount++;

        var pct = Math.round((item.qty / item.maxQty) * 100);
        var action = st.cls === "stock-ok" ? "-" : "Pedir";
        html += '<tr class="inv-row ' + st.cls + '-row">' +
            '<td class="inv-prod-name">' + item.name + '</td>' +
            '<td>' + item.section + '</td>' +
            '<td><div class="inv-qty-bar"><div class="inv-qty-fill ' + st.cls + '" style="width:' + pct + '%"></div></div><span class="inv-qty-num">' + item.qty + '</span></td>' +
            '<td>' + item.maxQty + '</td>' +
            '<td><span class="inv-badge ' + st.cls + '">' + st.label + '</span></td>' +
            '<td>' + (action === "Pedir" ? '<button class="inv-btn-order" data-idx="' + i + '">Pedir</button>' : '<span class="inv-action-ok">-</span>') + '</td>' +
            '</tr>';
    });

    tbody.innerHTML = html;
    var tp = document.getElementById("invTotalProducts");
    var so = document.getElementById("invStockOk");
    var sl = document.getElementById("invStockLow");
    var sout = document.getElementById("invStockOut");
    if (tp) tp.textContent = totalUnits;
    if (so) so.textContent = okCount;
    if (sl) sl.textContent = lowCount;
    if (sout) sout.textContent = outCount;

    var alertsList = document.getElementById("invAlertsList");
    if (alertsList) {
        var alertsHtml = "";
        inventory.forEach(function(item) {
            var st = getStockStatus(item);
            if (st.cls !== "stock-ok") {
                var needed = item.maxQty - item.qty;
                alertsHtml += '<div class="inv-alert-item ' + st.cls + '-alert">' +
                    '<span class="inv-alert-icon">' + (st.cls === "stock-out" ? "!" : "\u26A0") + '</span>' +
                    '<div><strong>' + item.name + '</strong> (' + item.section + ')<br>' +
                    '<small>Pedir ' + needed + ' unidades — Stock: ' + item.qty + '/' + item.maxQty + '</small></div></div>';
            }
        });
        if (!alertsHtml) alertsHtml = '<div class="inv-alert-ok">Todo el inventario esta en niveles optimos</div>';
        alertsList.innerHTML = alertsHtml;
    }

    var lastScan = document.getElementById("invLastScan");
    if (lastScan) {
        var now = new Date();
        lastScan.textContent = "Ultimo: " + now.getHours().toString().padStart(2, "0") + ":" + now.getMinutes().toString().padStart(2, "0") + ":" + now.getSeconds().toString().padStart(2, "0");
    }
}

function startContinuousScanning() {
    if (scanCycleTimer) return;
    var camIdx = 0;
    scanCycleTimer = setInterval(function() {
        currentScanCam = camIdx;
        simulateSales();
        inventory.forEach(function(item) {
            if (CAMERAS_DATA[camIdx].covers.indexOf(item.shelfId) !== -1) {
                item.lastScan = Date.now();
                var change = Math.floor(Math.random() * 5) - 2;
                item.qty = Math.max(0, Math.min(item.maxQty, item.qty + change));
            }
        });
        updateInventoryUI();
        addRpiLog("[SCAN] " + CAMERAS_DATA[camIdx].name + " (" + CAMERAS_DATA[camIdx].type + ") Estantes: " +
            CAMERAS_DATA[camIdx].covers.map(function(c) { return SHELVES[c].name; }).join(", "));
        camIdx = (camIdx + 1) % 4;
    }, 8000);
}

var rpiStats = { cpu: 42, ram: 58, temp: 51, npu: 67 };

function updateRpiUI() {
    rpiStats.cpu = Math.max(15, Math.min(95, rpiStats.cpu + (Math.random() * 10 - 5)));
    rpiStats.ram = Math.max(40, Math.min(85, rpiStats.ram + (Math.random() * 4 - 2)));
    rpiStats.temp = Math.max(38, Math.min(72, rpiStats.temp + (Math.random() * 3 - 1.5)));
    rpiStats.npu = Math.max(20, Math.min(98, rpiStats.npu + (Math.random() * 8 - 4)));

    var els = [
        { bar: "rpiCpu", val: "rpiCpuVal", v: rpiStats.cpu, suffix: "%" },
        { bar: "rpiRam", val: "rpiRamVal", v: rpiStats.ram, suffix: "%" },
        { bar: "rpiTemp", val: "rpiTempVal", v: rpiStats.temp, suffix: "C" },
        { bar: "rpiNpu", val: "rpiNpuVal", v: rpiStats.npu, suffix: "%" }
    ];
    els.forEach(function(e) {
        var barEl = document.getElementById(e.bar);
        var valEl = document.getElementById(e.val);
        if (barEl) barEl.style.width = Math.round(e.v) + "%";
        if (valEl) valEl.textContent = Math.round(e.v) + e.suffix;
    });

    for (var i = 0; i < 4; i++) {
        var fpsEl = document.getElementById("rpiCamFps" + i);
        if (fpsEl) fpsEl.textContent = (28 + Math.floor(Math.random() * 5)) + " FPS";
    }

    var led = document.getElementById("rpiHatLed");
    if (led) led.classList.toggle("rpi-led-blink");
    var gpioLed = document.getElementById("rpiGpioLed");
    if (gpioLed) gpioLed.classList.toggle("rpi-gpio-active");
}

function addRpiLog(msg) {
    var log = document.getElementById("rpiLog");
    if (!log) return;
    var entry = document.createElement("div");
    entry.className = "rpi-log-entry rpi-log-new";
    var now = new Date();
    entry.textContent = "[" + now.getHours().toString().padStart(2, "0") + ":" +
        now.getMinutes().toString().padStart(2, "0") + ":" +
        now.getSeconds().toString().padStart(2, "0") + "] " + msg;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
    if (log.children.length > 50) log.removeChild(log.children[0]);
}

var scene, camera, renderer, controls;
var shelfMeshes = [], camMeshGroups = [], labelEls = [], camLabelEls = [];
var raycaster, mouse;
var isLoaded = false, time = 0;

function init() {
    try {
        var canvas = document.getElementById("canvas3d");
        scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0a0d16);
        scene.fog = new THREE.FogExp2(0x0a0d16, 0.012);

        camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 0.1, 100);
        camera.position.set(0, 6, 12);

        renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
        renderer.setSize(innerWidth, innerHeight);
        renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        renderer.outputEncoding = THREE.sRGBEncoding;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.3;

        controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.08;
        controls.minDistance = 4;
        controls.maxDistance = 20;
        controls.maxPolarAngle = Math.PI / 2.05;
        controls.target.set(0, 1, -1);

        raycaster = new THREE.Raycaster();
        mouse = new THREE.Vector2();

        buildStore();
        addLighting();
        buildAllShelves();
        buildAllCameras();
        buildDecorations();

        addEventListener("resize", onResize);
        canvas.addEventListener("click", onClick);
        canvas.addEventListener("mousemove", onMouseMove);

        for (var i = 0; i < SHELVES.length; i++) labelEls.push(document.getElementById("label3d_" + i));
        for (var j = 0; j < CAMERAS_DATA.length; j++) camLabelEls.push(document.getElementById("camLabel" + j));

        initInventory();
        updateInventoryUI();
        startContinuousScanning();

        setInterval(updateRpiUI, 2000);
        setInterval(function() {
            var msgs = [
                "[INFER] Frame procesado: " + (Math.floor(Math.random() * 50) + 10) + " detecciones, " + (1.2 + Math.random() * 1.5).toFixed(1) + "s",
                "[NPU] Throughput: " + (Math.floor(Math.random() * 5) + 10) + " TOPS activos",
                "[MEM] Buffer frames: " + (Math.floor(Math.random() * 3) + 1) + "/4 camaras procesadas",
                "[NET] Sync inventario: " + (Math.floor(Math.random() * 20) + 5) + " registros actualizados",
                "[TEMP] Core temp: " + Math.round(rpiStats.temp) + "C — Throttle: OFF",
                "[CAM] PTZ reposicionando a estante " + SHELVES[Math.floor(Math.random() * 8)].name
            ];
            addRpiLog(msgs[Math.floor(Math.random() * msgs.length)]);
        }, 5000);

        animate();
        simulateLoading();
    } catch (err) {
        console.error("[RetailVisionAI] Init error:", err);
        document.getElementById("loadingScreen").classList.add("hidden");
        document.getElementById("topBar").classList.add("visible");
    }
}

function simulateLoading() {
    var bar = document.getElementById("loadingBarFill");
    var steps = ["ls1", "ls2", "ls3", "ls4"];
    var progress = 0, stepIdx = 0;
    var iv = setInterval(function() {
        progress += Math.random() * 18 + 8;
        if (progress > (stepIdx + 1) * 25 && stepIdx < steps.length) {
            var el = document.getElementById(steps[stepIdx]);
            if (el) { el.classList.remove("active"); el.classList.add("done"); }
            stepIdx++;
            if (stepIdx < steps.length) {
                var next = document.getElementById(steps[stepIdx]);
                if (next) next.classList.add("active");
            }
        }
        if (progress >= 100) {
            progress = 100; clearInterval(iv);
            setTimeout(function() {
                document.getElementById("loadingScreen").classList.add("hidden");
                document.getElementById("topBar").classList.add("visible");
                document.getElementById("hudHint").classList.add("visible");
                isLoaded = true;
                animateIntroCamera();
            }, 300);
        }
        bar.style.width = progress + "%";
    }, 120);
}

function animateIntroCamera() {
    var s = { x: 0, y: 10, z: 16 }, e = { x: 2, y: 5, z: 10 };
    var dur = 2500, st = Date.now();
    camera.position.set(s.x, s.y, s.z);
    (function step() {
        var t = Math.min((Date.now() - st) / dur, 1), ease = 1 - Math.pow(1 - t, 3);
        camera.position.set(s.x + (e.x - s.x) * ease, s.y + (e.y - s.y) * ease, s.z + (e.z - s.z) * ease);
        if (t < 1) requestAnimationFrame(step);
    })();
}

function buildStore() {
    var floorMat = new THREE.MeshStandardMaterial({ color: 0x1a1e2e, roughness: 0.8, metalness: 0.05 });
    var floor = new THREE.Mesh(new THREE.PlaneGeometry(18, 14), floorMat);
    floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true;
    scene.add(floor);

    var tileGeo = new THREE.PlaneGeometry(17.8, 13.8);
    var tileMat = new THREE.MeshStandardMaterial({ color: 0x222640, roughness: 0.9, metalness: 0 });
    var tiles = new THREE.Mesh(tileGeo, tileMat);
    tiles.rotation.x = -Math.PI / 2; tiles.position.y = 0.001; tiles.receiveShadow = true;
    scene.add(tiles);

    var grid = new THREE.GridHelper(18, 36, 0x1c2038, 0x151828);
    grid.position.y = 0.005; scene.add(grid);

    var wallMat = new THREE.MeshStandardMaterial({ color: 0x181c2e, roughness: 0.85, metalness: 0.05 });
    var bw = new THREE.Mesh(new THREE.PlaneGeometry(18, 5.5), wallMat);
    bw.position.set(0, 2.75, -7); bw.receiveShadow = true; scene.add(bw);
    var lw = new THREE.Mesh(new THREE.PlaneGeometry(14, 5.5), wallMat);
    lw.position.set(-9, 2.75, 0); lw.rotation.y = Math.PI / 2; lw.receiveShadow = true; scene.add(lw);
    var rw = new THREE.Mesh(new THREE.PlaneGeometry(14, 5.5), wallMat);
    rw.position.set(9, 2.75, 0); rw.rotation.y = -Math.PI / 2; rw.receiveShadow = true; scene.add(rw);
    var fw1 = new THREE.Mesh(new THREE.PlaneGeometry(6, 5.5), wallMat);
    fw1.position.set(-6, 2.75, 7); fw1.rotation.y = Math.PI; scene.add(fw1);
    var fw2 = new THREE.Mesh(new THREE.PlaneGeometry(6, 5.5), wallMat);
    fw2.position.set(6, 2.75, 7); fw2.rotation.y = Math.PI; scene.add(fw2);
    var ceil = new THREE.Mesh(new THREE.PlaneGeometry(18, 14), new THREE.MeshStandardMaterial({ color: 0x151830, roughness: 0.9 }));
    ceil.position.y = 5.5; ceil.rotation.x = Math.PI / 2; scene.add(ceil);

    var baseMat = new THREE.MeshBasicMaterial({ color: 0x4f7fff });
    var base = new THREE.Mesh(new THREE.BoxGeometry(18, 0.03, 0.02), baseMat);
    base.position.set(0, 0.015, -6.98); scene.add(base);
    var baseL = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.03, 14), baseMat);
    baseL.position.set(-8.98, 0.015, 0); scene.add(baseL);
    var baseR = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.03, 14), baseMat);
    baseR.position.set(8.98, 0.015, 0); scene.add(baseR);
}

function addLighting() {
    scene.add(new THREE.AmbientLight(0xb0bcdd, 0.7));
    scene.add(new THREE.HemisphereLight(0x80a0ff, 0x2a2d3c, 0.5));

    for (var row = -1; row <= 1; row += 2) {
        for (var col = -1; col <= 1; col++) {
            var fl = new THREE.RectAreaLight(0xdde4ff, 3, 2.5, 0.15);
            fl.position.set(col * 3, 5.45, row * 2.5);
            fl.rotation.x = Math.PI / 2;
            scene.add(fl);
            var tube = new THREE.Mesh(new THREE.BoxGeometry(2.5, 0.04, 0.12),
                new THREE.MeshBasicMaterial({ color: 0xccd4ee }));
            tube.position.set(col * 3, 5.46, row * 2.5); scene.add(tube);
        }
    }

    var spotCols = [0x4f7fff, 0x34d399, 0xa78bfa, 0xfb923c];
    for (var i = 0; i < 4; i++) {
        var sp = new THREE.SpotLight(spotCols[i], 0.8, 16, Math.PI / 4, 0.5, 0.8);
        sp.position.set(-4.5 + i * 3, 5.2, -1.5);
        sp.target.position.set(-4.5 + i * 3, 0, -2);
        sp.castShadow = true;
        sp.shadow.mapSize.set(512, 512);
        scene.add(sp); scene.add(sp.target);
    }

    var fill = new THREE.PointLight(0xffffff, 0.5, 25);
    fill.position.set(0, 4, 4); scene.add(fill);
    var bf = new THREE.PointLight(0x6080ff, 0.3, 20);
    bf.position.set(0, 3, 8); scene.add(bf);
}

function buildAllShelves() {
    var edgeCols = [0x4f7fff, 0x34d399, 0xa78bfa, 0xfb923c, 0x22d3ee, 0xf87171, 0x60a5fa, 0xfbbf24];
    var cats = ["ABARROTES", "BEBIDAS", "SNACKS", "LIMPIEZA", "LACTEOS", "DULCES", "HIGIENE", "CEREALES"];

    SHELVES.forEach(function(d, i) {
        var g = new THREE.Group();
        g.position.set(d.pos.x, 0, d.pos.z);

        var frameMat = new THREE.MeshStandardMaterial({ color: 0x3a3f55, roughness: 0.3, metalness: 0.8 });
        var boardMat = new THREE.MeshStandardMaterial({ color: 0x4a4f68, roughness: 0.5, metalness: 0.4 });
        var backMat = new THREE.MeshStandardMaterial({ color: 0x282c42, roughness: 0.85, metalness: 0.1 });

        var supGeo = new THREE.BoxGeometry(0.05, 2.6, 0.05);
        [[-1, 0], [1, 0]].forEach(function(p) {
            var s = new THREE.Mesh(supGeo, frameMat);
            s.position.set(p[0], 1.3, p[1]); s.castShadow = true; g.add(s);
        });

        var bGeo = new THREE.BoxGeometry(2.1, 0.035, 0.45);
        for (var lv = 0; lv < 4; lv++) {
            var b = new THREE.Mesh(bGeo, boardMat);
            b.position.set(0, 0.3 + lv * 0.7, 0);
            b.castShadow = true; b.receiveShadow = true; g.add(b);
        }
        var tb = new THREE.Mesh(bGeo, boardMat);
        tb.position.set(0, 2.6, 0); tb.castShadow = true; g.add(tb);

        var bp = new THREE.Mesh(new THREE.PlaneGeometry(2.1, 2.6), backMat);
        bp.position.set(0, 1.3, -0.22); bp.receiveShadow = true; g.add(bp);

        var prodCanvas = document.createElement("canvas");
        prodCanvas.width = 512; prodCanvas.height = 160;
        var pctx = prodCanvas.getContext("2d");
        var productPalettes = [
            ["#e74c3c", "#f39c12", "#27ae60", "#3498db", "#9b59b6", "#e67e22", "#1abc9c", "#c0392b"],
            ["#2ecc71", "#e74c3c", "#f1c40f", "#3498db", "#e67e22", "#1abc9c", "#9b59b6", "#d35400"],
            ["#f1c40f", "#e74c3c", "#9b59b6", "#2ecc71", "#e67e22", "#3498db", "#c0392b", "#1abc9c"],
            ["#3498db", "#27ae60", "#f39c12", "#e74c3c", "#8e44ad", "#16a085", "#d35400", "#2980b9"],
            ["#ecf0f1", "#3498db", "#f39c12", "#e74c3c", "#2ecc71", "#ecf0f1", "#f1c40f", "#bdc3c7"],
            ["#e74c3c", "#f1c40f", "#e67e22", "#9b59b6", "#2ecc71", "#3498db", "#c0392b", "#f39c12"],
            ["#1abc9c", "#3498db", "#ecf0f1", "#9b59b6", "#2ecc71", "#f39c12", "#e67e22", "#27ae60"],
            ["#f39c12", "#e74c3c", "#27ae60", "#3498db", "#f1c40f", "#9b59b6", "#e67e22", "#2ecc71"]
        ];
        var pal = productPalettes[i] || productPalettes[0];
        pctx.fillStyle = "#1a1e2e"; pctx.fillRect(0, 0, 512, 160);
        for (var px = 0; px < 8; px++) {
            var x = 10 + px * 62;
            pctx.fillStyle = pal[px];
            pctx.fillRect(x, 20, 52, 120);
            pctx.fillStyle = "rgba(255,255,255,0.2)";
            pctx.fillRect(x + 5, 50, 42, 30);
            pctx.fillStyle = "rgba(0,0,0,0.3)";
            pctx.fillRect(x + 10, 15, 32, 10);
        }
        var prodTex = new THREE.CanvasTexture(prodCanvas);
        prodTex.encoding = THREE.sRGBEncoding;
        var prodMat = new THREE.MeshBasicMaterial({ map: prodTex });
        for (var lv2 = 0; lv2 < 4; lv2++) {
            var pp = new THREE.Mesh(new THREE.PlaneGeometry(1.9, 0.55), prodMat);
            pp.position.set(0, 0.62 + lv2 * 0.7, 0.01); g.add(pp);
        }

        for (var lv3 = 0; lv3 < 4; lv3++) {
            for (var px2 = 0; px2 < 6; px2++) {
                var prodCol = parseInt(pal[px2 % pal.length].replace("#", ""), 16);
                var prodBox = new THREE.Mesh(
                    new THREE.BoxGeometry(0.18 + Math.random() * 0.08, 0.25 + Math.random() * 0.2, 0.15 + Math.random() * 0.05),
                    new THREE.MeshStandardMaterial({ color: prodCol, roughness: 0.5, metalness: 0.15 })
                );
                prodBox.position.set(-0.75 + px2 * 0.32, 0.5 + lv3 * 0.7, 0.05);
                prodBox.castShadow = true; g.add(prodBox);
            }
        }

        var hb = new THREE.Mesh(
            new THREE.BoxGeometry(2.2, 2.7, 0.5),
            new THREE.MeshBasicMaterial({ color: edgeCols[i], transparent: true, opacity: 0 })
        );
        hb.position.set(0, 1.3, 0); hb.userData = { shelfId: i, type: "shelf" }; g.add(hb);
        shelfMeshes.push(hb);

        var sc = document.createElement("canvas"); sc.width = 256; sc.height = 40;
        var ctx = sc.getContext("2d");
        ctx.fillStyle = "#0e1019"; ctx.fillRect(0, 0, 256, 40);
        ctx.fillStyle = "#" + edgeCols[i].toString(16).padStart(6, "0");
        ctx.font = "bold 18px Inter,sans-serif"; ctx.textAlign = "center";
        ctx.fillText(cats[i], 128, 28);
        var signMat = new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sc) });
        var sign = new THREE.Mesh(new THREE.PlaneGeometry(1, 0.16), signMat);
        sign.position.set(0, 2.72, 0.04); g.add(sign);

        var eGeo = new THREE.EdgesGeometry(new THREE.BoxGeometry(2.15, 2.65, 0.5));
        var eMat = new THREE.LineBasicMaterial({ color: edgeCols[i], transparent: true, opacity: 0.12 });
        var wf = new THREE.LineSegments(eGeo, eMat);
        wf.position.set(0, 1.3, 0); g.add(wf);

        scene.add(g);
    });
}

function buildAllCameras() {
    var bodyMat = new THREE.MeshStandardMaterial({ color: 0x3c4058, roughness: 0.25, metalness: 0.92 });
    var darkMat = new THREE.MeshStandardMaterial({ color: 0x111320, roughness: 0.1, metalness: 1 });

    CAMERAS_DATA.forEach(function(cd) {
        var cg = new THREE.Group();
        cg.position.set(cd.pos.x, cd.pos.y, cd.pos.z);

        cg.add(new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.04, 12), bodyMat));
        var arm = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.4, 8), bodyMat);
        arm.position.y = -0.22; cg.add(arm);
        var jt = new THREE.Mesh(new THREE.SphereGeometry(0.07, 10, 10), bodyMat);
        jt.position.y = -0.44; cg.add(jt);

        var hg = new THREE.Group();
        hg.position.y = -0.44; hg.rotation.x = Math.PI / 4.5;
        var housing = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.14, 0.32), bodyMat);
        housing.castShadow = true; hg.add(housing);
        var lens = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.06, 0.09, 10), darkMat);
        lens.rotation.x = Math.PI / 2; lens.position.set(0, -0.01, 0.19); hg.add(lens);
        var glass = new THREE.Mesh(new THREE.RingGeometry(0.025, 0.05, 12),
            new THREE.MeshBasicMaterial({ color: cd.color, side: THREE.DoubleSide }));
        glass.position.set(0, -0.01, 0.245); hg.add(glass);
        var led = new THREE.Mesh(new THREE.SphereGeometry(0.018, 8, 8),
            new THREE.MeshBasicMaterial({ color: 0xf87171 }));
        led.position.set(0.07, 0.05, -0.16); hg.add(led);
        cg.add(hg);

        var beamGeo = new THREE.ConeGeometry(2.2, 4.8, 20, 1, true);
        var beamMat2 = new THREE.MeshBasicMaterial({ color: cd.color, transparent: true, opacity: 0.025, side: THREE.DoubleSide, depthWrite: false });
        var beam = new THREE.Mesh(beamGeo, beamMat2);
        beam.position.y = -2.8; cg.add(beam);

        var sp = new THREE.SpotLight(cd.color, 0.4, 12, Math.PI / 3.5, 0.6, 1.2);
        sp.position.y = -0.5; sp.target.position.set(0, -5, -1);
        sp.castShadow = true; sp.shadow.mapSize.set(512, 512);
        cg.add(sp); cg.add(sp.target);

        scene.add(cg);
        camMeshGroups.push({ group: cg, led: led, beam: beamMat2 });
    });
}

function buildDecorations() {
    var cMat = new THREE.MeshStandardMaterial({ color: 0x2a2d3e, roughness: 0.4, metalness: 0.6 });
    var counter = new THREE.Mesh(new THREE.BoxGeometry(3.5, 1.05, 0.9), cMat);
    counter.position.set(-5, 0.525, 5.5); counter.castShadow = true; counter.receiveShadow = true; scene.add(counter);
    var reg = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.4, 0.45),
        new THREE.MeshStandardMaterial({ color: 0x1a1d2c, roughness: 0.2, metalness: 0.8 }));
    reg.position.set(-5, 1.25, 5.5); reg.castShadow = true; scene.add(reg);
    var scr = new THREE.Mesh(new THREE.PlaneGeometry(0.4, 0.28),
        new THREE.MeshBasicMaterial({ color: 0x1e90ff }));
    scr.position.set(-5, 1.38, 5.27); scr.rotation.x = -0.2; scene.add(scr);

    var dfMat = new THREE.MeshStandardMaterial({ color: 0x3a3d50, roughness: 0.4, metalness: 0.7 });
    var df = new THREE.Mesh(new THREE.BoxGeometry(3.2, 4, 0.08), dfMat);
    df.position.set(0, 2, 7); scene.add(df);
    var glassMat = new THREE.MeshStandardMaterial({ color: 0x8ab4f8, transparent: true, opacity: 0.15, roughness: 0, metalness: 0.9 });
    var glass1 = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 3.6), glassMat);
    glass1.position.set(-0.75, 1.9, 7.02); scene.add(glass1);
    var glass2 = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 3.6), glassMat);
    glass2.position.set(0.75, 1.9, 7.02); scene.add(glass2);

    var ssc = document.createElement("canvas"); ssc.width = 512; ssc.height = 128;
    var sctx = ssc.getContext("2d");
    var gr = sctx.createLinearGradient(0, 0, 512, 0);
    gr.addColorStop(0, "#4f7fff"); gr.addColorStop(1, "#a78bfa");
    sctx.fillStyle = gr; sctx.fillRect(0, 0, 512, 128);
    sctx.fillStyle = "#fff"; sctx.font = "bold 36px Inter,sans-serif"; sctx.textAlign = "center";
    sctx.fillText("RETAIL VISION AI", 256, 50);
    sctx.font = "20px Inter,sans-serif"; sctx.fillStyle = "rgba(255,255,255,0.85)";
    sctx.fillText("Samsung Innovation Campus", 256, 90);
    var ssMat = new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(ssc) });
    var ss = new THREE.Mesh(new THREE.PlaneGeometry(4.5, 1.1), ssMat);
    ss.position.set(0, 4.8, -6.95); scene.add(ss);

    var gondMat = new THREE.MeshStandardMaterial({ color: 0x3a3f55, roughness: 0.4, metalness: 0.6 });
    for (var gx = -1; gx <= 1; gx += 2) {
        var gond = new THREE.Mesh(new THREE.BoxGeometry(4, 0.8, 0.5), gondMat);
        gond.position.set(gx * 3, 0.4, 3); gond.castShadow = true; scene.add(gond);
        for (var px = 0; px < 6; px++) {
            var pCol = [0xf87171, 0x34d399, 0xfbbf24, 0x60a5fa, 0xa78bfa, 0xfb923c][px];
            var prod = new THREE.Mesh(new THREE.BoxGeometry(0.25, 0.35, 0.2),
                new THREE.MeshStandardMaterial({ color: pCol, roughness: 0.5, metalness: 0.2 }));
            prod.position.set(gx * 3 - 1.2 + px * 0.5, 0.97, 3);
            prod.castShadow = true; scene.add(prod);
        }
    }

    [0xf87171, 0x34d399, 0xfbbf24].forEach(function(c, i) {
        var b = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.25, 0.3),
            new THREE.MeshStandardMaterial({ color: c, roughness: 0.6, metalness: 0.2 }));
        b.position.set(2.5, 0.125 + i * 0.26, 6); b.castShadow = true; scene.add(b);
    });

    for (var ai = -1; ai <= 1; ai++) {
        var ln = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.004, 10),
            new THREE.MeshBasicMaterial({ color: 0x4f7fff, transparent: true, opacity: 0.06 }));
        ln.position.set(ai * 3, 0.003, 0); scene.add(ln);
    }

    var fridgeMat = new THREE.MeshStandardMaterial({ color: 0x2c3048, roughness: 0.3, metalness: 0.7 });
    var fridge = new THREE.Mesh(new THREE.BoxGeometry(0.6, 2.4, 3), fridgeMat);
    fridge.position.set(8.65, 1.2, -4); fridge.castShadow = true; scene.add(fridge);
    var fridgeGlass = new THREE.Mesh(new THREE.PlaneGeometry(0.01, 2.2, 2.8),
        new THREE.MeshStandardMaterial({ color: 0x60a5fa, transparent: true, opacity: 0.12, roughness: 0, metalness: 0.9 }));
    fridgeGlass.position.set(8.34, 1.2, -4); fridgeGlass.rotation.y = -Math.PI / 2; scene.add(fridgeGlass);
}

var hoveredShelf = null;

function onClick(e) {
    if (!isLoaded) return;
    mouse.x = (e.clientX / innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / innerHeight) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    var hits = raycaster.intersectObjects(shelfMeshes);
    if (hits.length > 0 && hits[0].object.userData.type === "shelf") {
        openModal(hits[0].object.userData.shelfId);
    }
}

function onMouseMove(e) {
    if (!isLoaded) return;
    mouse.x = (e.clientX / innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / innerHeight) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    var hits = raycaster.intersectObjects(shelfMeshes);
    if (hits.length > 0 && hits[0].object.userData.type === "shelf") {
        document.body.style.cursor = "pointer";
        if (hoveredShelf !== hits[0].object.userData.shelfId) {
            resetHighlights(); hoveredShelf = hits[0].object.userData.shelfId;
            hits[0].object.material.opacity = 0.08;
        }
        return;
    }
    document.body.style.cursor = "default";
    if (hoveredShelf !== null) { resetHighlights(); hoveredShelf = null; }
}

function resetHighlights() { shelfMeshes.forEach(function(m) { m.material.opacity = 0; }); }

var modalOverlay = document.getElementById("modalOverlay");
var modalClose = document.getElementById("modalClose");

function openModal(sid) {
    var d = SHELVES[sid]; if (!d) return;
    document.getElementById("modalTitle").textContent = d.name + " — Deteccion AI";
    document.getElementById("modalDetCount").textContent = d.det;
    document.getElementById("modalConf").textContent = d.conf + "%";
    document.getElementById("modalTime").textContent = d.time;
    document.getElementById("modalModel").textContent = "YOLO11x+RT-DETR+RF-DETR";
    document.getElementById("modalRes").textContent = d.res;
    document.getElementById("modalImageDetected").src = d.imgDet;
    document.getElementById("modalImageOriginal").src = d.imgOrig;

    document.getElementById("tabDetected").classList.add("active");
    document.getElementById("tabOriginal").classList.remove("active");
    document.getElementById("modalImageDetected").classList.add("active");
    document.getElementById("modalImageOriginal").classList.remove("active");

    var pl = document.getElementById("productList"); pl.innerHTML = "";
    var colors = ["#4f7fff", "#34d399", "#a78bfa", "#fb923c", "#60a5fa", "#f87171", "#22d3ee", "#fbbf24"];
    d.products.forEach(function(p, i) {
        var conf = (85 + Math.random() * 14).toFixed(1);
        var invItem = inventory.find(function(it) { return it.name === p && it.shelfId === sid; });
        var qtyStr = invItem ? " (" + invItem.qty + " uds)" : "";
        pl.innerHTML += '<div class="product-item"><span class="product-dot" style="background:' + colors[i % 8] + '"></span><span class="product-name">' + p + qtyStr + '</span><span class="product-conf">' + conf + '%</span></div>';
    });

    modalOverlay.classList.add("active");
    controls.enabled = false;
}

function closeModal() { modalOverlay.classList.remove("active"); controls.enabled = true; }
modalClose.addEventListener("click", closeModal);
modalOverlay.addEventListener("click", function(e) { if (e.target === modalOverlay) closeModal(); });

document.getElementById("tabDetected").addEventListener("click", function() {
    document.getElementById("tabDetected").classList.add("active");
    document.getElementById("tabOriginal").classList.remove("active");
    document.getElementById("modalImageDetected").classList.add("active");
    document.getElementById("modalImageOriginal").classList.remove("active");
});
document.getElementById("tabOriginal").addEventListener("click", function() {
    document.getElementById("tabOriginal").classList.add("active");
    document.getElementById("tabDetected").classList.remove("active");
    document.getElementById("modalImageOriginal").classList.add("active");
    document.getElementById("modalImageDetected").classList.remove("active");
});

function closePanels(except) {
    var panels = ["dashboard", "inventoryPanel", "rpiPanel", "sidebar"];
    panels.forEach(function(p) { if (p !== except) document.getElementById(p).classList.remove("open"); });
}

document.getElementById("btnToggleInfo").addEventListener("click", function() {
    closePanels("sidebar");
    document.getElementById("sidebar").classList.toggle("open");
});
document.getElementById("sidebarClose").addEventListener("click", function() {
    document.getElementById("sidebar").classList.remove("open");
});
document.getElementById("btnToggleDashboard").addEventListener("click", function() {
    closePanels("dashboard");
    document.getElementById("dashboard").classList.toggle("open");
});
document.getElementById("dashClose").addEventListener("click", function() {
    document.getElementById("dashboard").classList.remove("open");
});
document.getElementById("btnToggleInventory").addEventListener("click", function() {
    closePanels("inventoryPanel");
    document.getElementById("inventoryPanel").classList.toggle("open");
    updateInventoryUI();
});
document.getElementById("inventoryClose").addEventListener("click", function() {
    document.getElementById("inventoryPanel").classList.remove("open");
});
document.getElementById("btnToggleRpi").addEventListener("click", function() {
    closePanels("rpiPanel");
    document.getElementById("rpiPanel").classList.toggle("open");
});
document.getElementById("rpiClose").addEventListener("click", function() {
    document.getElementById("rpiPanel").classList.remove("open");
});

document.getElementById("btnRunScan").addEventListener("click", startScan);
document.getElementById("scanClose").addEventListener("click", function() {
    document.getElementById("scanOverlay").classList.remove("active");
});

function startScan() {
    var ov = document.getElementById("scanOverlay");
    ov.classList.add("active");
    document.getElementById("scanResults").style.display = "none";
    var bar = document.getElementById("scanBarFill");
    var pct = document.getElementById("scanPercent");
    bar.style.width = "0%"; pct.textContent = "0%";

    for (var i = 0; i < 4; i++) {
        var el = document.getElementById("scanCam" + i);
        el.className = "scan-cam";
        el.innerHTML = '<span class="sc-dot"></span> CAM-0' + (i + 1) + ': Esperando...';
    }

    var progress = 0, camIdx = 0;
    var camNames = ["CAM-01: Pasillo 1", "CAM-02: Pasillo 2", "CAM-03: Pasillo 3", "CAM-04: Perimetral"];
    var camDets = [42, 38, 56, 31];

    var iv = setInterval(function() {
        progress += Math.random() * 4 + 2;
        var newCam = Math.floor(progress / 25);
        if (newCam > camIdx && camIdx < 4) {
            var prev = document.getElementById("scanCam" + camIdx);
            prev.className = "scan-cam done";
            prev.innerHTML = '<span class="sc-dot"></span> ' + camNames[camIdx] + ': \u2713 ' + camDets[camIdx] + ' detectados';
            camIdx = newCam;
        }
        if (camIdx < 4) {
            var cur = document.getElementById("scanCam" + camIdx);
            cur.className = "scan-cam scanning";
            cur.innerHTML = '<span class="sc-dot"></span> ' + camNames[camIdx] + ': Escaneando...';
        }

        if (progress >= 100) {
            progress = 100; clearInterval(iv);
            if (camIdx <= 3) {
                var last = document.getElementById("scanCam" + Math.min(camIdx, 3));
                last.className = "scan-cam done";
                last.innerHTML = '<span class="sc-dot"></span> ' + camNames[Math.min(camIdx, 3)] + ': \u2713 ' + camDets[Math.min(camIdx, 3)] + ' detectados';
            }
            setTimeout(function() {
                var total = camDets.reduce(function(a, b) { return a + b; }, 0);
                document.getElementById("srTotal").textContent = total;
                document.getElementById("srSkus").textContent = 43;
                document.getElementById("srOcc").textContent = "87%";
                document.getElementById("srTime").textContent = "3.2s";
                document.getElementById("scanResults").style.display = "block";

                document.getElementById("kpiTotal").textContent = total;
                document.getElementById("kpiSkus").textContent = 43;
                document.getElementById("kpiOcc").textContent = "87%";

                simulateSales();
                updateInventoryUI();
                addRpiLog("[SCAN] Escaneo completo: " + total + " productos detectados en 3.2s");
            }, 400);
        }
        bar.style.width = Math.min(progress, 100) + "%";
        pct.textContent = Math.floor(Math.min(progress, 100)) + "%";
    }, 80);
}

document.getElementById("btnResetCamera").addEventListener("click", function() {
    animateIntroCamera();
    controls.target.set(0, 1, -1);
});

document.addEventListener("keydown", function(e) {
    if (e.key === "Escape") {
        if (modalOverlay.classList.contains("active")) closeModal();
        else if (document.getElementById("sidebar").classList.contains("open")) document.getElementById("sidebar").classList.remove("open");
        else if (document.getElementById("dashboard").classList.contains("open")) document.getElementById("dashboard").classList.remove("open");
        else if (document.getElementById("inventoryPanel").classList.contains("open")) document.getElementById("inventoryPanel").classList.remove("open");
        else if (document.getElementById("rpiPanel").classList.contains("open")) document.getElementById("rpiPanel").classList.remove("open");
        else if (document.getElementById("scanOverlay").classList.contains("active")) document.getElementById("scanOverlay").classList.remove("active");
    }
});

function updateLabels() {
    SHELVES.forEach(function(d, i) {
        var el = labelEls[i]; if (!el) return;
        var p = new THREE.Vector3(d.pos.x, d.pos.y + 1.6, d.pos.z);
        p.project(camera);
        var x = (p.x * 0.5 + 0.5) * innerWidth, y = (-p.y * 0.5 + 0.5) * innerHeight;
        if (p.z < 1 && x > -100 && x < innerWidth + 100 && y > -50 && y < innerHeight + 100) {
            el.style.display = "flex"; el.style.left = x + "px"; el.style.top = y + "px";
            el.style.transform = "translate(-50%,-100%)";
        } else { el.style.display = "none"; }
    });
    CAMERAS_DATA.forEach(function(cd, i) {
        var el = camLabelEls[i]; if (!el) return;
        var p = new THREE.Vector3(cd.pos.x, cd.pos.y + 0.3, cd.pos.z);
        p.project(camera);
        var x = (p.x * 0.5 + 0.5) * innerWidth, y = (-p.y * 0.5 + 0.5) * innerHeight;
        if (p.z < 1 && x > -50 && x < innerWidth + 50 && y > -50 && y < innerHeight + 50) {
            el.style.display = "block"; el.style.left = x + "px"; el.style.top = y + "px";
            el.style.transform = "translate(-50%,-100%)";
        } else { el.style.display = "none"; }
    });
}

function animate() {
    requestAnimationFrame(animate);
    time += 0.01;
    controls.update();

    camMeshGroups.forEach(function(c, i) {
        if (c.led) c.led.material.color.setHex(Math.sin(time * 3 + i) > 0 ? 0xf87171 : 0x441111);
        if (c.beam) c.beam.opacity = 0.02 + Math.sin(time * 1.5 + i) * 0.008;
    });

    if (isLoaded) updateLabels();
    renderer.render(scene, camera);
}

function onResize() {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
}

init();
})();
