import { FACE_TO_NORMAL, NORMAL_TO_FACE } from "../core/constants.js";
import { moveAxis, moveTurns, splitMove } from "../domain/formula.js";

const EPSILON = 1e-6;
const AXES = ["x", "y", "z"];
const ALL_FACES = ["U", "D", "R", "L", "F", "B"];

function roundCoord(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return 0;
  const rounded = Math.round(numeric * 1000) / 1000;
  return Object.is(rounded, -0) ? 0 : rounded;
}

function coordsKey(position) {
  return position.map((value) => String(roundCoord(value))).join(",");
}

function cloneVec(vec) {
  return [Number(vec[0] || 0), Number(vec[1] || 0), Number(vec[2] || 0)];
}

function cloneOrientation(orientation) {
  const next = {};
  ALL_FACES.forEach((face) => {
    next[face] = cloneVec(orientation?.[face] || FACE_TO_NORMAL[face] || [0, 0, 0]);
  });
  return next;
}

function cloneCubie(cubie) {
  return {
    id: String(cubie.id || ""),
    pos: cloneVec(cubie.pos || [0, 0, 0]),
    localColors: { ...(cubie.localColors || {}) },
    orientation: cloneOrientation(cubie.orientation || {}),
  };
}

export function createCoordinateValues(size) {
  const numeric = Number(size || 3);
  if (!Number.isInteger(numeric) || numeric < 2) {
    throw new Error(`Unsupported cube size: ${String(size)}`);
  }
  const values = [];
  if (numeric % 2 === 1) {
    const max = (numeric - 1) / 2;
    for (let value = -max; value <= max; value += 1) {
      values.push(value);
    }
    return values;
  }

  const half = numeric / 2;
  for (let idx = 0; idx < numeric; idx += 1) {
    values.push(-half + 0.5 + idx);
  }
  return values;
}

export function inferCubeSizeFromStateSlots(stateSlots) {
  const xs = new Set();
  const ys = new Set();
  const zs = new Set();
  (stateSlots || []).forEach((slot) => {
    const position = Array.isArray(slot?.position) ? slot.position : null;
    if (!position || position.length < 3) return;
    xs.add(roundCoord(position[0]));
    ys.add(roundCoord(position[1]));
    zs.add(roundCoord(position[2]));
  });
  const size = Math.max(xs.size, ys.size, zs.size, 3);
  return size || 3;
}

export function createSurfaceStateSlots(size) {
  const coords = createCoordinateValues(size);
  const min = coords[0];
  const max = coords[coords.length - 1];
  const slots = [];

  coords.forEach((x) => {
    coords.forEach((y) => {
      coords.forEach((z) => {
        if (Math.abs(z - max) < EPSILON) slots.push({ position: [x, y, z], face: "U" });
        if (Math.abs(z - min) < EPSILON) slots.push({ position: [x, y, z], face: "D" });
        if (Math.abs(y - min) < EPSILON) slots.push({ position: [x, y, z], face: "R" });
        if (Math.abs(y - max) < EPSILON) slots.push({ position: [x, y, z], face: "L" });
        if (Math.abs(x - min) < EPSILON) slots.push({ position: [x, y, z], face: "F" });
        if (Math.abs(x - max) < EPSILON) slots.push({ position: [x, y, z], face: "B" });
      });
    });
  });

  return slots;
}

export function stateToWorldVector(vec) {
  const x = Number(vec[0] || 0);
  const y = Number(vec[1] || 0);
  const z = Number(vec[2] || 0);
  return [-y, z, -x];
}

export function worldToStateVector(vec) {
  const x = Number(vec[0] || 0);
  const y = Number(vec[1] || 0);
  const z = Number(vec[2] || 0);
  return [-z, -x, y];
}

function eqCoord(a, b) {
  return Math.abs(Number(a || 0) - Number(b || 0)) < EPSILON;
}

function containsCoord(coords, target) {
  return coords.some((value) => eqCoord(value, target));
}

export function createMoveSelector(base, size) {
  const coords = createCoordinateValues(size);
  const min = coords[0];
  const max = coords[coords.length - 1];
  const innerMin = coords[1] ?? min;
  const innerMax = coords[coords.length - 2] ?? max;
  const hasMiddle = containsCoord(coords, 0);

  const selectors = {
    F: (p) => eqCoord(p[0], min),
    B: (p) => eqCoord(p[0], max),
    S: hasMiddle ? (p) => eqCoord(p[0], 0) : null,
    f: (p) => eqCoord(p[0], min) || eqCoord(p[0], innerMin),
    b: (p) => eqCoord(p[0], innerMax) || eqCoord(p[0], max),
    U: (p) => eqCoord(p[2], max),
    D: (p) => eqCoord(p[2], min),
    E: hasMiddle ? (p) => eqCoord(p[2], 0) : null,
    u: (p) => eqCoord(p[2], innerMax) || eqCoord(p[2], max),
    d: (p) => eqCoord(p[2], min) || eqCoord(p[2], innerMin),
    L: (p) => eqCoord(p[1], max),
    R: (p) => eqCoord(p[1], min),
    M: hasMiddle ? (p) => eqCoord(p[1], 0) : null,
    l: (p) => eqCoord(p[1], innerMax) || eqCoord(p[1], max),
    r: (p) => eqCoord(p[1], min) || eqCoord(p[1], innerMin),
    x: () => true,
    y: () => true,
    z: () => true,
  };

  return selectors[base] || null;
}

function rotateQuarter(vec, axis, direction) {
  const [x, y, z] = vec;
  if (axis === "x") {
    return direction > 0 ? [x, -z, y] : [x, z, -y];
  }
  if (axis === "y") {
    return direction > 0 ? [z, y, -x] : [-z, y, x];
  }
  if (axis === "z") {
    return direction > 0 ? [-y, x, z] : [y, -x, z];
  }
  return [x, y, z];
}

function rotateDiscrete(vec, axis, turns) {
  let current = cloneVec(vec);
  let remaining = Math.abs(Number(turns || 0));
  const direction = Number(turns || 0) >= 0 ? 1 : -1;
  while (remaining > 0) {
    current = rotateQuarter(current, axis, direction);
    remaining -= 1;
  }
  return current.map(roundCoord);
}

function rotateContinuous(vec, axis, angle) {
  const [x, y, z] = vec;
  const sin = Math.sin(angle);
  const cos = Math.cos(angle);
  if (axis === "x") {
    return [x, (y * cos) - (z * sin), (y * sin) + (z * cos)].map(roundCoord);
  }
  if (axis === "y") {
    return [(x * cos) + (z * sin), y, (-x * sin) + (z * cos)].map(roundCoord);
  }
  if (axis === "z") {
    return [(x * cos) - (y * sin), (x * sin) + (y * cos), z].map(roundCoord);
  }
  return cloneVec(vec).map(roundCoord);
}

function rotateOrientationDiscrete(orientation, axis, turns) {
  const next = {};
  ALL_FACES.forEach((face) => {
    next[face] = rotateDiscrete(orientation?.[face] || FACE_TO_NORMAL[face], axis, turns);
  });
  return next;
}

function rotateOrientationContinuous(orientation, axis, angle) {
  const next = {};
  ALL_FACES.forEach((face) => {
    next[face] = rotateContinuous(orientation?.[face] || FACE_TO_NORMAL[face], axis, angle);
  });
  return next;
}

function positionKey(position) {
  return coordsKey(position);
}

function findCubieAtPosition(model, position) {
  const key = positionKey(position);
  return model.cubies.find((cubie) => positionKey(cubie.pos) === key) || null;
}

function localFaceForStateFace(cubie, outwardFace) {
  const target = FACE_TO_NORMAL[outwardFace];
  if (!target) return "";
  for (const face of ALL_FACES) {
    const normal = cubie.orientation?.[face];
    if (!normal) continue;
    if (eqCoord(normal[0], target[0]) && eqCoord(normal[1], target[1]) && eqCoord(normal[2], target[2])) {
      return face;
    }
  }
  return "";
}

export function modelToStateString(model) {
  const slots = Array.isArray(model.stateSlots) ? model.stateSlots : [];
  return slots
    .map((slot) => {
      const position = Array.isArray(slot?.position) ? slot.position : null;
      const face = String(slot?.face || "");
      if (!position || !face) return face || "";
      const cubie = findCubieAtPosition(model, position);
      if (!cubie) return face;
      const localFace = localFaceForStateFace(cubie, face);
      return String(cubie.localColors?.[localFace] || face);
    })
    .join("");
}

export function createCubeModel(size, stateString, stateSlots) {
  const resolvedSize = Math.max(3, Number(size || inferCubeSizeFromStateSlots(stateSlots)) || 3);
  const resolvedSlots = Array.isArray(stateSlots) && stateSlots.length ? stateSlots : createSurfaceStateSlots(resolvedSize);
  const source = String(stateString || "");
  const cubies = new Map();

  resolvedSlots.forEach((slot, index) => {
    const position = Array.isArray(slot?.position) ? slot.position.map(roundCoord) : null;
    const face = String(slot?.face || "");
    if (!position || position.length < 3 || !face) return;
    const key = positionKey(position);
    if (!cubies.has(key)) {
      cubies.set(key, {
        id: key,
        pos: position,
        localColors: {},
        orientation: cloneOrientation(),
      });
    }
    const cubie = cubies.get(key);
    cubie.localColors[face] = source[index] || face;
  });

  return {
    size: resolvedSize,
    coords: createCoordinateValues(resolvedSize),
    stateSlots: resolvedSlots.map((slot) => ({
      position: Array.isArray(slot?.position) ? slot.position.map(roundCoord) : [0, 0, 0],
      face: String(slot?.face || ""),
    })),
    cubies: Array.from(cubies.values()).map(cloneCubie),
  };
}

export function cloneCubeModel(model) {
  return {
    size: Number(model?.size || 3),
    coords: Array.isArray(model?.coords) ? [...model.coords] : createCoordinateValues(Number(model?.size || 3)),
    stateSlots: Array.isArray(model?.stateSlots)
      ? model.stateSlots.map((slot) => ({
        position: Array.isArray(slot?.position) ? slot.position.map(roundCoord) : [0, 0, 0],
        face: String(slot?.face || ""),
      }))
      : [],
    cubies: Array.isArray(model?.cubies) ? model.cubies.map(cloneCubie) : [],
  };
}

export function parseCoreMove(move, size) {
  const token = String(move || "").trim();
  if (!token) return null;
  const [base, modifier] = splitMove(token);
  const axis = moveAxis(base);
  const selector = createMoveSelector(base, size);
  const turns = moveTurns(base, modifier);
  if (!axis || !selector || !Number.isFinite(turns) || turns === 0) {
    return null;
  }
  return { token, base, axis, turns, selector };
}

export function applyMove(model, move) {
  const next = cloneCubeModel(model);
  const parsed = parseCoreMove(move, next.size);
  if (!parsed) return next;

  next.cubies = next.cubies.map((cubie) => {
    if (!parsed.selector(cubie.pos)) return cubie;
    return {
      ...cubie,
      pos: rotateDiscrete(cubie.pos, parsed.axis, parsed.turns),
      orientation: rotateOrientationDiscrete(cubie.orientation, parsed.axis, parsed.turns),
    };
  });

  return next;
}

export function applyStep(model, stepMoves) {
  const moves = Array.isArray(stepMoves) ? stepMoves : [];
  return moves.reduce((current, move) => applyMove(current, move), cloneCubeModel(model));
}

function buildCubieSnapshot(cubie, statePos, orientation, progress) {
  const worldNormalsByLocalFace = {};
  ALL_FACES.forEach((face) => {
    worldNormalsByLocalFace[face] = stateToWorldVector(orientation[face] || FACE_TO_NORMAL[face]).map(roundCoord);
  });
  return {
    id: cubie.id,
    statePos: statePos.map(roundCoord),
    worldPos: stateToWorldVector(statePos).map(roundCoord),
    localColors: { ...(cubie.localColors || {}) },
    worldNormalsByLocalFace,
    progress: clamp01(progress),
  };
}

function clamp01(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return 0;
  if (numeric <= 0) return 0;
  if (numeric >= 1) return 1;
  return numeric;
}

function resolveStepTransition(model, stepMoves) {
  const moves = Array.isArray(stepMoves) ? stepMoves : [];
  const parsedMoves = moves
    .map((move) => parseCoreMove(move, model.size))
    .filter(Boolean);
  if (!parsedMoves.length) {
    return { axis: "", turnsByCubieId: new Map() };
  }

  const axis = parsedMoves[0].axis;
  const turnsByCubieId = new Map();
  parsedMoves.forEach((parsed) => {
    model.cubies.forEach((cubie) => {
      if (!parsed.selector(cubie.pos)) return;
      turnsByCubieId.set(cubie.id, parsed.turns);
    });
  });

  return { axis, turnsByCubieId };
}

export function snapshotForState(model) {
  const source = cloneCubeModel(model);
  return {
    size: source.size,
    cubies: source.cubies.map((cubie) => buildCubieSnapshot(cubie, cubie.pos, cubie.orientation, 0)),
  };
}

export function interpolateStep(model, stepMoves, progress, options = {}) {
  const source = cloneCubeModel(model);
  const clamped = clamp01(progress);
  if (clamped <= 0) {
    return snapshotForState(source);
  }
  if (clamped >= 1) {
    return snapshotForState(applyStep(source, stepMoves));
  }

  const { axis, turnsByCubieId } = resolveStepTransition(source, stepMoves);
  const easing = typeof options.easing === "function" ? options.easing : (value) => value;
  const eased = clamp01(easing(clamped));

  return {
    size: source.size,
    cubies: source.cubies.map((cubie) => {
      const turns = turnsByCubieId.get(cubie.id);
      if (!turns || !axis) {
        return buildCubieSnapshot(cubie, cubie.pos, cubie.orientation, eased);
      }
      const angle = (turns * Math.PI / 2) * eased;
      const nextPos = rotateContinuous(cubie.pos, axis, angle);
      const nextOrientation = rotateOrientationContinuous(cubie.orientation, axis, angle);
      return buildCubieSnapshot(cubie, nextPos, nextOrientation, eased);
    }),
  };
}

export function snapshotsForTimeline(initialModel, moveSteps) {
  const models = [cloneCubeModel(initialModel)];
  const snapshots = [snapshotForState(initialModel)];
  let current = cloneCubeModel(initialModel);
  (moveSteps || []).forEach((step) => {
    current = applyStep(current, step);
    models.push(current);
    snapshots.push(snapshotForState(current));
  });
  return { models, snapshots };
}

export function createRendererTransitionFrames(model, stepMoves, fractions, options = {}) {
  return (fractions || []).map((fraction) => interpolateStep(model, stepMoves, fraction, options));
}

export function outwardFacesForCubie(cubie) {
  const faces = {};
  ALL_FACES.forEach((outwardFace) => {
    const localFace = localFaceForStateFace(cubie, outwardFace);
    if (!localFace) return;
    faces[outwardFace] = cubie.localColors?.[localFace] || outwardFace;
  });
  return faces;
}
