export { FACE_COLORS } from "./visual-config.js";

export const LOCAL_FACE_NORMALS = {
  U: [0, 1, 0],
  D: [0, -1, 0],
  R: [1, 0, 0],
  L: [-1, 0, 0],
  F: [0, 0, 1],
  B: [0, 0, -1],
};

export const EPSILON = 1e-6;

export function clamp01(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return 0;
  if (numeric <= 0) return 0;
  if (numeric >= 1) return 1;
  return numeric;
}

function easeInOutSine(t) {
  return 0.5 - (0.5 * Math.cos(Math.PI * t));
}

export function resolveEasing(easingName) {
  if (String(easingName || "").trim() === "ease_in_out_sine") {
    return easeInOutSine;
  }
  return easeInOutSine;
}

export function parseColorToHex(raw, fallback) {
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

export function buildQuaternionFromSnapshot(THREE, cubie) {
  const normals = cubie?.worldNormalsByLocalFace || {};
  const xAxis = normals.R || [1, 0, 0];
  const yAxis = normals.U || [0, 1, 0];
  const zAxis = normals.F || [0, 0, 1];
  const matrix = new THREE.Matrix4().makeBasis(
    new THREE.Vector3(xAxis[0], xAxis[1], xAxis[2]),
    new THREE.Vector3(yAxis[0], yAxis[1], yAxis[2]),
    new THREE.Vector3(zAxis[0], zAxis[1], zAxis[2]),
  );
  return new THREE.Quaternion().setFromRotationMatrix(matrix);
}

export function cubieHasMaskedTopColor(cubie) {
  return Object.values(cubie?.localColors || {}).includes("U");
}
