import { DEFAULT_SANDBOX_PLAYBACK_CONFIG } from "../core/constants.js";
import {
  inferCubeSizeFromStateSlots,
} from "../cube-core/model.js";
import { normalizeMoveSteps } from "./formula.js";
import { resolveStartState } from "./start-state.js";
import { invertMoves, stateSlotsMetadata, stateStringAfterMoves } from "./state.js";
import { cloneObject } from "../utils/common.js";

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
  const stateSlots = stateSlotsMetadata();
  const playbackConfig = normalizeSandboxPlaybackConfig(baseSandbox?.playback_config);
  const cubeSize = Number(baseSandbox?.cube_size) || inferCubeSizeFromStateSlots(stateSlots);
  const initialState = resolveStartState(group, invertMoves(normalizedFormula.formula));
  const states = [initialState];
  let currentState = initialState;
  moveSteps.forEach((step) => {
    currentState = stateStringAfterMoves(currentState, step);
    states.push(currentState);
  });

  return {
    formula: normalizedFormula.formula,
    group: String(group || baseSandbox?.group || ""),
    cube_size: cubeSize,
    move_steps: moveSteps,
    moves_flat: normalizedFormula.movesFlat,
    initial_state: initialState,
    states_by_step: states,
    final_state: states[states.length - 1] || initialState,
    highlight_by_step: normalizedFormula.highlights,
    state_slots: cloneObject(stateSlots),
    playback_config: playbackConfig,
  };
}
