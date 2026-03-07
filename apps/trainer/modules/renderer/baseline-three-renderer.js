const FACE_COLORS = {
  U: 0xfdff00,
  R: 0xc1121f,
  F: 0x2dbe4a,
  D: 0xf4f4f4,
  L: 0xe06a00,
  B: 0x2b63e8,
};

const LOCAL_FACE_NORMALS = {
  U: [0, 1, 0],
  D: [0, -1, 0],
  R: [1, 0, 0],
  L: [-1, 0, 0],
  F: [0, 0, 1],
  B: [0, 0, -1],
};

const EPSILON = 1e-6;

function clamp01(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return 0;
  if (numeric <= 0) return 0;
  if (numeric >= 1) return 1;
  return numeric;
}

function easeInOutSine(t) {
  return 0.5 - (0.5 * Math.cos(Math.PI * t));
}

function resolveEasing(easingName) {
  if (String(easingName || "").trim() === "ease_in_out_sine") {
    return easeInOutSine;
  }
  return easeInOutSine;
}

function parseColorToHex(raw, fallback) {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return raw >>> 0;
  }
  if (typeof raw === "string") {
    const normalized = raw.trim().replace(/^#/, "");
    if (/^[0-9a-fA-F]{6}$/.test(normalized)) {
      return Number.parseInt(normalized, 16);
    }
  }
  return fallback;
}

function buildQuaternionFromSnapshot(THREE, cubie) {
  const normals = cubie?.worldNormalsByLocalFace || {};
  const xAxis = normals.R || [1, 0, 0];
  const yAxis = normals.U || [0, 1, 0];
  const zAxis = normals.F || [0, 0, 1];
  const matrix = new THREE.Matrix4().makeBasis(
    new THREE.Vector3(xAxis[0], xAxis[1], xAxis[2]),
    new THREE.Vector3(yAxis[0], yAxis[1], yAxis[2]),
    new THREE.Vector3(zAxis[0], zAxis[1], zAxis[2]),
  );
  return new THREE.Quaternion().setFromRotationMatrix(matrix);
}

function cubieHasMaskedTopColor(cubie) {
  return Object.values(cubie?.localColors || {}).includes("U");
}

export function createBaselineThreeRenderer(canvasEl) {
  const hasThree = Boolean(globalThis.THREE);
  if (!hasThree || !(canvasEl instanceof HTMLCanvasElement)) {
    return {
      buildScene() {},
      renderSnapshot() {},
      animateTransition() {
        return Promise.resolve(false);
      },
      setFaceColors() {},
      setStickerlessTopMask() {},
      resize() {},
      dispose() {},
    };
  }

  const THREE = globalThis.THREE;
  const cell = 1.04;
  const cubieSize = 0.9;
  const stickerSize = 0.74;
  const stickerOffset = (cubieSize * 0.5) + 0.014;
  const BASE_CAMERA_POSITION = { x: 4.8, y: 5.6, z: 6.4 };

  let faceColors = { ...FACE_COLORS };
  let stickerlessTopMaskEnabled = false;
  let stickerlessTopMaskColor = 0x0b1220;
  let disposed = false;
  let animationRaf = 0;
  let activeAnimationResolve = null;
  let currentModelSize = 3;
  let currentSnapshot = null;
  const cubieObjects = new Map();

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
  const renderer = new THREE.WebGLRenderer({
    canvas: canvasEl,
    antialias: true,
    alpha: false,
    powerPreference: "high-performance",
  });

  function render() {
    if (disposed) return;
    renderer.render(scene, camera);
  }

  function createSticker(faceName) {
    const normal = LOCAL_FACE_NORMALS[faceName];
    if (!normal) return null;
    const geom = new THREE.PlaneGeometry(stickerSize, stickerSize);
    const material = new THREE.MeshBasicMaterial({ color: 0x334155 });
    material.toneMapped = false;
    const mesh = new THREE.Mesh(geom, material);
    mesh.position.set(
      normal[0] * stickerOffset,
      normal[1] * stickerOffset,
      normal[2] * stickerOffset,
    );
    if (faceName === "U") mesh.rotation.x = -Math.PI / 2;
    if (faceName === "D") mesh.rotation.x = Math.PI / 2;
    if (faceName === "R") mesh.rotation.y = Math.PI / 2;
    if (faceName === "L") mesh.rotation.y = -Math.PI / 2;
    if (faceName === "B") mesh.rotation.y = Math.PI;
    return mesh;
  }

  function createCubieObject(cubie) {
    const group = new THREE.Group();
    const body = new THREE.Mesh(
      new THREE.BoxGeometry(cubieSize, cubieSize, cubieSize),
      new THREE.MeshStandardMaterial({
        color: 0x0b1220,
        roughness: 0.86,
        metalness: 0.02,
      }),
    );
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    const stickers = {};
    Object.keys(cubie?.localColors || {}).forEach((face) => {
      const sticker = createSticker(face);
      if (!sticker) return;
      stickers[face] = sticker;
      group.add(sticker);
    });

    group.userData.stickers = stickers;
    return group;
  }

  function clearCubies() {
    cubieObjects.forEach((group) => {
      scene.remove(group);
    });
    cubieObjects.clear();
  }

  function ensureCubieObjects(snapshot) {
    const incoming = Array.isArray(snapshot?.cubies) ? snapshot.cubies : [];
    const incomingIds = new Set(incoming.map((cubie) => String(cubie.id || "")));
    Array.from(cubieObjects.keys()).forEach((id) => {
      if (incomingIds.has(id)) return;
      const group = cubieObjects.get(id);
      if (group) scene.remove(group);
      cubieObjects.delete(id);
    });

    incoming.forEach((cubie) => {
      const id = String(cubie.id || "");
      if (!id) return;
      if (cubieObjects.has(id)) return;
      const group = createCubieObject(cubie);
      cubieObjects.set(id, group);
      scene.add(group);
    });
  }

  function applyCameraPose() {
    if (disposed) return;
    const dpr = Number(globalThis.devicePixelRatio || 1);
    const retinaScale = dpr >= 1.75 ? 1.14 : 1;
    const sizeScale = Math.max(1, currentModelSize / 3);
    const cameraScale = retinaScale * sizeScale;
    camera.position.set(
      BASE_CAMERA_POSITION.x * cameraScale,
      BASE_CAMERA_POSITION.y * cameraScale,
      BASE_CAMERA_POSITION.z * cameraScale,
    );
    camera.lookAt(0, 0, 0);
  }

  function updateSize() {
    if (disposed) return;
    const rect = canvasEl.getBoundingClientRect();
    const width = Math.max(1, Math.floor(rect.width));
    const height = Math.max(1, Math.floor(rect.height));
    renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio || 1, 3));
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    applyCameraPose();
    render();
  }

  function applyCubieSnapshot(cubie) {
    const id = String(cubie.id || "");
    const group = cubieObjects.get(id);
    if (!group) return;
    const position = cubie?.worldPos || [0, 0, 0];
    group.position.set(
      Number(position[0] || 0) * cell,
      Number(position[1] || 0) * cell,
      Number(position[2] || 0) * cell,
    );
    group.quaternion.copy(buildQuaternionFromSnapshot(THREE, cubie));

    const masked = stickerlessTopMaskEnabled && cubieHasMaskedTopColor(cubie);
    const stickers = group.userData.stickers || {};
    Object.entries(stickers).forEach(([face, sticker]) => {
      const colorCode = cubie?.localColors?.[face] || face;
      const colorHex = masked ? stickerlessTopMaskColor : (faceColors[colorCode] || 0x64748b);
      if (sticker?.material?.color) {
        sticker.material.color.setHex(colorHex);
      }
    });
  }

  function buildScene(modelSize) {
    currentModelSize = Math.max(3, Number(modelSize || 3) || 3);
    applyCameraPose();
    updateSize();
  }

  function renderSnapshot(snapshot) {
    if (disposed) return;
    currentSnapshot = snapshot || null;
    currentModelSize = Math.max(3, Number(snapshot?.size || currentModelSize || 3) || 3);
    ensureCubieObjects(snapshot);
    (snapshot?.cubies || []).forEach(applyCubieSnapshot);
    render();
  }

  function cancelAnimation(resolveValue) {
    if (animationRaf) {
      cancelAnimationFrame(animationRaf);
      animationRaf = 0;
    }
    if (typeof activeAnimationResolve === "function") {
      const resolver = activeAnimationResolve;
      activeAnimationResolve = null;
      resolver(resolveValue);
    }
  }

  function animateTransition(fromSnapshot, toSnapshot, options = {}) {
    if (disposed) return Promise.resolve(false);
    const interpolator = typeof options.interpolator === "function"
      ? options.interpolator
      : (progress) => (progress >= 1 ? toSnapshot : fromSnapshot);
    const durationMs = Math.max(80, Number(options.durationMs || 240));
    const easing = resolveEasing(options.easing);
    const onProgress = typeof options.onProgress === "function" ? options.onProgress : null;

    cancelAnimation(false);
    renderSnapshot(fromSnapshot);
    if (onProgress) onProgress(0);

    let startedAt = 0;
    return new Promise((resolve) => {
      activeAnimationResolve = resolve;
      const tick = (timestamp) => {
        if (disposed) {
          cancelAnimation(false);
          return;
        }
        if (!startedAt) startedAt = timestamp;
        const raw = clamp01((timestamp - startedAt) / durationMs);
        const eased = easing(raw);
        renderSnapshot(interpolator(eased));
        if (onProgress) onProgress(raw);
        if (raw >= 1 - EPSILON) {
          renderSnapshot(toSnapshot);
          if (onProgress) onProgress(1);
          cancelAnimation(true);
          return;
        }
        animationRaf = requestAnimationFrame(tick);
      };
      animationRaf = requestAnimationFrame(tick);
    });
  }

  function setFaceColors(faceColorMap) {
    if (faceColorMap == null) {
      faceColors = { ...FACE_COLORS };
      renderSnapshot(currentSnapshot);
      return;
    }
    if (typeof faceColorMap !== "object") return;
    faceColors = {
      U: parseColorToHex(faceColorMap.U, faceColors.U),
      R: parseColorToHex(faceColorMap.R, faceColors.R),
      F: parseColorToHex(faceColorMap.F, faceColors.F),
      D: parseColorToHex(faceColorMap.D, faceColors.D),
      L: parseColorToHex(faceColorMap.L, faceColors.L),
      B: parseColorToHex(faceColorMap.B, faceColors.B),
    };
    renderSnapshot(currentSnapshot);
  }

  function setStickerlessTopMask(enabled, colorHex) {
    stickerlessTopMaskEnabled = Boolean(enabled);
    if (typeof colorHex !== "undefined") {
      stickerlessTopMaskColor = parseColorToHex(colorHex, stickerlessTopMaskColor);
    }
    renderSnapshot(currentSnapshot);
  }

  function dispose() {
    cancelAnimation(false);
    disposed = true;
    clearCubies();
    renderer.dispose();
  }

  renderer.setClearColor(0xd8dadf, 1);
  if ("outputColorSpace" in renderer && THREE.SRGBColorSpace) {
    renderer.outputColorSpace = THREE.SRGBColorSpace;
  } else if ("outputEncoding" in renderer && THREE.sRGBEncoding) {
    renderer.outputEncoding = THREE.sRGBEncoding;
  }
  if ("toneMapping" in renderer && THREE.NoToneMapping != null) {
    renderer.toneMapping = THREE.NoToneMapping;
    renderer.toneMappingExposure = 1;
  }
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const ambient = new THREE.AmbientLight(0xffffff, 0.32);
  scene.add(ambient);
  const keyLight = new THREE.DirectionalLight(0xffffff, 0.58);
  keyLight.position.set(6.2, 8.6, 7.1);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  scene.add(keyLight);
  const fillLight = new THREE.DirectionalLight(0xffffff, 0.12);
  fillLight.position.set(-4.8, 3.8, -5.7);
  scene.add(fillLight);
  const rimLight = new THREE.DirectionalLight(0xffffff, 0.08);
  rimLight.position.set(-1.5, 6.4, 6.8);
  scene.add(rimLight);

  buildScene(3);

  return {
    buildScene,
    renderSnapshot,
    animateTransition,
    cancelTransition() {
      cancelAnimation(false);
      if (currentSnapshot) {
        renderSnapshot(currentSnapshot);
      }
    },
    setFaceColors,
    setStickerlessTopMask,
    resize: updateSize,
    dispose,
  };
}
