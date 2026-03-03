(() => {
  const FACE_COLORS = {
    U: 0xfdff00,
    R: 0xc1121f,
    F: 0x2dbe4a,
    D: 0xf4f4f4,
    L: 0xe06a00,
    B: 0x2b63e8,
  };

  const BASE_TO_AXIS = {
    F: "x",
    B: "x",
    S: "x",
    f: "x",
    b: "x",
    z: "x",
    U: "z",
    D: "z",
    E: "z",
    u: "z",
    d: "z",
    y: "z",
    L: "y",
    R: "y",
    M: "y",
    l: "y",
    r: "y",
    x: "y",
  };

  const POSITIVE_BASES = new Set(["R", "F", "D", "E", "S", "r", "f", "d", "x", "z"]);

  const WORLD_AXIS_BY_STATE_AXIS = {
    x: [0, 0, -1],
    y: [-1, 0, 0],
    z: [0, 1, 0],
  };

  const FACE_TO_WORLD_NORMAL = {
    U: [0, 1, 0],
    D: [0, -1, 0],
    R: [1, 0, 0],
    L: [-1, 0, 0],
    F: [0, 0, 1],
    B: [0, 0, -1],
  };

  function makeKey(x, y, z) {
    return `${x},${y},${z}`;
  }

  function mapStateToWorld(statePos) {
    const sx = Number(statePos[0] || 0);
    const sy = Number(statePos[1] || 0);
    const sz = Number(statePos[2] || 0);
    return [-sy, sz, -sx];
  }

  function mapWorldToState(worldPos) {
    const wx = Number(worldPos[0] || 0);
    const wy = Number(worldPos[1] || 0);
    const wz = Number(worldPos[2] || 0);
    return [-wz, -wx, wy];
  }

  function splitMoveModifier(move) {
    if (move.endsWith("2'")) {
      return [move.slice(0, -2), "2"];
    }
    if (move.endsWith("2")) {
      return [move.slice(0, -1), "2"];
    }
    if (move.endsWith("'")) {
      return [move.slice(0, -1), "'"];
    }
    return [move, ""];
  }

  function turnsForMove(base, modifier) {
    let turns = POSITIVE_BASES.has(base) ? 1 : -1;
    if (modifier === "'") turns *= -1;
    if (modifier === "2") turns *= 2;
    return turns;
  }

  function selectorForBase(base) {
    if (base === "F") return (p) => p.x === -1;
    if (base === "B") return (p) => p.x === 1;
    if (base === "S") return (p) => p.x === 0;
    if (base === "f") return (p) => p.x === -1 || p.x === 0;
    if (base === "b") return (p) => p.x === 0 || p.x === 1;

    if (base === "U") return (p) => p.z === 1;
    if (base === "D") return (p) => p.z === -1;
    if (base === "E") return (p) => p.z === 0;
    if (base === "u") return (p) => p.z === 0 || p.z === 1;
    if (base === "d") return (p) => p.z === -1 || p.z === 0;

    if (base === "L") return (p) => p.y === 1;
    if (base === "R") return (p) => p.y === -1;
    if (base === "M") return (p) => p.y === 0;
    if (base === "l") return (p) => p.y === 0 || p.y === 1;
    if (base === "r") return (p) => p.y === -1 || p.y === 0;

    if (base === "x" || base === "y" || base === "z") {
      return () => true;
    }

    return null;
  }

  function parseMove(move, reverse = false) {
    const token = String(move || "").trim();
    if (!token) return null;

    const [base, modifier] = splitMoveModifier(token);
    const axis = BASE_TO_AXIS[base];
    const selector = selectorForBase(base);
    if (!axis || !selector) {
      return null;
    }

    let turns = turnsForMove(base, modifier);
    if (reverse) turns *= -1;
    if (!Number.isFinite(turns) || turns === 0) {
      return null;
    }

    return {
      axis,
      selector,
      turns,
    };
  }

  function easeInOutSine(t) {
    return 0.5 - 0.5 * Math.cos(Math.PI * t);
  }

  function resolveEasingProgress(t, easingName) {
    if (String(easingName || "").trim() === "ease_in_out_sine") {
      return easeInOutSine(t);
    }
    return easeInOutSine(t);
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
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

  function createSandbox3D(canvasEl) {
    const hasThree = Boolean(window.THREE);
    const cell = 1.04;
    const cubieSize = 0.9;
    const stickerSize = 0.74;
    const stickerOffset = (cubieSize * 0.5) + 0.014;
    const BASE_CAMERA_POSITION = { x: 4.8, y: 5.6, z: 6.4 };

    let slots = [];
    let currentState = "";
    let faceColors = { ...FACE_COLORS };
    let stickerlessTopMaskEnabled = false;
    let stickerlessTopMaskColor = 0x0b1220;
    let disposed = false;
    let isAnimating = false;
    let animationRaf = 0;

    const scene = hasThree ? new THREE.Scene() : null;
    const camera = hasThree ? new THREE.PerspectiveCamera(34, 1, 0.1, 100) : null;
    const renderer = hasThree
      ? new THREE.WebGLRenderer({
        canvas: canvasEl,
        antialias: true,
        alpha: false,
        powerPreference: "high-performance",
      })
      : null;

    const cubies = [];

    function clearScene() {
      cubies.forEach((cubie) => {
        scene.remove(cubie);
      });
      cubies.length = 0;
    }

    function createSticker(faceName) {
      const normal = FACE_TO_WORLD_NORMAL[faceName];
      if (!normal) return null;

      const geom = new THREE.PlaneGeometry(stickerSize, stickerSize);
      const material = new THREE.MeshBasicMaterial({
        color: 0x334155,
      });
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

    function createCubie(statePos) {
      const [sx, sy, sz] = statePos;
      const [wx, wy, wz] = mapStateToWorld(statePos);

      const cubie = new THREE.Group();
      cubie.position.set(wx * cell, wy * cell, wz * cell);

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
      cubie.add(body);

      const stickers = {};
      if (sz === 1) stickers.U = createSticker("U");
      if (sz === -1) stickers.D = createSticker("D");
      if (sy === -1) stickers.R = createSticker("R");
      if (sy === 1) stickers.L = createSticker("L");
      if (sx === -1) stickers.F = createSticker("F");
      if (sx === 1) stickers.B = createSticker("B");

      Object.values(stickers).forEach((sticker) => {
        if (sticker) cubie.add(sticker);
      });

      cubie.userData.stickers = stickers;
      cubie.userData.statePos = { x: sx, y: sy, z: sz };
      cubies.push(cubie);
      scene.add(cubie);
    }

    function buildSolvedGeometry() {
      clearScene();
      for (let x = -1; x <= 1; x += 1) {
        for (let y = -1; y <= 1; y += 1) {
          for (let z = -1; z <= 1; z += 1) {
            createCubie([x, y, z]);
          }
        }
      }
    }

    function cubieFromStatePosition(position) {
      const [sx, sy, sz] = position;
      const [wx, wy, wz] = mapStateToWorld([sx, sy, sz]);
      const targetX = Math.round(wx);
      const targetY = Math.round(wy);
      const targetZ = Math.round(wz);
      for (const cubie of cubies) {
        const cx = Math.round(cubie.position.x / cell);
        const cy = Math.round(cubie.position.y / cell);
        const cz = Math.round(cubie.position.z / cell);
        if (cx === targetX && cy === targetY && cz === targetZ) {
          return cubie;
        }
      }
      return null;
    }

    function setAllStickersToNeutral() {
      cubies.forEach((cubie) => {
        const stickers = cubie.userData.stickers || {};
        Object.values(stickers).forEach((sticker) => {
          if (!sticker?.material?.color) return;
          sticker.material.color.setHex(0x334155);
        });
      });
    }

    function applyStateColors(state) {
      setAllStickersToNeutral();
      if (!Array.isArray(slots) || !slots.length) return;
      const normalized = String(state || "");
      const length = Math.min(normalized.length, slots.length);
      const maskedCubieKeys = new Set();
      if (stickerlessTopMaskEnabled) {
        for (let idx = 0; idx < length; idx += 1) {
          if (normalized[idx] !== "U") continue;
          const slot = slots[idx];
          const position = Array.isArray(slot?.position) ? slot.position : [0, 0, 0];
          maskedCubieKeys.add(makeKey(position[0], position[1], position[2]));
        }
      }
      for (let idx = 0; idx < length; idx += 1) {
        const slot = slots[idx];
        const face = String(slot?.face || "");
        const position = Array.isArray(slot?.position) ? slot.position : [0, 0, 0];
        const colorCode = normalized[idx];
        const cubieKey = makeKey(position[0], position[1], position[2]);
        const colorHex = (stickerlessTopMaskEnabled && maskedCubieKeys.has(cubieKey))
          ? stickerlessTopMaskColor
          : (faceColors[colorCode] || 0x64748b);

        const cubie = cubieFromStatePosition(position);
        const sticker = cubie?.userData?.stickers?.[face] || null;
        if (sticker?.material?.color) {
          sticker.material.color.setHex(colorHex);
        }
      }
    }

    function getStatePositionForCubie(cubie) {
      const wx = Math.round(cubie.position.x / cell);
      const wy = Math.round(cubie.position.y / cell);
      const wz = Math.round(cubie.position.z / cell);
      const [sx, sy, sz] = mapWorldToState([wx, wy, wz]);
      return { x: sx, y: sy, z: sz };
    }

    function snapRotation(quaternion) {
      const matrix = new THREE.Matrix4().makeRotationFromQuaternion(quaternion);
      const e = matrix.elements;
      const snap = (v) => {
        if (Math.abs(v) < 0.5) return 0;
        return v > 0 ? 1 : -1;
      };

      const r00 = snap(e[0]);
      const r01 = snap(e[4]);
      const r02 = snap(e[8]);
      const r10 = snap(e[1]);
      const r11 = snap(e[5]);
      const r12 = snap(e[9]);
      const r20 = snap(e[2]);
      const r21 = snap(e[6]);
      const r22 = snap(e[10]);

      const snapped = new THREE.Matrix4();
      snapped.set(
        r00, r01, r02, 0,
        r10, r11, r12, 0,
        r20, r21, r22, 0,
        0, 0, 0, 1,
      );

      return new THREE.Quaternion().setFromRotationMatrix(snapped);
    }

    function snapCubiesToGrid() {
      cubies.forEach((cubie) => {
        const gx = Math.round(cubie.position.x / cell);
        const gy = Math.round(cubie.position.y / cell);
        const gz = Math.round(cubie.position.z / cell);
        cubie.position.set(gx * cell, gy * cell, gz * cell);
        cubie.quaternion.copy(snapRotation(cubie.quaternion));
        const [sx, sy, sz] = mapWorldToState([gx, gy, gz]);
        cubie.userData.statePos = { x: sx, y: sy, z: sz };
      });
    }

    function render() {
      if (!hasThree || disposed) return;
      renderer.render(scene, camera);
    }

    function applyCameraPose() {
      if (!hasThree || disposed) return;
      const dpr = Number(window.devicePixelRatio || 1);
      const retinaScale = dpr >= 1.75 ? 1.14 : 1;
      const cubeScale = 0.9;
      const cameraScale = retinaScale * cubeScale;
      camera.position.set(
        BASE_CAMERA_POSITION.x * cameraScale,
        BASE_CAMERA_POSITION.y * cameraScale,
        BASE_CAMERA_POSITION.z * cameraScale,
      );
      camera.lookAt(0, 0, 0);
    }

    function updateSize() {
      if (!hasThree || disposed) return;
      const rect = canvasEl.getBoundingClientRect();
      const width = Math.max(1, Math.floor(rect.width));
      const height = Math.max(1, Math.floor(rect.height));
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 3));
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      applyCameraPose();
      render();
    }

    function resetFromState(state) {
      if (!hasThree || disposed) return;
      if (animationRaf) {
        cancelAnimationFrame(animationRaf);
        animationRaf = 0;
      }
      isAnimating = false;
      currentState = String(state || "");
      buildSolvedGeometry();
      applyStateColors(currentState);
      render();
    }

    function setSlots(newSlots) {
      slots = Array.isArray(newSlots) ? newSlots : [];
      if (currentState) {
        applyStateColors(currentState);
      }
      render();
    }

    function stateAxisToVector(axis) {
      const raw = WORLD_AXIS_BY_STATE_AXIS[axis] || [0, 1, 0];
      return new THREE.Vector3(raw[0], raw[1], raw[2]);
    }

    function collectMoveParts(stepMoves, reverse = false) {
      const moves = Array.isArray(stepMoves) ? stepMoves : [];
      const parts = [];
      const seenCubies = new Set();

      for (const move of moves) {
        const parsed = parseMove(move, reverse);
        if (!parsed) return null;

        const picked = cubies.filter((cubie) => parsed.selector(getStatePositionForCubie(cubie)));
        if (!picked.length) continue;

        for (const cubie of picked) {
          if (seenCubies.has(cubie)) return null;
          seenCubies.add(cubie);
        }

        const pivot = new THREE.Group();
        scene.add(pivot);
        picked.forEach((cubie) => pivot.attach(cubie));

        parts.push({
          pivot,
          cubies: picked,
          axisVector: stateAxisToVector(parsed.axis),
          angleTarget: (parsed.turns * Math.PI) / 2,
        });
      }

      return parts;
    }

    function applyPartsProgress(parts, easedProgress) {
      parts.forEach((part) => {
        part.pivot.setRotationFromAxisAngle(part.axisVector, part.angleTarget * easedProgress);
      });
    }

    function detachParts(parts) {
      parts.forEach((part) => {
        part.cubies.forEach((cubie) => {
          scene.attach(cubie);
        });
        scene.remove(part.pivot);
      });
    }

    function playStep(stepMoves, options = {}) {
      if (!hasThree || disposed || isAnimating) {
        return Promise.resolve(false);
      }

      const moves = Array.isArray(stepMoves) ? stepMoves : [];
      if (!moves.length) {
        return Promise.resolve(false);
      }

      const reverse = Boolean(options.reverse);
      const durationMs = Math.max(80, Number(options.durationMs || 360));
      const easing = String(options.easing || "ease_in_out_sine").trim();
      const baseState = typeof options.baseState === "string" ? options.baseState : "";
      const onProgress = typeof options.onProgress === "function" ? options.onProgress : null;
      const startProgress = clamp(Number(options.startProgress) || 0, 0, 1);

      if (baseState) {
        resetFromState(baseState);
      }

      const parts = collectMoveParts(moves, reverse);
      if (!parts || !parts.length) {
        return Promise.resolve(false);
      }

      isAnimating = true;
      let startTs = 0;
      if (onProgress) onProgress(startProgress);

      return new Promise((resolve) => {
        const tick = (timestamp) => {
          if (disposed) {
            isAnimating = false;
            resolve(false);
            return;
          }

          if (!startTs) startTs = timestamp;
          const elapsed = timestamp - startTs;
          const rawT = clamp(elapsed / durationMs, 0, 1);
          const t = startProgress + ((1 - startProgress) * rawT);
          const eased = resolveEasingProgress(t, easing);

          applyPartsProgress(parts, eased);
          if (onProgress) onProgress(t);
          render();

          if (t < 1) {
            animationRaf = requestAnimationFrame(tick);
            return;
          }

          detachParts(parts);
          snapCubiesToGrid();
          render();
          isAnimating = false;
          animationRaf = 0;
          if (onProgress) onProgress(1);
          resolve(true);
        };

        animationRaf = requestAnimationFrame(tick);
      });
    }

    function previewStepFromState(baseState, stepMoves, options = {}) {
      if (!hasThree || disposed || isAnimating) {
        return false;
      }

      const base = String(baseState || "");
      resetFromState(base);

      const moves = Array.isArray(stepMoves) ? stepMoves : [];
      if (!moves.length) {
        return true;
      }

      const reverse = Boolean(options.reverse);
      const easing = String(options.easing || "ease_in_out_sine").trim();
      const progress = clamp(Number(options.progress) || 0, 0, 1);
      if (progress <= 0) return true;

      const parts = collectMoveParts(moves, reverse);
      if (!parts || !parts.length) {
        return false;
      }

      const eased = resolveEasingProgress(progress, easing);
      applyPartsProgress(parts, eased);
      detachParts(parts);
      render();
      return true;
    }

    function setFaceColors(faceColorMap) {
      if (faceColorMap == null) {
        faceColors = { ...FACE_COLORS };
        applyStateColors(currentState);
        render();
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
      applyStateColors(currentState);
      render();
    }

    function setStickerlessTopMask(enabled, colorHex) {
      stickerlessTopMaskEnabled = Boolean(enabled);
      if (typeof colorHex !== "undefined") {
        stickerlessTopMaskColor = parseColorToHex(colorHex, stickerlessTopMaskColor);
      }
      applyStateColors(currentState);
      render();
    }

    function setState(state) {
      resetFromState(state);
    }

    function resize() {
      updateSize();
    }

    function dispose() {
      disposed = true;
      if (animationRaf) {
        cancelAnimationFrame(animationRaf);
        animationRaf = 0;
      }
      clearScene();
      if (renderer) {
        renderer.dispose();
      }
    }

    if (hasThree) {
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

      applyCameraPose();

      buildSolvedGeometry();
      applyStateColors(currentState);
      updateSize();
      render();
    }

    return {
      setSlots,
      setState,
      setFaceColors,
      setStickerlessTopMask,
      previewStepFromState,
      resize,
      dispose,
      playStep,
    };
  }

  window.CubeSandbox3D = {
    createSandbox3D,
  };
})();
