document.addEventListener('DOMContentLoaded', () => {
  const sections = Array.from(document.querySelectorAll('section'));
  const btnScroll = document.getElementById('btn-scroll');
  const progressTrack = document.getElementById('progress-track');
  const total = sections.length;
  let currentSection = 0;
  let prevSection = -1;
  let mascotTimeout = null;
  let hopInterval = null; // To control the hopping ticks

  // Mascot Elements
  const mascotContainers = document.getElementById('bison-mascot');
  const mascotSpeech = document.getElementById('bison-speech');

  // Build progress dots
  sections.forEach((_, i) => {
    const d = document.createElement('div');
    d.className = 'progress-dot' + (i === 0 ? ' active' : '');
    d.addEventListener('click', () => sections[i].scrollIntoView({ behavior: 'smooth' }));
    progressTrack.appendChild(d);
  });

  // Scroll button
  btnScroll.addEventListener('click', () => {
    if (currentSection < total - 1) {
      sections[currentSection + 1].scrollIntoView({ behavior: 'smooth' });
    }
  });

  // ===== INTERSECTION OBSERVER: Scroll animations =====
  const animObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) entry.target.classList.add('visible');
    });
  }, { threshold: 0.15 });

  document.querySelectorAll('.card, .vs-container, .stat, .pipe-step, .cluster-row, .inline-img')
    .forEach(el => animObserver.observe(el));

  // ===== SECTION OBSERVER: Track active section =====
  const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const idx = sections.indexOf(entry.target);
        if (idx >= 0 && idx !== currentSection) {
          prevSection = currentSection;
          currentSection = idx;
          updateProgress(idx);
          animateFoodItems(idx);
          triggerFoodAnimations(idx);
          btnScroll.classList.toggle('at-end', idx === total - 1);
          updateMascot(idx);
        }
      }
    });
  }, { threshold: 0.5 });

  sections.forEach(s => sectionObserver.observe(s));

  function updateProgress(idx) {
    const dots = progressTrack.querySelectorAll('.progress-dot');
    dots.forEach((d, i) => d.classList.toggle('active', i === idx));
  }

  // ===== FOOD ITEM POSITION MAP =====
  const foodEls = Array.from(document.querySelectorAll('.food-item'));
  const posMap = {};

  foodEls.forEach(item => {
    const id = item.id;
    const positions = {};
    for (let i = 0; i < total; i++) {
      const attr = item.getAttribute('data-pos-' + i);
      if (attr) {
        const props = {};
        attr.split(';').forEach(pair => {
          const [k, v] = pair.split(':').map(s => s.trim());
          if (k && v) props[k] = v;
        });
        positions[i] = props;
      }
    }
    posMap[id] = positions;
  });

  function animateFoodItems(sectionIdx) {
    foodEls.forEach(item => {
      const positions = posMap[item.id];
      if (!positions) return;

      // Find closest defined position
      let targetPos = null;
      for (let i = sectionIdx; i >= 0; i--) {
        if (positions[i]) { targetPos = positions[i]; break; }
      }
      if (!targetPos) return;

      // Apply positions
      item.style.top = targetPos.top || '';
      item.style.bottom = targetPos.bottom || '';
      item.style.left = targetPos.left || '';
      item.style.right = targetPos.right || '';

      if (targetPos.top) item.style.bottom = 'auto';
      if (targetPos.bottom) item.style.top = 'auto';
      if (targetPos.left) item.style.right = 'auto';
      if (targetPos.right) item.style.left = 'auto';

      if (targetPos.opacity) item.style.opacity = targetPos.opacity;
      if (targetPos.width) item.style.width = targetPos.width;
    });
  }

  // ===== FOOD ANIMATIONS PER SECTION =====
  function triggerFoodAnimations(sectionIdx) {
    const apple = document.getElementById('food-apple');
    const wafer = document.getElementById('food-wafer');
    const pudding = document.getElementById('food-pudding');
    const soda = document.getElementById('food-soda');
    const gum = document.getElementById('food-gum');
    const noodles = document.getElementById('food-noodles');

    // Remove previous animation classes
    foodEls.forEach(el => {
      el.classList.remove('wobble', 'bounce', 'spin', 'bitten');
    });

    // Force reflow
    void document.body.offsetWidth;

    // Apple: gets bitten after section 1
    if (sectionIdx >= 2 && apple) {
      apple.classList.add('bitten');
    }

    // Add wobble to different items on different sections
    switch(sectionIdx) {
      case 1:
        if (apple) apple.classList.add('wobble');
        if (wafer) wafer.classList.add('bounce');
        break;
      case 2:
        if (apple) { apple.classList.add('bitten'); apple.classList.add('wobble'); }
        if (gum) gum.classList.add('bounce');
        break;
      case 3:
        if (pudding) pudding.classList.add('wobble');
        if (noodles) noodles.classList.add('spin');
        break;
      case 4:
        if (soda) soda.classList.add('wobble');
        if (wafer) wafer.classList.add('bounce');
        break;
      case 5:
        if (gum) gum.classList.add('spin');
        if (apple) { apple.classList.add('bitten'); apple.classList.add('wobble'); }
        break;
      case 6:
        if (noodles) noodles.classList.add('wobble');
        if (pudding) pudding.classList.add('bounce');
        break;
      case 7:
        if (soda) soda.classList.add('spin');
        if (wafer) wafer.classList.add('wobble');
        break;
      case 8:
        if (soda) soda.classList.add('wobble');
        if (gum) gum.classList.add('bounce');
        break;
      case 9:
        // Grand finale: all bounce
        foodEls.forEach(el => el.classList.add('bounce'));
        break;
    }
  }

  // ===== BISON MASCOT LOGIC =====
  function parsePercent(str) {
    return parseFloat(str.replace('%', ''));
  }

  // Animación base para que respire suavemente cuando está quieto
  function startBreathing() {
    const svg = mascotContainers.querySelector('.bison-svg');
    if(svg) {
      svg.style.transform = '';
      svg.classList.remove('hopping-fast');
    }
  }

  function updateMascot(sectionIdx) {
    if (!mascotContainers || !mascotSpeech) return;
    
    if (mascotTimeout) clearTimeout(mascotTimeout);
    if (hopInterval) cancelAnimationFrame(hopInterval); // Update to cancel animation frame

    // Ocultar burbuja al empezar a moverse
    mascotSpeech.classList.remove('show');
    
    // Posiciones dinámicas (esquinas/huecos según diseño actual)
    const positions = [
      { left: '8%',  top: '70%' }, // Sec 0 - Cover
      { left: '78%', top: '15%' }, // Sec 1 - Overview
      { left: '8%',  top: '35%' }, // Sec 2 - YOLO
      { left: '78%', top: '75%' }, // Sec 3 - Godmode
      { left: '10%', top: '75%' }, // Sec 4 - Ensemble
      { left: '78%', top: '25%' }, // Sec 5 - Bug fix
      { left: '80%', top: '70%' }, // Sec 6 - ML
      { left: '8%',  top: '15%' }, // Sec 7 - 3D 
      { left: '78%', top: '15%' }, // Sec 8 - Metrics
      { left: '10%', top: '65%' }  // Sec 9 - Footer
    ];
    
    const targetPos = positions[sectionIdx] || positions[0];
    const svg = mascotContainers.querySelector('.bison-svg');

    // Obtener la posición física actual en PX (para moverlo fluidamente sin lidiar con los %)
    // Usamos el bounding box que nos da siempre el viewport exacto.
    const rect = mascotContainers.getBoundingClientRect();
    let currentX = rect.left;
    let currentY = rect.top;

    // Convertir el Target % a píxeles exactos (basado en el ancho/alto de la ventana disponible)
    const viewW = window.innerWidth;
    const viewH = window.innerHeight;
    
    // Calcular el destino en píxeles. Restamos padding para que encaje como lo haría en CSS relative/percent
    const targetLeftPct = parsePercent(targetPos.left) / 100;
    const targetTopPct = parsePercent(targetPos.top) / 100;
    
    // Suponiendo que nuestro div mide 140px por 140px
    const mascotW = 140; 
    const mascotH = 140;
    
    const targetX = targetLeftPct * window.innerWidth;
    const targetY = targetTopPct * window.innerHeight;

    // A partir de este momento vamos a moverlo manualmente en PX fijándolo en 'left' y 'top' px.
    // Desactivar animaciones CSS de mudanza porque tomamos control en JS
    mascotContainers.style.transition = 'none';

    // === Sistema de físicas para saltitos ("Bouncing") fluido ===
    const dx = targetX - currentX;
    const dy = targetY - currentY;
    const totalDist = Math.sqrt(dx*dx + dy*dy);

    if (totalDist < 5) {
      // Ya está en el sitio; no hacer nada y solo mostrar el texto
      showSpeech(sectionIdx);
      return;
    }

    // Cuantos saltos debe dar según la distancia
    let numJumps = Math.max(2, Math.floor(totalDist / 120)); 
    if (numJumps > 6) numJumps = 6;
    
    // Variables de la animación visual
    let startTime = null;
    let bounceDuration = 400; // milisegundos por cada saltito
    const totalDuration = numJumps * bounceDuration;
    const startX = currentX;
    const startY = currentY;

    // Le ponemos una clase al SVG que cambia su respiración a "achaparrarse" rápido por los saltos
    if(svg) svg.classList.add('hopping-fast');

    function animateHop(timestamp) {
      if (!startTime) startTime = timestamp;
      const progressTime = timestamp - startTime;
      
      let t = progressTime / totalDuration; // Va a ir de 0.0 a 1.0 (inicio a fin del viaje entero)
      if (t >= 1) t = 1;

      // 1. Calculamos la posición lineal "deslizante" a través de la curva T
      // Para suavizarlo usamos una curva easeInOutSine
      const easeT = -(Math.cos(Math.PI * t) - 1) / 2;
      const interpX = startX + (dx * easeT);
      const interpY = startY + (dy * easeT);

      // 2. Le agregamos los brincos. Usamos Math.abs(Math.sin) mapeado a la cantidad de saltos.
      // Así subirá y bajará 'numJumps' veces en su viaje desde 0 a 1.
      const jumpWave = Math.sin(t * numJumps * Math.PI); 
      
      // La altura máxima de cada salto en aire
      const hopHeight = 80; 
      const currentHopY = Math.abs(jumpWave) * hopHeight;

      // 3. Animación de Squish (Achaparrarse). 
      // Cuando la onda se acerca a 0 (aterrizaje o inicio), "aplastamos" al bisonte en el SVG
      // Cuando la onda se acerca a 1 (cresta del salto superior), "estiramos" un poquito
      let scaleY = 1.0;
      let scaleX = 1.0;
      let rotationX = 0; // Giro segun hacia donde salta
      
      if (Math.abs(jumpWave) < 0.2) {
        // Está contactando el suelo "squish!"
        scaleY = 0.85; 
        scaleX = 1.15;
      } else {
        // En el aire
        scaleY = 1.05;
        scaleX = 0.95;
      }

      // Si viaja hacia la izquierda, inclinar su cuerpo a la izquierda, si derecha a la derecha
      const isGoingRight = dx > 0;
      const angle = isGoingRight ? 10 : -10;
      if (Math.abs(jumpWave) > 0.1) rotationX = angle * Math.abs(jumpWave); // Rotación máxima arriba

      // Aplicar posiciones fisicas absolutas (Pixeles)
      mascotContainers.style.left = interpX + 'px';
      mascotContainers.style.top = (interpY - currentHopY) + 'px';
      
      // Aplicar deformación al SVG de adentro para exagerar ternura
      if (svg) {
         svg.style.transform = `scale(${scaleX}, ${scaleY}) rotate(${rotationX}deg)`;
      }

      if (t < 1) {
        hopInterval = requestAnimationFrame(animateHop);
      } else {
        // Termino toda la animación
        startBreathing();
        
        // Regresamos al estado de alineamiento basado en % (para el responsiveness si redimensionan pantalla)
        mascotContainers.style.left = targetPos.left;
        mascotContainers.style.top = targetPos.top;
        
        // Volver a activar las transiciones CSS ligeras de hover por defecto
        setTimeout(() => {
          mascotContainers.style.transition = 'opacity 0.3s ease';
          showSpeech(sectionIdx);
        }, 50);
      }
    }

    hopInterval = requestAnimationFrame(animateHop);

    // Dialogo Mostrar helper
    function showSpeech(idx) {
        const dialogues = [
          "¡Hola! Soy Bisontito. ¡Preparate para ver magia!", 
          "¿Sabías que la Raspberry Pi 5 consume menos luz que un foco viejo?", 
          "¡YOLOv8x es mi raza de modelo favorita! Super rapido y exacto.", 
          "GodMode activado: ¡Nadie se esconde de nosotros!", 
          "Tres mentes piensan mejor que una. ¡Por eso somos un equipo!", 
          "¡Bug aplastado! Ahora ya no confundo el jabón con la sopa.", 
          "Clasificación, clustering... ¡Puro poder matemático!", 
          "¡Me encanta el 3D! Cuidado con el mundo digital 🤖", 
          "Las matemáticas nunca mienten. ¡Mira esa curva perfecta!", 
          "¡Gracias por ver nuestra presentación! - Equipo Bisontitos 🦬♥" 
        ];

        if (idx >= 0 && idx < dialogues.length) {
          mascotTimeout = setTimeout(() => {
            mascotSpeech.textContent = dialogues[idx];
            mascotSpeech.classList.add('show');
          }, 200); // Wait slightly to trigger speech
        }
    }

  }

  // ===== Keyboard navigation =====
  document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === ' ') {
      e.preventDefault();
      if (currentSection < total - 1) sections[currentSection + 1].scrollIntoView({ behavior: 'smooth' });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (currentSection > 0) sections[currentSection - 1].scrollIntoView({ behavior: 'smooth' });
    }
  });

  // ===== Fullscreen Toggle =====
  const btnFullscreen = document.getElementById('btn-fullscreen');
  if (btnFullscreen) {
    btnFullscreen.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(err => {
          console.log(`Error attempting to enable fullscreen: ${err.message}`);
        });
      } else {
        document.exitFullscreen();
      }
    });
  }

  // Init
  animateFoodItems(0);
});
