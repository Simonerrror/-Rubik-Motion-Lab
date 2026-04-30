import { GROUPS } from "../core/constants.js";

const PREVIEW_IMAGE_SIZES = "(max-width: 860px) calc(100vw - 48px), (max-width: 1280px) calc(100vw - 420px), (max-width: 1720px) calc(100vw - 760px), 960px";

const PREVIEW_ASSETS = Object.freeze({
  F2L: Object.freeze({
    src: "./assets/previews/trainer-preview-f2l.png",
    srcset: "./assets/previews/trainer-preview-f2l-384.jpg 384w, ./assets/previews/trainer-preview-f2l-640.jpg 640w, ./assets/previews/trainer-preview-f2l.png 960w",
    sizes: PREVIEW_IMAGE_SIZES,
  }),
  OLL: Object.freeze({
    src: "./assets/previews/trainer-preview-oll.png",
    srcset: "./assets/previews/trainer-preview-oll-384.jpg 384w, ./assets/previews/trainer-preview-oll-640.jpg 640w, ./assets/previews/trainer-preview-oll.png 960w",
    sizes: PREVIEW_IMAGE_SIZES,
  }),
  ZBLS: Object.freeze({
    src: "./assets/previews/trainer-preview-oll.png",
    srcset: "./assets/previews/trainer-preview-oll-384.jpg 384w, ./assets/previews/trainer-preview-oll-640.jpg 640w, ./assets/previews/trainer-preview-oll.png 960w",
    sizes: PREVIEW_IMAGE_SIZES,
  }),
  PLL: Object.freeze({
    src: "./assets/previews/trainer-preview-pll.png",
    srcset: "./assets/previews/trainer-preview-pll-384.jpg 384w, ./assets/previews/trainer-preview-pll-640.jpg 640w, ./assets/previews/trainer-preview-pll.png 960w",
    sizes: PREVIEW_IMAGE_SIZES,
  }),
});

export function getSandboxPreviewAsset(group) {
  const normalized = String(group || "").toUpperCase();
  if (GROUPS.includes(normalized) && PREVIEW_ASSETS[normalized]) {
    return PREVIEW_ASSETS[normalized];
  }
  return PREVIEW_ASSETS.PLL;
}
