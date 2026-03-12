import { GROUPS } from "../core/constants.js";

const PREVIEW_ASSETS = Object.freeze({
  F2L: "./assets/previews/trainer-preview-f2l.png",
  OLL: "./assets/previews/trainer-preview-oll.png",
  PLL: "./assets/previews/trainer-preview-pll.png",
});

export function getSandboxPreviewAsset(group) {
  const normalized = String(group || "").toUpperCase();
  if (GROUPS.includes(normalized)) {
    return PREVIEW_ASSETS[normalized];
  }
  return PREVIEW_ASSETS.PLL;
}
