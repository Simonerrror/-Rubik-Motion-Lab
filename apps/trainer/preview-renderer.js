import { applyMove, createCubeModel, createSurfaceStateSlots, snapshotForState } from "./modules/cube-core/model.js";
import { SANDBOX_MASK_COLOR } from "./modules/renderer/visual-config.js";
import { createSandbox3D } from "./sandbox3d.js";

const PREVIEW_PRESETS = Object.freeze({
  F2L: {
    moves: ["R", "U", "R'", "F"],
    stickerlessTopMask: true,
  },
  OLL: {
    moves: ["F", "R", "U", "R'", "U'", "F'"],
    stickerlessTopMask: false,
  },
  PLL: {
    moves: ["R", "U", "R'", "U'", "R'", "F", "R2", "U", "R'", "U'", "F'"],
    stickerlessTopMask: false,
  },
});

function resolveGroup() {
  const params = new URLSearchParams(window.location.search);
  const group = String(params.get("group") || "PLL").toUpperCase();
  return PREVIEW_PRESETS[group] ? group : "PLL";
}

function buildPreviewSnapshot(group) {
  const slots = createSurfaceStateSlots(3);
  const solved = slots.map((slot) => slot.face).join("");
  let model = createCubeModel(3, solved, slots);
  const preset = PREVIEW_PRESETS[group];
  preset.moves.forEach((move) => {
    model = applyMove(model, move);
  });
  return {
    snapshot: snapshotForState(model),
    stickerlessTopMask: Boolean(preset.stickerlessTopMask),
  };
}

async function main() {
  const canvas = document.getElementById("preview-capture");
  if (!(canvas instanceof HTMLCanvasElement)) {
    throw new Error("Preview canvas is unavailable");
  }

  const group = resolveGroup();
  const player = createSandbox3D(canvas);
  const payload = buildPreviewSnapshot(group);
  player.buildScene(3);
  player.setStickerlessTopMask(payload.stickerlessTopMask, SANDBOX_MASK_COLOR);
  player.renderSnapshot(payload.snapshot);
  window.dispatchEvent(new Event("resize"));
  await new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
  document.body.dataset.group = group;
  document.body.dataset.ready = "true";
}

void main().catch((error) => {
  console.error(error);
  document.body.dataset.ready = "error";
});
