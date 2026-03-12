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

function createNoopRenderer() {
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
        bodyInstances: 0,
        stickerFaceMeshes: 0,
        stickerInstances: 0,
      };
    },
    getBackendName() {
      return "noop";
    },
  };
}

function createStickerTemplate(THREE, faceName, stickerSize, stickerOffset) {
  const normal = LOCAL_FACE_NORMALS[faceName];
  if (!normal) return null;
  const template = new THREE.Object3D();
  template.position.set(
    normal[0] * stickerOffset,
    normal[1] * stickerOffset,
    normal[2] * stickerOffset,
  );
  if (faceName === "U") template.rotation.x = -Math.PI / 2;
  if (faceName === "D") template.rotation.x = Math.PI / 2;
  if (faceName === "R") template.rotation.y = Math.PI / 2;
  if (faceName === "L") template.rotation.y = -Math.PI / 2;
  if (faceName === "B") template.rotation.y = Math.PI;
  template.updateMatrix();
  return template.matrix.clone();
}

export function createInstancedThreeRenderer(canvasEl) {
  const hasThree = Boolean(globalThis.THREE);
  if (!hasThree || !(canvasEl instanceof HTMLCanvasElement)) {
    return createNoopRenderer();
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
  let currentModelSize = 4;
  let currentSnapshot = null;
  let bodyCapacity = 1;
  let bodyMesh = null;
  const stickerFaceMeshes = new Map();
  const stickerFaceCapacities = new Map();
  const stickerTemplates = new Map();
  const instanceMatrix = new THREE.Matrix4();
  const cubieMatrix = new THREE.Matrix4();
  const stickerMatrix = new THREE.Matrix4();
  const scaleVector = new THREE.Vector3(1, 1, 1);
  const positionVector = new THREE.Vector3();
  const instanceColor = new THREE.Color();

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
  const renderer = new THREE.WebGLRenderer({
    canvas: canvasEl,
    antialias: true,
    alpha: false,
    powerPreference: "high-performance",
  });
  const bodyGeometry = new THREE.BoxGeometry(cubieSize, cubieSize, cubieSize);
  const bodyMaterial = new THREE.MeshStandardMaterial({
    color: 0x0b1220,
    roughness: 0.86,
    metalness: 0.02,
  });
  const stickerGeometry = new THREE.PlaneGeometry(stickerSize, stickerSize);

  function render() {
    if (disposed) return;
    renderer.render(scene, camera);
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

  function ensureBodyMesh(capacity) {
    const nextCapacity = Math.max(1, Number(capacity || 1));
    if (bodyMesh && bodyCapacity >= nextCapacity) {
      return;
    }
    if (bodyMesh) {
      scene.remove(bodyMesh);
    }
    bodyCapacity = Math.max(bodyCapacity, nextCapacity);
    bodyMesh = new THREE.InstancedMesh(bodyGeometry, bodyMaterial, bodyCapacity);
    bodyMesh.castShadow = true;
    bodyMesh.receiveShadow = true;
    bodyMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage || THREE.StaticDrawUsage);
    scene.add(bodyMesh);
  }

  function ensureStickerFaceMesh(face, capacity) {
    if (!stickerTemplates.has(face)) {
      stickerTemplates.set(face, createStickerTemplate(THREE, face, stickerSize, stickerOffset));
    }
    const nextCapacity = Math.max(1, Number(capacity || 1));
    const currentCapacity = stickerFaceCapacities.get(face) || 0;
    if (stickerFaceMeshes.has(face) && currentCapacity >= nextCapacity) {
      return stickerFaceMeshes.get(face);
    }
    const existing = stickerFaceMeshes.get(face);
    if (existing) {
      scene.remove(existing);
    }
    const material = new THREE.MeshBasicMaterial({ color: 0xffffff });
    material.toneMapped = false;
    const mesh = new THREE.InstancedMesh(stickerGeometry, material, Math.max(currentCapacity, nextCapacity));
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage || THREE.StaticDrawUsage);
    mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(mesh.count * 3), 3);
    mesh.frustumCulled = false;
    scene.add(mesh);
    stickerFaceMeshes.set(face, mesh);
    stickerFaceCapacities.set(face, Math.max(currentCapacity, nextCapacity));
    return mesh;
  }

  function ensureStickerMeshes(snapshot) {
    const countsByFace = new Map();
    (snapshot?.cubies || []).forEach((cubie) => {
      Object.keys(cubie?.localColors || {}).forEach((face) => {
        countsByFace.set(face, (countsByFace.get(face) || 0) + 1);
      });
    });
    Array.from(stickerFaceMeshes.keys()).forEach((face) => {
      if (countsByFace.has(face)) return;
      const mesh = stickerFaceMeshes.get(face);
      if (mesh) {
        scene.remove(mesh);
        mesh.material.dispose();
      }
      stickerFaceMeshes.delete(face);
      stickerFaceCapacities.delete(face);
    });
    countsByFace.forEach((count, face) => {
      ensureStickerFaceMesh(face, count);
    });
    return countsByFace;
  }

  function renderSnapshot(snapshot) {
    if (disposed) return;
    currentSnapshot = snapshot || null;
    currentModelSize = Math.max(3, Number(snapshot?.size || currentModelSize || 4) || 4);
    const cubies = Array.isArray(snapshot?.cubies) ? snapshot.cubies : [];
    ensureBodyMesh(cubies.length || 1);
    const countsByFace = ensureStickerMeshes(snapshot);
    const writeIndexByFace = new Map();
    countsByFace.forEach((_count, face) => {
      writeIndexByFace.set(face, 0);
    });

    cubies.forEach((cubie, index) => {
      const quaternion = buildQuaternionFromSnapshot(THREE, cubie);
      const position = cubie?.worldPos || [0, 0, 0];
      positionVector.set(
        Number(position[0] || 0) * cell,
        Number(position[1] || 0) * cell,
        Number(position[2] || 0) * cell,
      );
      instanceMatrix.compose(positionVector, quaternion, scaleVector);
      bodyMesh.setMatrixAt(index, instanceMatrix);

      cubieMatrix.copy(instanceMatrix);
      const masked = stickerlessTopMaskEnabled && cubieHasMaskedTopColor(cubie);
      Object.keys(cubie?.localColors || {}).forEach((face) => {
        const mesh = stickerFaceMeshes.get(face);
        const stickerIndex = writeIndexByFace.get(face) || 0;
        const template = stickerTemplates.get(face);
        stickerMatrix.multiplyMatrices(cubieMatrix, template);
        mesh.setMatrixAt(stickerIndex, stickerMatrix);
        const colorCode = cubie?.localColors?.[face] || face;
        const colorHex = masked ? stickerlessTopMaskColor : (faceColors[colorCode] || 0x64748b);
        instanceColor.setHex(colorHex);
        mesh.setColorAt(stickerIndex, instanceColor);
        writeIndexByFace.set(face, stickerIndex + 1);
      });
    });

    bodyMesh.count = cubies.length;
    bodyMesh.instanceMatrix.needsUpdate = true;
    stickerFaceMeshes.forEach((mesh, face) => {
      mesh.count = writeIndexByFace.get(face) || 0;
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) {
        mesh.instanceColor.needsUpdate = true;
      }
    });
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

  function buildScene(modelSize) {
    currentModelSize = Math.max(3, Number(modelSize || 4) || 4);
    applyCameraPose();
    updateSize();
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
    if (bodyMesh) {
      scene.remove(bodyMesh);
      bodyMesh = null;
    }
    stickerFaceMeshes.forEach((mesh) => {
      scene.remove(mesh);
      mesh.material.dispose();
    });
    stickerFaceMeshes.clear();
    stickerFaceCapacities.clear();
    bodyGeometry.dispose();
    bodyMaterial.dispose();
    stickerGeometry.dispose();
    renderer.dispose();
  }

  function getRenderStats() {
    let stickerInstances = 0;
    stickerFaceMeshes.forEach((mesh) => {
      stickerInstances += Number(mesh.count || 0);
    });
    return {
      backend: "instanced",
      drawCalls: Number(renderer.info?.render?.calls || 0),
      triangles: Number(renderer.info?.render?.triangles || 0),
      lines: Number(renderer.info?.render?.lines || 0),
      points: Number(renderer.info?.render?.points || 0),
      sceneChildren: Number(scene.children?.length || 0),
      bodyInstances: Number(bodyMesh?.count || 0),
      stickerFaceMeshes: Number(stickerFaceMeshes.size || 0),
      stickerInstances,
    };
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

  buildScene(4);

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
      return "instanced";
    },
  };
}
