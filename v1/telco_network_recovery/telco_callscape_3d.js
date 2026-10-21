import * as THREE from './vendor/three.module.js';

document.body.classList.toggle('embedded', new URLSearchParams(location.search).has('embed'));

// Geolocated sample from data/cell_towers.csv; counts are from data/call_detail_records.csv.
const towerRows = [
  ['TWR-0005', 37.789659, -122.386949, 'DEGRADED', 'WEST', 94, 143],
  ['TWR-0010', 37.816078, -122.451989, 'DEGRADED', 'WEST', 18, 164],
  ['TWR-0015', 37.786973, -122.428582, 'DEGRADED', 'WEST', 60, 151],
  ['TWR-0020', 37.965878, -122.717131, 'ACTIVE', 'NORTH', 43, 36],
  ['TWR-0025', 37.917298, -122.333992, 'ACTIVE', 'NORTH', 65, 36],
  ['TWR-0030', 37.936083, -122.113125, 'MAINTENANCE', 'EAST', 35, 39],
  ['TWR-0032', 37.639302, -122.744463, 'MAINTENANCE', 'CENTRAL', 54, 37],
  ['TWR-0035', 37.595039, -122.764491, 'ACTIVE', 'EAST', 10, 27],
  ['TWR-0040', 37.892879, -122.314671, 'MAINTENANCE', 'WEST', 69, 31],
  ['TWR-0045', 37.621992, -122.275154, 'MAINTENANCE', 'SOUTH', 23, 40],
  ['TWR-0050', 37.719936, -122.229164, 'ACTIVE', 'EAST', 44, 34],
  ['TWR-0055', 37.636468, -122.411486, 'MAINTENANCE', 'SOUTH', 53, 41],
  ['TWR-0060', 37.526043, -122.038464, 'ACTIVE', 'NORTH', 93, 47],
  ['TWR-0065', 37.537998, -122.247508, 'ACTIVE', 'EAST', 41, 29],
  ['TWR-0067', 37.830761, -122.744835, 'ACTIVE', 'WEST', 53, 35],
  ['TWR-0070', 37.912867, -122.326020, 'ACTIVE', 'EAST', 41, 32],
  ['TWR-0075', 37.855921, -122.441460, 'ACTIVE', 'SOUTH', 21, 32],
  ['TWR-0080', 37.988304, -122.380291, 'ACTIVE', 'EAST', 22, 31],
  ['TWR-0085', 37.814723, -122.757113, 'ACTIVE', 'NORTH', 82, 37],
  ['TWR-0090', 37.725252, -122.324951, 'ACTIVE', 'EAST', 14, 36],
  ['TWR-0095', 37.799018, -122.088462, 'ACTIVE', 'NORTH', 51, 29],
  ['TWR-0100', 37.831292, -122.479638, 'MAINTENANCE', 'NORTH', 14, 37],
  ['TWR-0105', 37.506837, -122.473607, 'MAINTENANCE', 'NORTH', 24, 31],
  ['TWR-0110', 37.769290, -122.523901, 'MAINTENANCE', 'WEST', 79, 26],
  ['TWR-0114', 37.762976, -122.434458, 'MAINTENANCE', 'SOUTH', 28, 43],
  ['TWR-0115', 37.734745, -122.024637, 'MAINTENANCE', 'NORTH', 89, 32],
  ['TWR-0120', 37.715343, -122.604642, 'ACTIVE', 'SOUTH', 82, 40],
];

const stage = document.getElementById('stage');
const loadState = document.getElementById('load-state');
const focusId = document.getElementById('focus-id');
const focusDetail = document.getElementById('focus-detail');
const focusImpact = document.getElementById('focus-impact');
const linkCount = document.getElementById('link-count');
const clock = document.getElementById('clock');
const timelineFill = document.getElementById('timeline-fill');
const pauseButton = document.getElementById('pause');
const resetButton = document.getElementById('reset');
const trafficButton = document.getElementById('mode-traffic');
const statusButton = document.getElementById('mode-status');
const speedInput = document.getElementById('speed');
const speedValue = document.getElementById('speed-value');

const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const statusColors = {
  ACTIVE: new THREE.Color('#85caa3'),
  DEGRADED: new THREE.Color('#ff8269'),
  MAINTENANCE: new THREE.Color('#f3c679'),
};
const trafficLow = new THREE.Color('#55d8ce');
const trafficHigh = new THREE.Color('#f6b96f');
const heroIds = new Set(['TWR-0030', 'TWR-0067', 'TWR-0114']);
const tmpColor = new THREE.Color();
const up = new THREE.Vector3(0, 1, 0);
const unitBeam = new THREE.CylinderGeometry(1, 1, 1, 6);
const loopSeconds = 20;
let seed = 12041985;
let elapsed = 0;
let lastFrame = performance.now();
let paused = prefersReducedMotion.matches;
let mode = 'traffic';
let selectedTower = null;
let theta = -0.42;
let phi = 0.87;
let radius = 143;
let lastInteraction = 0;
let dragging = null;
let sceneActive = true;

function random() {
  seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
  return seed / 4294967296;
}

function terrainHeight(x, z) {
  const hill = 1.65 * Math.exp(-(((x + 28) / 28) ** 2 + ((z - 5) / 29) ** 2));
  return -1.0 + hill + 0.65 * Math.sin(x * 0.13 + z * 0.035)
    + 0.34 * Math.cos(z * 0.19 - x * 0.07)
    + 0.25 * Math.sin(x * 0.32 + z * 0.25);
}

function locationFor(lat, lon) {
  const x = (lon + 122.4) * 145;
  const z = (37.75 - lat) * 170;
  return new THREE.Vector3(x, terrainHeight(x, z), z);
}

const towers = towerRows.map(([id, lat, lon, status, region, capacity, calls]) => ({
  id, lat, lon, status, region, capacity, calls,
  position: locationFor(lat, lon),
  hero: heroIds.has(id),
}));
const towerById = new Map(towers.map(tower => [tower.id, tower]));

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
} catch (error) {
  loadState.textContent = 'The 3D scene needs WebGL in this browser.';
  throw error;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.7));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.65;
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color('#10232a');
scene.fog = new THREE.FogExp2('#10232a', 0.0038);
const camera = new THREE.PerspectiveCamera(43, 1, 0.1, 450);
const target = new THREE.Vector3(0, 0.2, 0);

scene.add(new THREE.HemisphereLight('#d5fff0', '#274548', 2.0));
const sun = new THREE.DirectionalLight('#ffe0b2', 2.0);
sun.position.set(-42, 85, 26);
scene.add(sun);
const tealFill = new THREE.DirectionalLight('#80eddf', 1.2);
tealFill.position.set(48, 35, -30);
scene.add(tealFill);

function addTerrain() {
  const geometry = new THREE.PlaneGeometry(146, 110, 96, 72);
  geometry.rotateX(-Math.PI / 2);
  const positions = geometry.attributes.position;
  const colors = [];
  const low = new THREE.Color('#1d3e3e');
  const high = new THREE.Color('#42685b');
  const ridge = new THREE.Color('#57776a');
  for (let i = 0; i < positions.count; i += 1) {
    const x = positions.getX(i);
    const z = positions.getZ(i);
    const height = terrainHeight(x, z);
    positions.setY(i, height);
    tmpColor.copy(low).lerp(high, THREE.MathUtils.clamp((height + 1.7) / 4.4, 0, 1));
    tmpColor.lerp(ridge, Math.max(0, height - 1.1) * 0.09);
    colors.push(tmpColor.r, tmpColor.g, tmpColor.b);
  }
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geometry.computeVertexNormals();
  scene.add(new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
    vertexColors: true, roughness: 0.94, metalness: 0.04, flatShading: true,
  })));

  const gridPositions = [];
  for (let x = -70; x <= 70; x += 10) {
    for (let z = -52; z < 52; z += 2) {
      gridPositions.push(x, terrainHeight(x, z) + 0.09, z);
      gridPositions.push(x, terrainHeight(x, z + 2) + 0.09, z + 2);
    }
  }
  for (let z = -50; z <= 50; z += 10) {
    for (let x = -72; x < 72; x += 2) {
      gridPositions.push(x, terrainHeight(x, z) + 0.09, z);
      gridPositions.push(x + 2, terrainHeight(x + 2, z) + 0.09, z);
    }
  }
  const gridGeometry = new THREE.BufferGeometry();
  gridGeometry.setAttribute('position', new THREE.Float32BufferAttribute(gridPositions, 3));
  scene.add(new THREE.LineSegments(gridGeometry, new THREE.LineBasicMaterial({
    color: '#91ccc3', transparent: true, opacity: 0.16, depthWrite: false,
  })));

  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(1200, 1200),
    new THREE.MeshStandardMaterial({ color: '#102b31', roughness: 1 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -3.5;
  scene.add(floor);
}

function addCityBlocks() {
  const centers = [
    [-25, -6], [-12, 12], [18, -12], [33, 11], [-40, 22], [4, 28],
  ];
  const count = 220;
  const geometry = new THREE.BoxGeometry(1, 1, 1);
  const material = new THREE.MeshStandardMaterial({ color: '#d5e9dd', roughness: 0.82, metalness: 0.22 });
  const blocks = new THREE.InstancedMesh(geometry, material, count);
  const dummy = new THREE.Object3D();
  const base = new THREE.Color('#28454a');
  const lit = new THREE.Color('#819484');
  for (let i = 0; i < count; i += 1) {
    const [cx, cz] = centers[i % centers.length];
    const x = cx + (random() - 0.5) * 34;
    const z = cz + (random() - 0.5) * 25;
    const height = 0.7 + random() ** 2 * 4.0;
    dummy.position.set(x, terrainHeight(x, z) + height / 2, z);
    dummy.scale.set(0.9 + random() * 2.3, height, 0.9 + random() * 2.3);
    dummy.rotation.y = random() * 0.22;
    dummy.updateMatrix();
    blocks.setMatrixAt(i, dummy.matrix);
    tmpColor.copy(base).lerp(lit, random() * 0.52);
    blocks.setColorAt(i, tmpColor);
  }
  blocks.instanceMatrix.needsUpdate = true;
  if (blocks.instanceColor) blocks.instanceColor.needsUpdate = true;
  scene.add(blocks);
}

function makeGlowTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const context = canvas.getContext('2d');
  const gradient = context.createRadialGradient(64, 64, 1, 64, 64, 64);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.1, 'rgba(255,255,255,.92)');
  gradient.addColorStop(0.3, 'rgba(255,255,255,.35)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');
  context.fillStyle = gradient;
  context.fillRect(0, 0, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}
const glowTexture = makeGlowTexture();

function beamBetween(group, from, to, radius, material) {
  const direction = new THREE.Vector3().subVectors(to, from);
  const beam = new THREE.Mesh(unitBeam, material);
  beam.position.copy(from).add(to).multiplyScalar(0.5);
  beam.quaternion.setFromUnitVectors(up, direction.clone().normalize());
  beam.scale.set(radius, direction.length(), radius);
  group.add(beam);
}

const hitMeshes = [];
function addTower(tower) {
  const mast = new THREE.Group();
  mast.position.copy(tower.position);
  const height = (tower.hero ? 11.2 : 7.3) + tower.capacity * 0.023;
  const base = tower.hero ? 1.12 : 0.82;
  const mastMaterial = new THREE.MeshStandardMaterial({
    color: '#9fbab5', metalness: 0.75, roughness: 0.32,
    emissive: '#216a68', emissiveIntensity: 0.2,
  });
  const braceMaterial = new THREE.MeshStandardMaterial({
    color: '#587e7b', metalness: 0.68, roughness: 0.4,
  });
  const foot = [
    new THREE.Vector3(-base, 0, -base), new THREE.Vector3(base, 0, -base),
    new THREE.Vector3(base, 0, base), new THREE.Vector3(-base, 0, base),
  ];
  const top = foot.map(point => point.clone().multiplyScalar(0.16).setY(height));
  for (let i = 0; i < 4; i += 1) beamBetween(mast, foot[i], top[i], tower.hero ? 0.11 : 0.085, mastMaterial);
  for (const fraction of [0.23, 0.48, 0.73]) {
    const level = foot.map((point, index) => point.clone().lerp(top[index], fraction));
    for (let i = 0; i < 4; i += 1) {
      beamBetween(mast, level[i], level[(i + 1) % 4], 0.052, braceMaterial);
    }
  }
  for (let i = 0; i < 4; i += 1) {
    const a = foot[i].clone().lerp(top[i], 0.26);
    const b = foot[(i + 1) % 4].clone().lerp(top[(i + 1) % 4], 0.51);
    beamBetween(mast, a, b, 0.041, braceMaterial);
  }
  beamBetween(mast, new THREE.Vector3(0, height - 0.3, 0), new THREE.Vector3(0, height + 2.3, 0), 0.083, mastMaterial);

  const beaconMaterial = new THREE.MeshStandardMaterial({
    color: '#59dbcd', emissive: '#59dbcd', emissiveIntensity: 2.8,
    roughness: 0.18, metalness: 0,
  });
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(tower.hero ? 0.47 : 0.33, 12, 8), beaconMaterial);
  beacon.position.y = height + 2.35;
  mast.add(beacon);
  const beaconGlow = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTexture, color: '#59dbcd', transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending, toneMapped: false,
  }));
  beaconGlow.position.y = height + 2.35;
  beaconGlow.scale.setScalar(tower.hero ? 6.8 : 4.5);
  mast.add(beaconGlow);

  const ringMaterial = new THREE.MeshBasicMaterial({
    color: '#59dbcd', transparent: true, opacity: 0.45,
    depthWrite: false, side: THREE.DoubleSide,
  });
  const ring = new THREE.Mesh(new THREE.RingGeometry(tower.hero ? 2.1 : 1.6, tower.hero ? 2.27 : 1.75, 48), ringMaterial);
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.09;
  mast.add(ring);

  const marker = new THREE.Mesh(
    new THREE.CircleGeometry(tower.hero ? 1.7 : 1.2, 32),
    new THREE.MeshBasicMaterial({ color: '#0e2a30', transparent: true, opacity: 0.76, side: THREE.DoubleSide }),
  );
  marker.rotation.x = -Math.PI / 2;
  marker.position.y = 0.025;
  mast.add(marker);

  const hit = new THREE.Mesh(
    new THREE.CylinderGeometry(2.3, 2.3, height + 4, 8),
    new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }),
  );
  hit.position.y = (height + 4) / 2;
  hit.userData.tower = tower;
  mast.add(hit);
  hitMeshes.push(hit);
  scene.add(mast);

  tower.mast = mast;
  tower.mastMaterial = mastMaterial;
  tower.beacon = beacon;
  tower.beaconGlow = beaconGlow;
  tower.ring = ring;
  tower.height = height + 2.35;
  tower.topPosition = tower.position.clone().add(new THREE.Vector3(0, tower.height, 0));
}

function towerColor(tower) {
  if (mode === 'status') return statusColors[tower.status];
  if (tower.id === 'TWR-0030') return statusColors.MAINTENANCE;
  const weight = THREE.MathUtils.clamp((tower.calls - 25) / 140, 0, 1);
  return tmpColor.copy(trafficLow).lerp(trafficHigh, weight);
}

function colorTowers() {
  for (const tower of towers) {
    const color = towerColor(tower);
    tower.beacon.material.color.copy(color);
    tower.beacon.material.emissive.copy(color);
    tower.beaconGlow.material.color.copy(color);
    tower.ring.material.color.copy(color);
    tower.mastMaterial.color.copy(new THREE.Color('#819d98')).lerp(color, mode === 'status' ? 0.48 : 0.2);
    tower.mastMaterial.emissive.copy(color);
    tower.mastMaterial.emissiveIntensity = tower === selectedTower ? 0.5 : 0.14;
  }
}

const flows = [];
function addFlows() {
  const keys = new Set();
  const pairs = [];
  function pair(a, b, featured = false) {
    const key = [a.id, b.id].sort().join(':');
    if (keys.has(key)) return;
    keys.add(key);
    pairs.push({ a, b, featured });
  }
  for (const tower of towers) {
    const nearest = towers
      .filter(other => other !== tower)
      .sort((a, b) => tower.position.distanceToSquared(a.position) - tower.position.distanceToSquared(b.position))
      .slice(0, 2);
    nearest.forEach(other => pair(tower, other));
  }
  pair(towerById.get('TWR-0067'), towerById.get('TWR-0114'), true);
  pair(towerById.get('TWR-0030'), towerById.get('TWR-0067'), true);
  pair(towerById.get('TWR-0010'), towerById.get('TWR-0067'), true);
  const flowColors = ['#5ce2d2', '#ff947a', '#f3cb83'];
  for (let i = 0; i < pairs.length; i += 1) {
    const { a, b, featured } = pairs[i];
    const start = a.topPosition;
    const end = b.topPosition;
    const midpoint = start.clone().add(end).multiplyScalar(0.5);
    midpoint.y += 5 + start.distanceTo(end) * 0.13;
    const curve = new THREE.QuadraticBezierCurve3(start, midpoint, end);
    const color = flowColors[i % flowColors.length];
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(curve.getPoints(48)),
      new THREE.LineBasicMaterial({
        color, transparent: true, opacity: featured ? 0.47 : 0.15,
        depthWrite: false,
      }),
    );
    scene.add(line);
    const pulses = [];
    const pulseCount = featured ? 3 : 2;
    for (let pulseIndex = 0; pulseIndex < pulseCount; pulseIndex += 1) {
      const tail = [];
      for (let j = 0; j < 3; j += 1) {
        const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
          map: glowTexture, color, transparent: true,
          opacity: j === 0 ? 0.95 : (j === 1 ? 0.46 : 0.2),
          depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false,
        }));
        sprite.scale.setScalar((featured ? 3.0 : 2.25) * (1 - j * 0.21));
        scene.add(sprite);
        tail.push(sprite);
      }
      pulses.push({ tail, phase: (pulseIndex / pulseCount + random() * 0.21) % 1 });
    }
    flows.push({ curve, line, pulses, rate: 0.23 + random() * 0.22 });
  }
  linkCount.textContent = String(flows.length);
}

function chooseTower(tower) {
  selectedTower = tower;
  focusId.textContent = tower.id;
  focusDetail.textContent = `${tower.region} / ${tower.status} / ${tower.calls} routed calls`;
  if (tower.id === 'TWR-0067') {
    focusImpact.textContent = 'Call-weighted impact: 1.47M';
  } else if (tower.id === 'TWR-0030') {
    focusImpact.textContent = 'Call-weighted impact: 76,180';
  } else {
    focusImpact.textContent = `Tower capacity: ${tower.capacity} Gbps`;
  }
  colorTowers();
}

function updateCamera() {
  camera.position.set(
    target.x + radius * Math.sin(phi) * Math.sin(theta),
    target.y + radius * Math.cos(phi),
    target.z + radius * Math.sin(phi) * Math.cos(theta),
  );
  camera.lookAt(target);
}

const labelAnchors = [
  ['tag-0067', 'TWR-0067'],
  ['tag-0030', 'TWR-0030'],
  ['tag-0114', 'TWR-0114'],
  ['geo-west', new THREE.Vector3(-63, 3, 24)],
  ['geo-east', new THREE.Vector3(62, 3, 24)],
  ['geo-north', new THREE.Vector3(-59, 3, -39)],
];
function updateLabels() {
  const blockers = ['.story', '.upper-tools', '.focus', '.side-footer', '.clock-row']
    .map(selector => document.querySelector(selector).getBoundingClientRect());
  for (const [id, anchor] of labelAnchors) {
    const label = document.getElementById(id);
    const position = typeof anchor === 'string' ? towerById.get(anchor).topPosition : anchor;
    const projected = position.clone().project(camera);
    const x = (projected.x * 0.5 + 0.5) * stage.clientWidth;
    const y = (-projected.y * 0.5 + 0.5) * stage.clientHeight;
    label.style.left = `${x}px`;
    label.style.top = `${y}px`;
    const labelWidth = label.classList.contains('tower-tag') ? 104 : 80;
    const box = { left: x + 8, right: x + labelWidth, top: y - 26, bottom: y + 6 };
    const blocked = blockers.some(rect => (
      box.left < rect.right && box.right > rect.left
      && box.top < rect.bottom && box.bottom > rect.top
    ));
    label.hidden = projected.z > 1 || x < 4 || x > stage.clientWidth - labelWidth
      || y < 6 || y > stage.clientHeight - 8 || blocked;
  }
}

function resize() {
  const width = stage.clientWidth;
  const height = stage.clientHeight;
  if (width < 1 || height < 1) return;
  camera.aspect = width / height;
  camera.fov = width < 600 ? 55 : 43;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
  updateCamera();
  updateLabels();
}

function updateFlows(time) {
  for (const flow of flows) {
    for (const pulse of flow.pulses) {
      const head = (time * flow.rate + pulse.phase) % 1;
      for (let j = 0; j < pulse.tail.length; j += 1) {
        const t = (head - j * 0.018 + 1) % 1;
        pulse.tail[j].position.copy(flow.curve.getPoint(t));
      }
    }
  }
}

function updateBeacons(time) {
  for (let i = 0; i < towers.length; i += 1) {
    const tower = towers[i];
    const pulse = 0.5 + 0.5 * Math.sin(time * 4.2 + i * 1.7);
    const selected = tower === selectedTower;
    tower.beaconGlow.material.opacity = (selected ? 0.9 : 0.53) + pulse * 0.1;
    tower.beaconGlow.scale.setScalar((tower.hero ? 6.8 : 4.5) * (0.9 + pulse * 0.24));
    tower.ring.scale.setScalar(0.94 + pulse * (selected ? 0.36 : 0.18));
    tower.ring.material.opacity = selected ? 0.66 : 0.22 + pulse * 0.18;
  }
}

function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min((now - lastFrame) / 1000, 0.08);
  lastFrame = now;
  if (!sceneActive || stage.clientWidth < 1 || stage.clientHeight < 1) return;
  if (!paused) {
    elapsed = (elapsed + dt * Number(speedInput.value)) % loopSeconds;
    if (now - lastInteraction > 3500) theta += dt * 0.012;
  }
  updateCamera();
  updateFlows(elapsed);
  updateBeacons(elapsed);
  updateLabels();
  timelineFill.style.width = `${elapsed / loopSeconds * 100}%`;
  clock.textContent = `00:${String(Math.floor(elapsed)).padStart(2, '0')} / 00:20`;
  renderer.render(scene, camera);
  stage.dataset.frames = String((Number(stage.dataset.frames) || 0) + 1);
}

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
stage.addEventListener('pointerdown', event => {
  dragging = { x: event.clientX, y: event.clientY, theta, phi };
  stage.setPointerCapture(event.pointerId);
  lastInteraction = performance.now();
});
stage.addEventListener('pointermove', event => {
  if (!dragging) return;
  const dx = event.clientX - dragging.x;
  const dy = event.clientY - dragging.y;
  theta = dragging.theta - dx * 0.005;
  phi = THREE.MathUtils.clamp(dragging.phi + dy * 0.004, 0.48, 1.32);
  lastInteraction = performance.now();
});
stage.addEventListener('pointerup', event => {
  if (!dragging) return;
  const moved = Math.hypot(event.clientX - dragging.x, event.clientY - dragging.y);
  dragging = null;
  if (moved > 6) return;
  const rect = stage.getBoundingClientRect();
  pointer.set(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1,
  );
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(hitMeshes, false)[0];
  if (hit) chooseTower(hit.object.userData.tower);
});
stage.addEventListener('pointercancel', () => { dragging = null; });
stage.addEventListener('wheel', event => {
  event.preventDefault();
  radius = THREE.MathUtils.clamp(radius + event.deltaY * 0.095, 73, 210);
  lastInteraction = performance.now();
}, { passive: false });

pauseButton.addEventListener('click', () => {
  paused = !paused;
  pauseButton.textContent = paused ? 'Play' : 'Pause';
  pauseButton.setAttribute('aria-pressed', String(paused));
});
resetButton.addEventListener('click', () => {
  theta = -0.42;
  phi = 0.87;
  radius = 143;
  lastInteraction = performance.now();
  chooseTower(towerById.get('TWR-0067'));
});
trafficButton.addEventListener('click', () => {
  mode = 'traffic';
  trafficButton.setAttribute('aria-pressed', 'true');
  statusButton.setAttribute('aria-pressed', 'false');
  colorTowers();
});
statusButton.addEventListener('click', () => {
  mode = 'status';
  statusButton.setAttribute('aria-pressed', 'true');
  trafficButton.setAttribute('aria-pressed', 'false');
  colorTowers();
});
speedInput.addEventListener('input', () => {
  speedValue.textContent = `${Number(speedInput.value).toFixed(Number(speedInput.value) % 1 ? 2 : 0)}x`;
});
window.addEventListener('resize', resize);
window.addEventListener('message', event => {
  if (event.source !== window.parent || event.data?.type !== 'telco-callscape-visibility') return;
  sceneActive = Boolean(event.data.active);
  if (sceneActive) {
    elapsed = 0;
    lastFrame = performance.now();
    resize();
  }
});
window.addEventListener('keydown', event => {
  if (window.parent === window || event.target instanceof HTMLInputElement) return;
  if (['ArrowRight', 'PageDown'].includes(event.key)) {
    event.preventDefault();
    window.parent.postMessage({ type: 'telco-callscape-next' }, '*');
  }
  if (['ArrowLeft', 'PageUp'].includes(event.key)) {
    event.preventDefault();
    window.parent.postMessage({ type: 'telco-callscape-previous' }, '*');
  }
});
new ResizeObserver(resize).observe(stage);
prefersReducedMotion.addEventListener('change', event => {
  if (event.matches) {
    paused = true;
    pauseButton.textContent = 'Play';
    pauseButton.setAttribute('aria-pressed', 'true');
  }
});

addTerrain();
addCityBlocks();
towers.forEach(addTower);
addFlows();
chooseTower(towerById.get('TWR-0067'));
resize();
loadState.classList.add('hidden');
stage.dataset.ready = 'true';
pauseButton.setAttribute('aria-pressed', String(paused));
if (paused) pauseButton.textContent = 'Play';
requestAnimationFrame(frame);
