import {
  DEFAULT_SANDBOX_PLAYBACK_CONFIG,
  FACE_TO_NORMAL,
  NORMAL_TO_FACE,
} from "../core/constants.js";
import {
  moveAxis,
  moveSelector,
  moveTurns,
  normalizeMoveSteps,
  splitMove,
} from "./formula.js";
import { cloneObject } from "../utils/common.js";

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
  return [x, y, z];
}

function buildCubiesFromState(stateString, stateSlots) {
  const cubies = new Map();
  const source = String(stateString || "");

  (stateSlots || []).forEach((slot, idx) => {
    const position = slot?.position;
    const face = String(slot?.face || "");
    if (!Array.isArray(position) || position.length < 3 || !face) return;
    const key = `${position[0]},${position[1]},${position[2]}`;
    const color = source[idx] || face;
    if (!cubies.has(key)) {
      cubies.set(key, {
        pos: [position[0], position[1], position[2]],
        faces: {},
      });
    }
    cubies.get(key).faces[face] = color;
  });

  return cubies;
}

function cubiesToStateString(cubies, stateSlots) {
  return (stateSlots || [])
    .map((slot) => {
      const position = slot?.position;
      const face = String(slot?.face || "");
      if (!Array.isArray(position) || position.length < 3 || !face) return face;
      const key = `${position[0]},${position[1]},${position[2]}`;
      const cubie = cubies.get(key);
      if (!cubie) return face;
      return String(cubie.faces[face] || face);
    })
    .join("");
}

function applyMoveToCubies(cubies, token) {
  const [base, modifier] = splitMove(token);
  const axis = moveAxis(base);
  const selector = moveSelector(base);
  const turns = moveTurns(base, modifier);
  if (!axis || !selector || !Number.isFinite(turns) || turns === 0) {
    return cubies;
  }

  let current = cubies;
  let remaining = Math.abs(turns);
  const direction = turns > 0 ? 1 : -1;

  while (remaining > 0) {
    const next = new Map();
    current.forEach((cubie) => {
      let nextPos = [...cubie.pos];
      let nextFaces = { ...cubie.faces };

      if (selector(cubie.pos)) {
        nextPos = rotateVec(cubie.pos, axis, direction);
        const rotatedFaces = {};
        Object.entries(cubie.faces).forEach(([face, color]) => {
          const normal = FACE_TO_NORMAL[face];
          if (!normal) {
            rotatedFaces[face] = color;
            return;
          }
          const rotated = rotateVec(normal, axis, direction);
          const mappedFace = NORMAL_TO_FACE[rotated.join(",")] || face;
          rotatedFaces[mappedFace] = color;
        });
        nextFaces = rotatedFaces;
      }

      const key = `${nextPos[0]},${nextPos[1]},${nextPos[2]}`;
      next.set(key, {
        pos: nextPos,
        faces: nextFaces,
      });
    });
    current = next;
    remaining -= 1;
  }

  return current;
}

export function normalizeSandboxPlaybackConfig(raw) {
  const config = { ...DEFAULT_SANDBOX_PLAYBACK_CONFIG };
  if (!raw || typeof raw !== "object") return config;
  const runTime = Number(raw.run_time_sec);
  const doubleMultiplier = Number(raw.double_turn_multiplier);
  const pauseRatio = Number(raw.inter_move_pause_ratio);
  const rateFunc = String(raw.rate_func || "").trim();
  if (Number.isFinite(runTime) && runTime > 0) config.run_time_sec = runTime;
  if (Number.isFinite(doubleMultiplier) && doubleMultiplier > 0) config.double_turn_multiplier = doubleMultiplier;
  if (Number.isFinite(pauseRatio) && pauseRatio >= 0) config.inter_move_pause_ratio = pauseRatio;
  if (rateFunc) config.rate_func = rateFunc;
  return config;
}

export function buildLocalSandboxTimeline(baseSandbox, formula, group) {
  const normalizedFormula = normalizeMoveSteps(formula || "");
  const moveSteps = normalizedFormula.steps.map((step) => step.map((move) => String(move)));
  const stateSlots = Array.isArray(baseSandbox?.state_slots) ? cloneObject(baseSandbox.state_slots) : [];
  const initialState = String(baseSandbox?.initial_state || "");
  const playbackConfig = normalizeSandboxPlaybackConfig(baseSandbox?.playback_config);

  let cubies = buildCubiesFromState(initialState, stateSlots);
  const states = [initialState || cubiesToStateString(cubies, stateSlots)];

  moveSteps.forEach((step) => {
    step.forEach((move) => {
      cubies = applyMoveToCubies(cubies, move);
    });
    states.push(cubiesToStateString(cubies, stateSlots));
  });

  return {
    formula: normalizedFormula.formula,
    group: String(group || baseSandbox?.group || ""),
    move_steps: moveSteps,
    moves_flat: normalizedFormula.movesFlat,
    initial_state: states[0] || "",
    states_by_step: states,
    highlight_by_step: normalizedFormula.highlights,
    state_slots: stateSlots,
    playback_config: playbackConfig,
  };
}
