import { createBaselineThreeRenderer } from "./modules/renderer/baseline-three-renderer.js";

function createSandbox3D(canvasEl) {
  const renderer = createBaselineThreeRenderer(canvasEl);
  return {
    buildScene: renderer.buildScene,
    renderSnapshot: renderer.renderSnapshot,
    animateTransition: renderer.animateTransition,
    cancelTransition: renderer.cancelTransition,
    setFaceColors: renderer.setFaceColors,
    setStickerlessTopMask: renderer.setStickerlessTopMask,
    resize: renderer.resize,
    dispose: renderer.dispose,
  };
}

globalThis.CubeSandbox3D = {
  createSandbox3D,
};
