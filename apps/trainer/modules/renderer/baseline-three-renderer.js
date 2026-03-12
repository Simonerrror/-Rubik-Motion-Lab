import {
  FACE_COLORS,
  LOCAL_FACE_NORMALS,
  EPSILON,
  clamp01,
  resolveEasing,
  parseColorToHex,
  buildQuaternionFromSnapshot,
  cubieHasMaskedTopColor,
} from "./common.js";
import {
  BODY_MATERIAL_CONFIG,
  CAMERA_BASE_POSITION,
  LIGHT_RIG,
  RENDERER_DIMENSIONS,
  SANDBOX_CLEAR_COLOR,
  SANDBOX_MASK_COLOR,
  STICKER_OFFSET,
} from "./visual-config.js";

export function createBaselineThreeRenderer(canvasEl) {
  const hasThree = Boolean(globalThis.THREE);
  if (!hasThree || !(canvasEl instanceof HTMLCanvasElement)) {
    return {
      buildScene() {},
      renderSnapshot() {},
      animateTransition() {
        return Promise.resolve(false);
      },
      cancelTransition() {},
      setFaceColors() {},
      setStickerlessTopMask() {},
      resize() {},
      dispose() {},
      getRenderStats() {
        return {
          backend: "noop",
          drawCalls: 0,
          triangles: 0,
          lines: 0,
          points: 0,
          sceneChildren: 0,
          cubieObjects: 0,
          stickerObjects: 0,
        };
      },
      getBackendName() {
        return "noop";
      },
    };
  }

  const THREE = globalThis.THREE;
  const cell = RENDERER_DIMENSIONS.cell;
  const cubieSize = RENDERER_DIMENSIONS.cubieSize;
  const stickerSize = RENDERER_DIMENSIONS.stickerSize;
  const stickerOffset = STICKER_OFFSET;

  let faceColors = { ...FACE_COLORS };
  let stickerlessTopMaskEnabled = false;
  let stickerlessTopMaskColor = SANDBOX_MASK_COLOR;
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
      new THREE.MeshStandardMaterial(BODY_MATERIAL_CONFIG),
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
      if (!id || cubieObjects.has(id)) return;
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
      CAMERA_BASE_POSITION.x * cameraScale,
      CAMERA_BASE_POSITION.y * cameraScale,
      CAMERA_BASE_POSITION.z * cameraScale,
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

  function getRenderStats() {
    let stickerObjects = 0;
    cubieObjects.forEach((group) => {
      stickerObjects += Object.keys(group.userData?.stickers || {}).length;
    });
    return {
      backend: "baseline",
      drawCalls: Number(renderer.info?.render?.calls || 0),
      triangles: Number(renderer.info?.render?.triangles || 0),
      lines: Number(renderer.info?.render?.lines || 0),
      points: Number(renderer.info?.render?.points || 0),
      sceneChildren: Number(scene.children?.length || 0),
      cubieObjects: Number(cubieObjects.size || 0),
      stickerObjects,
    };
  }

  renderer.setClearColor(SANDBOX_CLEAR_COLOR, 1);
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

  LIGHT_RIG.forEach((entry) => {
    if (entry.kind === "ambient") {
      scene.add(new THREE.AmbientLight(entry.color, entry.intensity));
      return;
    }
    const light = new THREE.DirectionalLight(entry.color, entry.intensity);
    light.position.set(entry.position[0], entry.position[1], entry.position[2]);
    if (entry.castShadow) {
      light.castShadow = true;
    }
    if (entry.shadowMapSize) {
      light.shadow.mapSize.set(entry.shadowMapSize[0], entry.shadowMapSize[1]);
    }
    scene.add(light);
  });

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
    getRenderStats,
    getBackendName() {
      return "baseline";
    },
  };
}
