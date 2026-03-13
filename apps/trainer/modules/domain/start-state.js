import { stateSlotsMetadata, stateStringFromMoves } from "./state.js";

const VALID_FACE_COLORS = new Set(["U", "R", "F", "D", "L", "B"]);
const SIDE_FACES = new Set(["F", "R", "B", "L"]);
const SIDE_ORDER = ["F", "R", "B", "L"];
const CORNER_POSITIONS = [
  [1, 1, 1],
  [1, -1, 1],
  [-1, -1, 1],
  [-1, 1, 1],
];
const EDGE_POSITIONS = [
  [1, 0, 1],
  [0, -1, 1],
  [-1, 0, 1],
  [0, 1, 1],
];
const CENTER_POSITIONS = {
  U: [0, 0, 1],
  R: [0, -1, 0],
  F: [-1, 0, 0],
  D: [0, 0, -1],
  L: [0, 1, 0],
  B: [1, 0, 0],
};
const ROTATIONS = ["x", "x'", "y", "y'", "z", "z'"];

function vecKey(position) {
  return `${position[0]},${position[1]},${position[2]}`;
}

function faceletLookup(state) {
  const normalized = String(state || "");
  if (normalized.length !== 54) {
    throw new Error(`State must contain exactly 54 facelets, got ${normalized.length}`);
  }
  const lookup = new Map();
  stateSlotsMetadata().forEach((slot, index) => {
    const color = normalized[index];
    if (!VALID_FACE_COLORS.has(color)) {
      throw new Error(`Invalid face color: ${String(color)}`);
    }
    lookup.set(`${slot.face}|${vecKey(slot.position)}`, color);
  });
  return lookup;
}

function colorAt(lookup, face, position) {
  return lookup.get(`${face}|${vecKey(position)}`);
}

function validateOllStartState(state) {
  const lookup = faceletLookup(state);
  stateSlotsMetadata().forEach((slot, index) => {
    const [x, y, z] = slot.position;
    const color = colorAt(lookup, slot.face, slot.position);
    if (slot.face === "D" && color !== "D") {
      throw new Error(`Invalid OLL start state at index ${index}`);
    }
    if (SIDE_FACES.has(slot.face) && z !== 1 && color !== slot.face) {
      throw new Error(`Invalid OLL start state at index ${index}`);
    }
  });
}

function centerColors(lookup) {
  return Object.fromEntries(
    Object.entries(CENTER_POSITIONS).map(([face, position]) => [face, colorAt(lookup, face, position)])
  );
}

function validatePllStartState(state) {
  const lookup = faceletLookup(state);
  const centers = centerColors(lookup);
  stateSlotsMetadata().forEach((slot, index) => {
    const [, , z] = slot.position;
    const color = colorAt(lookup, slot.face, slot.position);
    if ((slot.face === "U" || slot.face === "D") && color !== slot.face) {
      throw new Error(`Invalid PLL start state at index ${index}`);
    }
    if (SIDE_FACES.has(slot.face) && z !== 1 && color !== centers[slot.face]) {
      throw new Error(`Invalid PLL start state at index ${index}`);
    }
  });
}

function orientationCorrections() {
  const sequences = [[]];
  const seen = new Set([stateStringFromMoves([])]);
  const queue = [[]];
  while (queue.length && seen.size < 24) {
    const current = queue.shift();
    ROTATIONS.forEach((move) => {
      const candidate = [...current, move];
      const signature = stateStringFromMoves(candidate);
      if (seen.has(signature)) return;
      seen.add(signature);
      sequences.push(candidate);
      queue.push(candidate);
    });
  }
  sequences.sort((left, right) => left.length - right.length);
  return sequences;
}

const CACHED_CORRECTIONS = orientationCorrections();

function resolveByValidator(inverseMoves, validator) {
  for (const correction of CACHED_CORRECTIONS) {
    const state = stateStringFromMoves([...inverseMoves, ...correction]);
    try {
      validator(state);
      return state;
    } catch {}
  }
  for (const correction of CACHED_CORRECTIONS) {
    const state = stateStringFromMoves([...correction, ...inverseMoves]);
    try {
      validator(state);
      return state;
    } catch {}
  }
  return stateStringFromMoves(inverseMoves);
}

export function resolveStartState(group, inverseMoves) {
  const normalized = String(group || "").trim().toUpperCase();
  if (normalized === "OLL") {
    return resolveByValidator(inverseMoves, validateOllStartState);
  }
  if (normalized === "PLL") {
    return resolveByValidator(inverseMoves, validatePllStartState);
  }
  return stateStringFromMoves(inverseMoves);
}

export function balancePllFormulaRotations(formula) {
  const normalized = String(formula || "").trim();
  if (!normalized) return normalized;
  const rotationMoves = normalized.split(/\s+/).filter((move) => {
    const base = move.endsWith("'") || move.endsWith("2") ? move.slice(0, -1) : move;
    return ["x", "y", "z"].includes(base);
  });
  if (!rotationMoves.length) return normalized;
  for (const correction of CACHED_CORRECTIONS) {
    if (stateStringFromMoves([...rotationMoves, ...correction]) === stateStringFromMoves([])) {
      return correction.length ? `${normalized} ${correction.join(" ")}` : normalized;
    }
  }
  return normalized;
}

export function pllTopSideColorMap(state) {
  const lookup = faceletLookup(state);
  const centers = centerColors(lookup);
  return {
    centers,
    corners: CORNER_POSITIONS.map((position) => ({
      position,
      colors: SIDE_ORDER.filter((face) => {
        const [x, y] = position;
        if (face === "F") return x === -1;
        if (face === "B") return x === 1;
        if (face === "R") return y === -1;
        if (face === "L") return y === 1;
        return false;
      }).map((face) => colorAt(lookup, face, position)),
    })),
    edges: EDGE_POSITIONS.map((position) => ({
      position,
      colors: SIDE_ORDER.filter((face) => {
        const [x, y] = position;
        if (face === "F") return x === -1;
        if (face === "B") return x === 1;
        if (face === "R") return y === -1;
        if (face === "L") return y === 1;
        return false;
      }).map((face) => colorAt(lookup, face, position)),
    })),
  };
}
