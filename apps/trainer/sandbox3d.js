import { createBaselineThreeRenderer } from "./modules/renderer/baseline-three-renderer.js";
import { createInstancedThreeRenderer } from "./modules/renderer/instanced-three-renderer.js";
import { pickRendererBackend } from "./modules/renderer/factory.js";

const RENDERER_CREATORS = {
  baseline: createBaselineThreeRenderer,
  instanced: createInstancedThreeRenderer,
};

function createSandbox3D(canvasEl) {
  let activeRenderer = null;
  let activeBackend = "";
  let currentSnapshot = null;
  let currentFaceColors = null;
  let currentMaskEnabled = false;
  let currentMaskColor = 0x0b1220;

  function ensureRenderer(modelSize) {
    const backend = pickRendererBackend(modelSize);
    if (activeRenderer && activeBackend === backend) {
      return activeRenderer;
    }
    if (activeRenderer) {
      activeRenderer.dispose?.();
    }
    activeBackend = backend;
    const createRenderer = RENDERER_CREATORS[backend] || createBaselineThreeRenderer;
    activeRenderer = createRenderer(canvasEl);
    activeRenderer.buildScene?.(modelSize);
    activeRenderer.setFaceColors?.(currentFaceColors);
    activeRenderer.setStickerlessTopMask?.(currentMaskEnabled, currentMaskColor);
    if (currentSnapshot) {
      activeRenderer.renderSnapshot?.(currentSnapshot);
    }
    return activeRenderer;
  }

  return {
    buildScene(modelSize) {
      ensureRenderer(modelSize).buildScene?.(modelSize);
    },
    renderSnapshot(snapshot) {
      currentSnapshot = snapshot || null;
      const modelSize = Number(snapshot?.size || 3) || 3;
      ensureRenderer(modelSize).renderSnapshot?.(currentSnapshot);
    },
    animateTransition(fromSnapshot, toSnapshot, options = {}) {
      currentSnapshot = toSnapshot || currentSnapshot;
      const modelSize = Number(toSnapshot?.size || fromSnapshot?.size || 3) || 3;
      return ensureRenderer(modelSize).animateTransition?.(fromSnapshot, toSnapshot, options) || Promise.resolve(false);
    },
    cancelTransition() {
      activeRenderer?.cancelTransition?.();
    },
    setFaceColors(faceColors) {
      currentFaceColors = faceColors == null ? null : { ...faceColors };
      activeRenderer?.setFaceColors?.(currentFaceColors);
    },
    setStickerlessTopMask(enabled, colorHex) {
      currentMaskEnabled = Boolean(enabled);
      if (typeof colorHex !== "undefined") {
        currentMaskColor = colorHex;
      }
      activeRenderer?.setStickerlessTopMask?.(currentMaskEnabled, currentMaskColor);
    },
    resize() {
      activeRenderer?.resize?.();
    },
    dispose() {
      activeRenderer?.dispose?.();
      activeRenderer = null;
      activeBackend = "";
    },
    getRenderStats() {
      return activeRenderer?.getRenderStats?.() || {
        backend: activeBackend || "none",
        drawCalls: 0,
        triangles: 0,
        lines: 0,
        points: 0,
      };
    },
    getBackendName() {
      return activeRenderer?.getBackendName?.() || activeBackend || "none";
    },
  };
}

globalThis.CubeSandbox3D = {
  createSandbox3D,
};
