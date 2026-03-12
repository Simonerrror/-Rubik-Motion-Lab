export const FACE_COLORS = Object.freeze({
  U: 0xfdff00,
  R: 0xc1121f,
  F: 0x2dbe4a,
  D: 0xf4f4f4,
  L: 0xe06a00,
  B: 0x2b63e8,
});

export const SANDBOX_MASK_COLOR = 0x0b1220;
export const SANDBOX_CLEAR_COLOR = 0xd8dadf;

export const RENDERER_DIMENSIONS = Object.freeze({
  cell: 1.04,
  cubieSize: 0.9,
  stickerSize: 0.74,
});

export const STICKER_OFFSET = (RENDERER_DIMENSIONS.cubieSize * 0.5) + 0.014;

export const CAMERA_BASE_POSITION = Object.freeze({
  x: 4.8,
  y: 5.6,
  z: 6.4,
});

export const BODY_MATERIAL_CONFIG = Object.freeze({
  color: SANDBOX_MASK_COLOR,
  roughness: 0.86,
  metalness: 0.02,
});

export const LIGHT_RIG = Object.freeze([
  {
    kind: "ambient",
    color: 0xffffff,
    intensity: 0.32,
  },
  {
    kind: "directional",
    color: 0xffffff,
    intensity: 0.58,
    position: Object.freeze([6.2, 8.6, 7.1]),
    castShadow: true,
    shadowMapSize: Object.freeze([1024, 1024]),
  },
  {
    kind: "directional",
    color: 0xffffff,
    intensity: 0.12,
    position: Object.freeze([-4.8, 3.8, -5.7]),
  },
  {
    kind: "directional",
    color: 0xffffff,
    intensity: 0.08,
    position: Object.freeze([-1.5, 6.4, 6.8]),
  },
]);
