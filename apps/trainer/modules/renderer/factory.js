import { INSTANCED_RENDERER_MIN_SIZE } from "../core/constants.js";

export function pickRendererBackend(modelSize) {
  const size = Math.max(3, Number(modelSize || 3) || 3);
  return size >= INSTANCED_RENDERER_MIN_SIZE ? "instanced" : "baseline";
}
