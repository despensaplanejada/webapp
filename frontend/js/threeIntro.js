/**
 * Three.js Shopping Cart & Falling Products Intro Animation
 * Despensa Planejada Santos
 */

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';

let scene, camera, renderer, animationFrameId;
let cartGroup, products = [];
let isExiting = false;
let startTime = null;

const INTRO_DURATION_MS = 4200; // Tempo total antes da transição automática

export function initThreeIntro() {
  const container = document.getElementById('threeCanvasContainer');
  const overlay = document.getElementById('threeIntroOverlay');
  const btnSkip = document.getElementById('btnSkipIntro');
  const btnReplay = document.getElementById('btnReplayIntro');

  if (!container || !overlay) return;

  // Se já tiver visto na sessão atual e não for acionado manualmente, pode pular
  const alreadySeen = sessionStorage.getItem('despensa_intro_seen');
  if (alreadySeen === 'true') {
    overlay.classList.add('fade-out');
    overlay.style.display = 'none';
    if (btnReplay) btnReplay.classList.remove('hidden');
    return;
  }

  setupScene(container);
  buildShoppingCart();
  spawnProducts();

  window.addEventListener('resize', onWindowResize);

  if (btnSkip) {
    btnSkip.addEventListener('click', () => finishIntro());
  }

  if (btnReplay) {
    btnReplay.addEventListener('click', () => {
      sessionStorage.removeItem('despensa_intro_seen');
      overlay.style.display = 'flex';
      // Forçar reflow para ativar transição CSS
      void overlay.offsetWidth;
      overlay.classList.remove('fade-out');
      initThreeIntro();
    });
  }

  startTime = performance.now();
  animate();
}

function setupScene(container) {
  // Limpar container anterior caso reexecutado
  container.innerHTML = '';
  products = [];
  isExiting = false;

  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x0a0f1d, 0.04);

  const aspect = window.innerWidth / window.innerHeight;
  camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 100);
  camera.position.set(0, 3.8, 7.5);
  camera.lookAt(0, 1.2, 0);

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;

  container.appendChild(renderer.domElement);

  // Iluminação de estúdio elegante
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
  scene.add(ambientLight);

  const mainLight = new THREE.DirectionalLight(0x34d399, 2.2); // Verde esmeralda da marca
  mainLight.position.set(5, 8, 5);
  mainLight.castShadow = true;
  mainLight.shadow.mapSize.width = 1024;
  mainLight.shadow.mapSize.height = 1024;
  scene.add(mainLight);

  const rimLight = new THREE.DirectionalLight(0x38bdf8, 1.8); // Azul ciano de contraste
  rimLight.position.set(-6, 4, -4);
  scene.add(rimLight);

  const fillLight = new THREE.PointLight(0xf59e0b, 1.2, 12); // Ponto quente âmbar
  fillLight.position.set(0, 4, 2);
  scene.add(fillLight);

  // Chão com reflexo suave e sombras
  const floorGeo = new THREE.PlaneGeometry(30, 30);
  const floorMat = new THREE.MeshStandardMaterial({
    color: 0x070b14,
    roughness: 0.6,
    metalness: 0.2
  });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = 0;
  floor.receiveShadow = true;
  scene.add(floor);

  // Grade sutil estilizada no chão
  const gridHelper = new THREE.GridHelper(20, 20, 0x10b981, 0x1e293b);
  gridHelper.position.y = 0.01;
  scene.add(gridHelper);
}

function buildShoppingCart() {
  cartGroup = new THREE.Group();

  const chromeMat = new THREE.MeshStandardMaterial({
    color: 0xcccccc,
    metalness: 0.9,
    roughness: 0.2
  });

  const greenMat = new THREE.MeshStandardMaterial({
    color: 0x059669, // Cor verde da marca
    metalness: 0.4,
    roughness: 0.4
  });

  const darkMat = new THREE.MeshStandardMaterial({
    color: 0x1e293b,
    roughness: 0.8
  });

  // Cesto principal (aramado com transparência elegante)
  const basketWidth = 2.4;
  const basketHeight = 1.3;
  const basketDepth = 1.8;

  const wireframeMat = new THREE.MeshStandardMaterial({
    color: 0x10b981,
    metalness: 0.7,
    roughness: 0.2,
    wireframe: true
  });
  const basketGeo = new THREE.BoxGeometry(basketWidth, basketHeight, basketDepth, 6, 4, 5);
  const basket = new THREE.Mesh(basketGeo, wireframeMat);
  basket.position.set(0, 1.4, 0);
  basket.castShadow = true;
  cartGroup.add(basket);

  // Borda superior reforçada do cesto
  const rimGeo = new THREE.BoxGeometry(basketWidth + 0.1, 0.08, basketDepth + 0.1);
  const rim = new THREE.Mesh(rimGeo, greenMat);
  rim.position.set(0, 1.4 + basketHeight / 2, 0);
  cartGroup.add(rim);

  // Barra/Pegador do carrinho (Handlebar)
  const handleGeo = new THREE.CylinderGeometry(0.05, 0.05, basketDepth, 16);
  const handle = new THREE.Mesh(handleGeo, greenMat);
  handle.rotation.x = Math.PI / 2;
  handle.position.set(-basketWidth / 2 - 0.4, 2.05, 0);
  cartGroup.add(handle);

  // Braços de suporte do puxador
  const supportGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.9, 16);
  const supportLeft = new THREE.Mesh(supportGeo, chromeMat);
  supportLeft.rotation.z = Math.PI / 5;
  supportLeft.position.set(-basketWidth / 2 - 0.2, 1.7, -basketDepth / 2 + 0.1);
  cartGroup.add(supportLeft);

  const supportRight = supportLeft.clone();
  supportRight.position.z = basketDepth / 2 - 0.1;
  cartGroup.add(supportRight);

  // Chassi de base metálica
  const chassisGeo = new THREE.BoxGeometry(basketWidth * 0.9, 0.08, basketDepth * 0.8);
  const chassis = new THREE.Mesh(chassisGeo, chromeMat);
  chassis.position.set(0, 0.45, 0);
  chassis.castShadow = true;
  cartGroup.add(chassis);

  // Rodinhas quádruplas
  const wheelRadius = 0.22;
  const wheelGeo = new THREE.CylinderGeometry(wheelRadius, wheelRadius, 0.1, 16);
  wheelGeo.rotateZ(Math.PI / 2);

  const wheelPositions = [
    [-basketWidth * 0.35, wheelRadius, -basketDepth * 0.35],
    [basketWidth * 0.35, wheelRadius, -basketDepth * 0.35],
    [-basketWidth * 0.35, wheelRadius, basketDepth * 0.35],
    [basketWidth * 0.35, wheelRadius, basketDepth * 0.35]
  ];

  wheelPositions.forEach(([x, y, z]) => {
    const wheel = new THREE.Mesh(wheelGeo, darkMat);
    wheel.position.set(x, y, z);
    wheel.castShadow = true;
    cartGroup.add(wheel);

    // Calota metálica
    const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.12, 12), chromeMat);
    hub.rotation.z = Math.PI / 2;
    hub.position.set(x, y, z);
    cartGroup.add(hub);
  });

  // Posição inicial fora da tela (para deslizar com impacto)
  cartGroup.position.set(-4.5, 0, 0);
  cartGroup.rotation.y = Math.PI / 10;
  scene.add(cartGroup);
}

function spawnProducts() {
  // Modelos coloridos representando compras: Pacotes, Frutas, Garrafas, Latas
  const productConfigs = [
    { type: 'box', color: 0xef4444, size: [0.35, 0.5, 0.25], name: 'Cereal / Caixa' },
    { type: 'box', color: 0x3b82f6, size: [0.3, 0.45, 0.3], name: 'Sabão em Pó' },
    { type: 'bottle', color: 0x10b981, size: [0.12, 0.55], name: 'Azeite / Suco' },
    { type: 'can', color: 0xf59e0b, size: [0.18, 0.32], name: 'Molho / Lata' },
    { type: 'sphere', color: 0x84cc16, size: [0.2], name: 'Maçã / Fruta' },
    { type: 'box', color: 0xa855f7, size: [0.4, 0.25, 0.35], name: 'Biscoitos' },
    { type: 'can', color: 0xec4899, size: [0.16, 0.35], name: 'Bebida Energética' },
    { type: 'sphere', color: 0xf97316, size: [0.22], name: 'Laranja / Fruta' },
    { type: 'box', color: 0x14b8a6, size: [0.35, 0.4, 0.25], name: 'Arroz / Massa' },
    { type: 'bottle', color: 0x6366f1, size: [0.13, 0.5], name: 'Leite UHT' }
  ];

  productConfigs.forEach((cfg, idx) => {
    let mesh;
    const mat = new THREE.MeshStandardMaterial({
      color: cfg.color,
      roughness: 0.3,
      metalness: 0.2
    });

    if (cfg.type === 'box') {
      mesh = new THREE.Mesh(new THREE.BoxGeometry(...cfg.size), mat);
    } else if (cfg.type === 'bottle') {
      const g = new THREE.CylinderGeometry(cfg.size[0] * 0.7, cfg.size[0], cfg.size[1], 16);
      mesh = new THREE.Mesh(g, mat);
    } else if (cfg.type === 'can') {
      mesh = new THREE.Mesh(new THREE.CylinderGeometry(cfg.size[0], cfg.size[0], cfg.size[1], 16), mat);
    } else {
      mesh = new THREE.Mesh(new THREE.SphereGeometry(cfg.size[0], 16, 16), mat);
    }

    mesh.castShadow = true;
    mesh.receiveShadow = true;

    // Posições no fundo do cesto (destino do pulo)
    const targetX = (Math.random() - 0.5) * 1.6;
    const targetZ = (Math.random() - 0.5) * 1.2;
    const targetY = 1.0 + Math.random() * 0.5;

    // Posição inicial no alto acima da tela
    mesh.position.set(targetX, 6 + Math.random() * 4, targetZ);
    mesh.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, Math.random() * Math.PI);

    products.push({
      mesh,
      targetY,
      targetX,
      targetZ,
      velocityY: -(0.08 + Math.random() * 0.05),
      rotSpeed: {
        x: (Math.random() - 0.5) * 0.06,
        y: (Math.random() - 0.5) * 0.06,
        z: (Math.random() - 0.5) * 0.06
      },
      delay: 700 + idx * 180, // Efeito cascata: caem um após o outro
      inBasket: false,
      bounces: 0
    });

    scene.add(mesh);
  });
}

function animate(currentTime = 0) {
  animationFrameId = requestAnimationFrame(animate);

  const elapsed = currentTime - startTime;

  // 1. Entrada suave do carrinho de supermercado
  if (cartGroup) {
    if (cartGroup.position.x < 0) {
      cartGroup.position.x += (0 - cartGroup.position.x) * 0.06;
      cartGroup.rotation.y += (0.1 - cartGroup.rotation.y) * 0.06;
    } else {
      // Leve balanço orbital idle
      cartGroup.rotation.y = 0.1 + Math.sin(elapsed * 0.0015) * 0.05;
      cartGroup.position.y = Math.sin(elapsed * 0.003) * 0.04;
    }
  }

  // 2. Queda e física elástica dos produtos
  products.forEach(p => {
    if (elapsed > p.delay) {
      if (!p.inBasket) {
        p.mesh.position.y += p.velocityY;
        p.velocityY -= 0.007; // Gravidade

        p.mesh.rotation.x += p.rotSpeed.x;
        p.mesh.rotation.y += p.rotSpeed.y;
        p.mesh.rotation.z += p.rotSpeed.z;

        // Bate no fundo do carrinho e quica
        if (p.mesh.position.y <= p.targetY) {
          p.mesh.position.y = p.targetY;
          p.velocityY = -p.velocityY * 0.42; // Coeficiente de restituição
          p.bounces++;
          if (p.bounces > 2) {
            p.inBasket = true;
          }
        }
      } else {
        // Segue o balanço do carrinho
        if (cartGroup) {
          p.mesh.position.x = p.targetX + cartGroup.position.x;
        }
      }
    }
  });

  // 3. Zoom de transição após o tempo total
  if (elapsed > INTRO_DURATION_MS && !isExiting) {
    finishIntro();
  }

  // Efeito de aproximação de câmera ao encerrar
  if (isExiting) {
    camera.position.z -= 0.08;
    camera.position.y -= 0.02;
  }

  renderer.render(scene, camera);
}

function finishIntro() {
  if (isExiting) return;
  isExiting = true;

  const overlay = document.getElementById('threeIntroOverlay');
  const btnReplay = document.getElementById('btnReplayIntro');

  sessionStorage.setItem('despensa_intro_seen', 'true');

  if (overlay) {
    overlay.classList.add('fade-out');
    setTimeout(() => {
      overlay.style.display = 'none';
      if (btnReplay) btnReplay.classList.remove('hidden');
      cleanupThree();
    }, 850);
  }
}

function cleanupThree() {
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
  }
  window.removeEventListener('resize', onWindowResize);
}

function onWindowResize() {
  if (!camera || !renderer) return;
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}
