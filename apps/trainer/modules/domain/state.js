import { moveAxis, moveSelector, moveTurns, normalizeMoveSteps, splitMove } from "./formula.js";

const FACE_ORDER = "URFDLB";
const NORMAL_TO_FACE = new Map([
  ["0,0,1", "U"],
  ["0,-1,0", "R"],
  ["-1,0,0", "F"],
  ["0,0,-1", "D"],
  ["0,1,0", "L"],
  ["1,0,0", "B"],
]);

const FACE_TO_NORMAL = {
  U: [0, 0, 1],
  R: [0, -1, 0],
  F: [-1, 0, 0],
  D: [0, 0, -1],
  L: [0, 1, 0],
  B: [1, 0, 0],
};

class Sticker {
  constructor(position, normal, color) {
    this.position = [...position];
    this.normal = [...normal];
    this.color = String(color || "");
  }
}

function vecKey(vec) {
  return `${Number(vec[0] || 0)},${Number(vec[1] || 0)},${Number(vec[2] || 0)}`;
}

function rotateVec(vec, axis, direction) {
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
  throw new Error(`Unsupported axis: ${String(axis)}`);
}

function solvedStickers() {
  const stickers = [];
  [-1, 0, 1].forEach((x) => {
    [-1, 0, 1].forEach((y) => {
      [-1, 0, 1].forEach((z) => {
        const position = [x, y, z];
        if (z === 1) stickers.push(new Sticker(position, [0, 0, 1], "U"));
        if (z === -1) stickers.push(new Sticker(position, [0, 0, -1], "D"));
        if (y === -1) stickers.push(new Sticker(position, [0, -1, 0], "R"));
        if (y === 1) stickers.push(new Sticker(position, [0, 1, 0], "L"));
        if (x === -1) stickers.push(new Sticker(position, [-1, 0, 0], "F"));
        if (x === 1) stickers.push(new Sticker(position, [1, 0, 0], "B"));
      });
    });
  });
  return stickers;
}

function cubeIndex() {
  const cube = [];
  for (let x = 0; x < 3; x += 1) {
    cube[x] = [];
    for (let y = 0; y < 3; y += 1) {
      cube[x][y] = [];
      for (let z = 0; z < 3; z += 1) {
        cube[x][y][z] = [x - 1, y - 1, z - 1];
      }
    }
  }
  return cube;
}

function flip(matrix, axes) {
  let next = matrix.map((row) => [...row]);
  if (axes.includes(0)) next = [...next].reverse();
  if (axes.includes(1)) next = next.map((row) => [...row].reverse());
  return next;
}

function rot90(matrix, k = 1) {
  let next = matrix.map((row) => [...row]);
  const turns = ((k % 4) + 4) % 4;
  for (let index = 0; index < turns; index += 1) {
    next = next[0].map((_, col) => next.map((row) => row[col]).reverse());
  }
  return next;
}

function flatten(matrix) {
  return matrix.flat();
}

function stateSlots() {
  const cube = cubeIndex();
  const sliceXY = (zIndex) => [[cube[0][0][zIndex], cube[0][1][zIndex], cube[0][2][zIndex]], [cube[1][0][zIndex], cube[1][1][zIndex], cube[1][2][zIndex]], [cube[2][0][zIndex], cube[2][1][zIndex], cube[2][2][zIndex]]];
  const sliceXZ = (yIndex) => [[cube[0][yIndex][0], cube[0][yIndex][1], cube[0][yIndex][2]], [cube[1][yIndex][0], cube[1][yIndex][1], cube[1][yIndex][2]], [cube[2][yIndex][0], cube[2][yIndex][1], cube[2][yIndex][2]]];
  const sliceYZ = (xIndex) => [[cube[xIndex][0][0], cube[xIndex][0][1], cube[xIndex][0][2]], [cube[xIndex][1][0], cube[xIndex][1][1], cube[xIndex][1][2]], [cube[xIndex][2][0], cube[xIndex][2][1], cube[xIndex][2][2]]];

  return [
    ...flatten(rot90(sliceXY(2), 2)).map((position) => ({ position, face: "U" })),
    ...flatten(rot90(flip(sliceXZ(0), [0, 1]), -1)).map((position) => ({ position, face: "R" })),
    ...flatten(rot90(flip(sliceYZ(0), [0]))).map((position) => ({ position, face: "F" })),
    ...flatten(rot90(flip(sliceXY(0), [0]), 2)).map((position) => ({ position, face: "D" })),
    ...flatten(rot90(flip(sliceXZ(2), [0]))).map((position) => ({ position, face: "L" })),
    ...flatten(rot90(flip(sliceYZ(2), [0, 1]), -1)).map((position) => ({ position, face: "B" })),
  ];
}

let cachedSlots = null;

export function stateSlotsMetadata() {
  if (!cachedSlots) {
    cachedSlots = stateSlots();
  }
  return cachedSlots.map((slot) => ({
    position: [...slot.position],
    face: slot.face,
  }));
}

export function solvedStateString() {
  return FACE_ORDER.split("").map((face) => face.repeat(9)).join("");
}

function stickersFromState(state) {
  const normalized = String(state || "");
  if (normalized.length !== 54) {
    throw new Error(`State must contain exactly 54 facelets, got ${normalized.length}`);
  }
  return stateSlotsMetadata().map((slot, index) => new Sticker(slot.position, FACE_TO_NORMAL[slot.face], normalized[index]));
}

function applyMove(stickers, move) {
  const [base, modifier] = splitMove(move);
  const axis = moveAxis(base);
  const selector = moveSelector(base);
  const turns = moveTurns(base, modifier);
  const steps = Math.abs(turns);
  const direction = turns > 0 ? 1 : -1;
  for (let step = 0; step < steps; step += 1) {
    stickers.forEach((sticker) => {
      if (!selector(sticker.position)) return;
      sticker.position = rotateVec(sticker.position, axis, direction);
      sticker.normal = rotateVec(sticker.normal, axis, direction);
    });
  }
}

function stateStringFromStickers(stickers) {
  const lookup = new Map();
  stickers.forEach((sticker) => {
    const face = NORMAL_TO_FACE.get(vecKey(sticker.normal));
    lookup.set(`${vecKey(sticker.position)}|${face}`, sticker.color);
  });
  return stateSlotsMetadata()
    .map((slot) => lookup.get(`${vecKey(slot.position)}|${slot.face}`) || slot.face)
    .join("");
}

export function stateStringFromMoves(moves) {
  const stickers = solvedStickers();
  (moves || []).forEach((move) => applyMove(stickers, move));
  return stateStringFromStickers(stickers);
}

export function stateStringAfterMoves(state, moves) {
  const stickers = stickersFromState(state);
  (moves || []).forEach((move) => applyMove(stickers, move));
  return stateStringFromStickers(stickers);
}

export function invertMoves(formula) {
  const normalized = normalizeMoveSteps(formula || "");
  return [...normalized.steps]
    .reverse()
    .flatMap((step) => [...step].reverse().map((move) => {
      if (move.endsWith("'")) return move.slice(0, -1);
      if (move.endsWith("2")) return move;
      return `${move}'`;
    }));
}
