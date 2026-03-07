import { DEFAULT_SANDBOX_PLAYBACK_CONFIG } from "../core/constants.js";
import {
  applyStep,
  createCubeModel,
  inferCubeSizeFromStateSlots,
  modelToStateString,
  snapshotsForTimeline,
} from "../cube-core/model.js";
import { normalizeMoveSteps } from "./formula.js";
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
  const stateSlots = Array.isArray(baseSandbox?.state_slots) ? cloneObject(baseSandbox.state_slots) : [];
  const playbackConfig = normalizeSandboxPlaybackConfig(baseSandbox?.playback_config);
  const cubeSize = Number(baseSandbox?.cube_size) || inferCubeSizeFromStateSlots(stateSlots);
  const initialModel = createCubeModel(cubeSize, String(baseSandbox?.initial_state || ""), stateSlots);
  const { models } = snapshotsForTimeline(initialModel, moveSteps);
  const states = models.map((model) => modelToStateString(model));
  const finalModel = moveSteps.reduce((model, step) => applyStep(model, step), initialModel);

  return {
    formula: normalizedFormula.formula,
    group: String(group || baseSandbox?.group || ""),
    cube_size: cubeSize,
    move_steps: moveSteps,
    moves_flat: normalizedFormula.movesFlat,
    initial_state: states[0] || "",
    states_by_step: states,
    final_state: modelToStateString(finalModel),
    highlight_by_step: normalizedFormula.highlights,
    state_slots: stateSlots,
    playback_config: playbackConfig,
  };
}
