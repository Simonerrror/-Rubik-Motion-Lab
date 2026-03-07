import {
  DEFAULT_SANDBOX_PLAYBACK_CONFIG,
  SANDBOX_PLAYBACK_SPEEDS,
  SANDBOX_RESTART_DELAY_MS,
} from "../core/constants.js";
import {
  createCubeModel,
  inferCubeSizeFromStateSlots,
  interpolateStep,
  snapshotForState,
  snapshotsForTimeline,
} from "../cube-core/model.js";
import { normalizeSandboxPlaybackConfig } from "../domain/timeline-builder.js";
import { clamp } from "../utils/common.js";

const PLAY_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><polygon class="fill-icon" points="8,6 18,12 8,18"></polygon></svg>';
const PAUSE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6V18"></path><path d="M15 6V18"></path></svg>';

function easeInOutSine(t) {
  return 0.5 - (0.5 * Math.cos(Math.PI * t));
}

function resolveEasing(name) {
  if (String(name || "").trim() === "ease_in_out_sine") {
    return easeInOutSine;
  }
  return easeInOutSine;
}

/**
 * @param {Object} deps
 */
export function createSandboxController(deps) {
  const { state, dom, store, onRenderActiveAlgorithmDisplay, onUpdateActiveAlgorithmStepHighlight } = deps;

  function sandboxState() {
    return store.getState();
  }

  function syncLegacyState() {
    const sandbox = sandboxState();
    state.sandboxStore = store;
    state.sandboxData = sandbox.activeTimeline;
    state.sandboxStepIndex = sandbox.cursorStepIndex;
    state.sandboxTimelineProgress = sandbox.timelineProgress;
    state.sandboxCursorStepIndex = sandbox.cursorStepIndex;
    state.sandboxCursorStepProgress = sandbox.cursorStepProgress;
    state.sandboxTimelineRafPending = sandbox.timelineRafPending;
    state.sandboxPendingTimelineProgress = sandbox.pendingTimelineProgress;
    state.sandboxPlaybackConfig = sandbox.playbackConfig;
    state.sandboxPlaybackSpeed = sandbox.playbackSpeed;
    state.sandboxMachineState = sandbox.playbackMode.toUpperCase();
    state.sandboxWasPlayingBeforeScrub = sandbox.wasPlayingBeforeScrub;
    state.sandboxPlaybackToken = sandbox.playbackToken;
  }

  function currentTimeline() {
    return sandboxState().activeTimeline;
  }

  function currentSandboxStepCount() {
    const steps = currentTimeline()?.move_steps;
    return Array.isArray(steps) ? steps.length : 0;
  }

  function formatPlaybackSpeed(value) {
    const numeric = Number(value);
    return Number.isInteger(numeric) ? `×${numeric}` : `×${numeric.toFixed(1)}`;
  }

  function isPlaying() {
    return sandboxState().playbackMode === "playing";
  }

  function isStepping() {
    return sandboxState().playbackMode === "stepping";
  }

  function isScrubbing() {
    return sandboxState().playbackMode === "scrubbing";
  }

  function isTransportLocked() {
    return isStepping() || isScrubbing();
  }

  function normalizeTimelineProgress(rawProgress) {
    const total = currentSandboxStepCount();
    const numeric = Number(rawProgress);
    if (!Number.isFinite(numeric)) return 0;
    return clamp(numeric, 0, total);
  }

  function timelineCurrentStepForHighlight() {
    const sandbox = sandboxState();
    const total = currentSandboxStepCount();
    if (sandbox.cursorStepIndex < total && sandbox.cursorStepProgress > 0) {
      return sandbox.cursorStepIndex;
    }
    return -1;
  }

  function updateTimelineDisplay() {
    const total = currentSandboxStepCount();
    if (dom.sandboxTimelineSlider) {
      dom.sandboxTimelineSlider.max = String(total);
      dom.sandboxTimelineSlider.value = String(normalizeTimelineProgress(sandboxState().timelineProgress));
    }
  }

  function updateActiveAlgorithmStepHighlight() {
    onUpdateActiveAlgorithmStepHighlight(timelineCurrentStepForHighlight());
  }

  function updateSandboxControls() {
    const sandbox = sandboxState();
    const hasTimeline = Boolean(sandbox.activeTimeline);
    const total = currentSandboxStepCount();
    const progress = normalizeTimelineProgress(sandbox.timelineProgress);
    const atStart = progress <= 0.000001;
    const atEnd = progress >= total - 0.000001;
    const locked = isTransportLocked();

    if (dom.sandboxToStartBtn) {
      dom.sandboxToStartBtn.disabled = !hasTimeline || atStart || locked;
      dom.sandboxToStartBtn.title = "Reset to start";
      dom.sandboxToStartBtn.setAttribute("aria-label", "Reset to start");
    }
    if (dom.sandboxPrevBtn) {
      dom.sandboxPrevBtn.disabled = !hasTimeline || atStart || locked;
      dom.sandboxPrevBtn.title = "Step back";
      dom.sandboxPrevBtn.setAttribute("aria-label", "Step back");
    }
    if (dom.sandboxPlayPauseBtn) {
      dom.sandboxPlayPauseBtn.disabled = !hasTimeline || total === 0;
      dom.sandboxPlayPauseBtn.innerHTML = isPlaying() ? PAUSE_ICON : PLAY_ICON;
      dom.sandboxPlayPauseBtn.title = isPlaying() ? "Pause" : "Play";
      dom.sandboxPlayPauseBtn.setAttribute("aria-label", isPlaying() ? "Pause" : "Play");
    }
    if (dom.sandboxNextBtn) {
      dom.sandboxNextBtn.disabled = !hasTimeline || atEnd || locked;
      dom.sandboxNextBtn.title = "Step forward";
      dom.sandboxNextBtn.setAttribute("aria-label", "Step forward");
    }
    if (dom.sandboxSpeedToggleBtn) {
      dom.sandboxSpeedToggleBtn.disabled = !hasTimeline || total === 0;
      const label = formatPlaybackSpeed(sandbox.playbackSpeed);
      dom.sandboxSpeedToggleBtn.textContent = label;
      dom.sandboxSpeedToggleBtn.title = `Playback speed ${label}`;
      dom.sandboxSpeedToggleBtn.setAttribute("aria-label", `Playback speed ${label}`);
    }
    if (dom.sandboxTimelineSlider) {
      dom.sandboxTimelineSlider.disabled = !hasTimeline || total === 0;
    }

    updateTimelineDisplay();
    updateActiveAlgorithmStepHighlight();
  }

  function getModelAtStep(stepIndex) {
    return sandboxState().timelineModels?.[stepIndex] || null;
  }

  function getSnapshotAtStep(stepIndex) {
    return sandboxState().timelineSnapshots?.[stepIndex] || null;
  }

  function resolveSnapshotForProgress(progress) {
    const sandbox = sandboxState();
    const timeline = sandbox.activeTimeline;
    if (!timeline) return null;
    const total = currentSandboxStepCount();
    const clamped = normalizeTimelineProgress(progress);
    const stepIndex = Math.min(Math.floor(clamped), total);
    const stepProgress = stepIndex >= total ? 0 : clamp(clamped - stepIndex, 0, 0.999999);
    if (stepProgress <= 0 || stepIndex >= total) {
      return getSnapshotAtStep(stepIndex);
    }
    const model = getModelAtStep(stepIndex);
    const stepMoves = Array.isArray(timeline.move_steps?.[stepIndex]) ? timeline.move_steps[stepIndex] : [];
    return interpolateStep(model, stepMoves, stepProgress, {
      easing: resolveEasing(sandbox.playbackConfig?.rate_func),
    });
  }

  function renderSandboxProgress(options = {}) {
    const timeline = currentTimeline();
    if (!timeline) {
      store.dispatch({ type: "SET_PROGRESS", progress: 0 });
      updateTimelineDisplay();
      updateActiveAlgorithmStepHighlight();
      return false;
    }

    const progress = options.progress != null ? options.progress : sandboxState().timelineProgress;
    store.dispatch({ type: "SET_PROGRESS", progress });
    const snapshot = resolveSnapshotForProgress(store.getState().timelineProgress);
    if (state.sandboxPlayer && snapshot) {
      state.sandboxPlayer.renderSnapshot(snapshot);
    }
    updateSandboxControls();
    return Boolean(snapshot);
  }

  function setPlaybackSpeed(rawSpeed) {
    store.dispatch({ type: "SET_SPEED", speed: rawSpeed });
    updateSandboxControls();
  }

  function cyclePlaybackSpeed() {
    const current = Number(sandboxState().playbackSpeed);
    const currentIndex = Math.max(0, SANDBOX_PLAYBACK_SPEEDS.indexOf(current));
    const next = SANDBOX_PLAYBACK_SPEEDS[(currentIndex + 1) % SANDBOX_PLAYBACK_SPEEDS.length] || 1;
    setPlaybackSpeed(next);
  }

  function isDoubleTurnMove(move) {
    return /2'?$/.test(String(move || "").trim());
  }

  function sandboxStepDurationMs(stepMoves) {
    const sandbox = sandboxState();
    const cfg = sandbox.playbackConfig || DEFAULT_SANDBOX_PLAYBACK_CONFIG;
    const speed = sandbox.playbackSpeed || 1;
    const step = Array.isArray(stepMoves) ? stepMoves : [];
    const allDoubleTurns = step.length > 0 && step.every(isDoubleTurnMove);
    const runTimeSec = allDoubleTurns ? cfg.run_time_sec * cfg.double_turn_multiplier : cfg.run_time_sec;
    return Math.max(80, Math.round((runTimeSec * 1000) / speed));
  }

  function manualStepDurationMs(stepMoves) {
    return Math.max(110, Math.round(sandboxStepDurationMs(stepMoves) * 0.42));
  }

  function sandboxInterMovePauseMs() {
    const sandbox = sandboxState();
    const cfg = sandbox.playbackConfig || DEFAULT_SANDBOX_PLAYBACK_CONFIG;
    const speed = sandbox.playbackSpeed || 1;
    const pauseSec = (cfg.run_time_sec * cfg.inter_move_pause_ratio) / speed;
    return Math.max(0, Math.round(pauseSec * 1000));
  }

  function sleepWithToken(delayMs, token) {
    const ms = Math.max(0, Math.round(delayMs));
    if (!ms) return Promise.resolve(sandboxState().playbackToken === token);
    return new Promise((resolve) => {
      window.setTimeout(() => {
        resolve(sandboxState().playbackToken === token);
      }, ms);
    });
  }

  function clearActionQueue() {
    store.dispatch({ type: "CLEAR_ACTION_QUEUE" });
  }

  async function flushActionQueue() {
    if (isStepping() || isScrubbing() || isPlaying()) return;
    const nextAction = sandboxState().pendingActionQueue[0];
    if (!nextAction) return;
    store.dispatch({ type: "SHIFT_ACTION" });
    if (nextAction === "next") {
      await moveBy(1, { animate: true, resumePlaying: false, durationMs: manualStepDurationMs(currentTimeline()?.move_steps?.[sandboxState().cursorStepIndex] || []) });
      return;
    }
    if (nextAction === "prev") {
      const targetStep = Math.max(0, sandboxState().cursorStepProgress > 0 ? sandboxState().cursorStepIndex : sandboxState().cursorStepIndex - 1);
      const stepMoves = currentTimeline()?.move_steps?.[targetStep] || [];
      await moveBy(-1, { animate: true, resumePlaying: false, durationMs: manualStepDurationMs(stepMoves) });
    }
  }

  function enqueueAction(kind) {
    store.dispatch({ type: "ENQUEUE_ACTION", payload: kind });
  }

  function cancelRendererAnimation() {
    state.sandboxPlayer?.cancelTransition?.();
  }

  function stopPlayback(options = {}) {
    const hadPlayback = isPlaying() || isStepping();
    cancelRendererAnimation();
    store.dispatch({ type: "BUMP_TOKEN" });
    store.dispatch({ type: "SET_PLAYBACK_MODE", mode: "idle" });
    if (!options.preserveQueue) {
      clearActionQueue();
    }
    if (!options.silent && (hadPlayback || options.forceUpdate)) {
      renderSandboxProgress({ progress: sandboxState().timelineProgress });
    }
  }

  function hardResetOnSwitch(options = {}) {
    stopPlayback({ silent: true, forceUpdate: true });
    store.dispatch({ type: "RESET" });
    if (state.sandboxPlayer) {
      state.sandboxPlayer.setFaceColors?.(null);
      state.sandboxPlayer.setStickerlessTopMask?.(false);
      state.sandboxPlayer.buildScene?.(3);
    }
    syncLegacyState();
    updateSandboxControls();
  }

  async function moveBy(delta, options = {}) {
    const sandbox = sandboxState();
    const timeline = sandbox.activeTimeline;
    if (!timeline) return false;
    if (isScrubbing()) return false;
    if (isStepping()) {
      if (delta > 0) enqueueAction("next");
      if (delta < 0) enqueueAction("prev");
      return false;
    }

    const total = currentSandboxStepCount();
    if (total <= 0) return false;
    const animate = options.animate !== false;
    const resumePlaying = Boolean(options.resumePlaying);
    const progress = sandbox.timelineProgress;

    let fromProgress = progress;
    let toProgress = progress;
    let stepIndex = sandbox.cursorStepIndex;
    let stepMoves = [];
    let model = null;

    if (delta < 0) {
      if (progress <= 0.000001) return false;
      if (sandbox.cursorStepProgress > 0) {
        toProgress = sandbox.cursorStepIndex;
        stepIndex = sandbox.cursorStepIndex;
        stepMoves = Array.isArray(timeline.move_steps?.[stepIndex]) ? timeline.move_steps[stepIndex] : [];
        model = getModelAtStep(stepIndex);
      } else {
        stepIndex = Math.max(0, sandbox.cursorStepIndex - 1);
        stepMoves = Array.isArray(timeline.move_steps?.[stepIndex]) ? timeline.move_steps[stepIndex] : [];
        model = getModelAtStep(stepIndex);
        fromProgress = stepIndex + 1;
        toProgress = stepIndex;
      }
    } else if (delta > 0) {
      if (progress >= total - 0.000001) return false;
      stepIndex = sandbox.cursorStepIndex;
      stepMoves = Array.isArray(timeline.move_steps?.[stepIndex]) ? timeline.move_steps[stepIndex] : [];
      model = getModelAtStep(stepIndex);
      toProgress = Math.min(stepIndex + 1, total);
    } else {
      return false;
    }

    if (!model) {
      store.dispatch({ type: "SET_PROGRESS", progress: toProgress });
      renderSandboxProgress({ progress: toProgress });
      return true;
    }

    const fromSnapshot = resolveSnapshotForProgress(fromProgress);
    const toSnapshot = resolveSnapshotForProgress(toProgress);
    const durationMs = Number(options.durationMs) || (animate ? sandboxStepDurationMs(stepMoves) : 0);

    store.dispatch({ type: "SET_PLAYBACK_MODE", mode: animate ? "stepping" : (resumePlaying ? "playing" : "idle") });
    updateSandboxControls();

    if (!animate || !state.sandboxPlayer?.animateTransition || !stepMoves.length) {
      store.dispatch({ type: "SET_PROGRESS", progress: toProgress });
      store.dispatch({ type: "SET_PLAYBACK_MODE", mode: resumePlaying ? "playing" : "idle" });
      renderSandboxProgress({ progress: toProgress });
      await flushActionQueue();
      return true;
    }

    const reverse = delta < 0;
    const token = sandboxState().playbackToken;
    let animated = false;
    try {
      animated = await state.sandboxPlayer.animateTransition(fromSnapshot, toSnapshot, {
        durationMs,
        easing: sandboxState().playbackConfig?.rate_func,
        interpolator: (progress01) => {
          const interpolation = reverse
            ? interpolateStep(model, stepMoves, 1 - progress01, { easing: resolveEasing(sandboxState().playbackConfig?.rate_func) })
            : interpolateStep(model, stepMoves, progress01, { easing: resolveEasing(sandboxState().playbackConfig?.rate_func) });
          return interpolation;
        },
        onProgress: (progress01) => {
          if (reverse) {
            store.dispatch({ type: "SET_PROGRESS", progress: fromProgress - progress01 });
          } else {
            store.dispatch({ type: "SET_PROGRESS", progress: stepIndex + progress01 });
          }
          updateTimelineDisplay();
          updateActiveAlgorithmStepHighlight();
        },
      });
    } catch (_error) {
      animated = false;
    }

    if (token !== sandboxState().playbackToken) {
      return false;
    }

    if (!animated) {
      store.dispatch({ type: "SET_PROGRESS", progress: toProgress });
      renderSandboxProgress({ progress: toProgress });
      store.dispatch({ type: "SET_PLAYBACK_MODE", mode: resumePlaying ? "playing" : "idle" });
      updateSandboxControls();
      await flushActionQueue();
      return true;
    }

    store.dispatch({ type: "SET_PROGRESS", progress: toProgress });
    store.dispatch({ type: "SET_PLAYBACK_MODE", mode: resumePlaying ? "playing" : "idle" });
    renderSandboxProgress({ progress: toProgress });
    await flushActionQueue();
    return true;
  }

  async function startPlayback() {
    const timeline = currentTimeline();
    if (!timeline || isPlaying() || isScrubbing() || isStepping()) return;
    const total = currentSandboxStepCount();
    if (total <= 0) return;

    if (sandboxState().timelineProgress >= total) {
      renderSandboxProgress({ progress: 0 });
    }

    store.dispatch({ type: "SET_PLAYBACK_MODE", mode: "playing" });
    store.dispatch({ type: "BUMP_TOKEN" });
    const token = sandboxState().playbackToken;
    updateSandboxControls();

    while (sandboxState().playbackMode === "playing" && token === sandboxState().playbackToken) {
      const nowTotal = currentSandboxStepCount();
      if (sandboxState().timelineProgress >= nowTotal - 0.000001) break;
      const stepIndex = sandboxState().cursorStepIndex;
      if (stepIndex >= nowTotal) break;
      const stepMoves = timeline.move_steps?.[stepIndex] || [];
      const durationMs = sandboxStepDurationMs(stepMoves);
      const moved = await moveBy(1, { animate: true, durationMs, resumePlaying: true });
      if (!moved || token !== sandboxState().playbackToken || sandboxState().playbackMode !== "playing") {
        break;
      }
      if (sandboxState().timelineProgress >= nowTotal - 0.000001) {
        break;
      }
      const pauseOk = await sleepWithToken(sandboxInterMovePauseMs(), token);
      if (!pauseOk) return;
    }

    if (token !== sandboxState().playbackToken) return;
    if (sandboxState().playbackMode === "playing") {
      store.dispatch({ type: "SET_PLAYBACK_MODE", mode: "idle" });
    }
    if (sandboxState().timelineProgress >= currentSandboxStepCount() - 0.000001) {
      const restartDelayOk = await sleepWithToken(SANDBOX_RESTART_DELAY_MS, token);
      if (!restartDelayOk) return;
      renderSandboxProgress({ progress: 0 });
    }
    updateSandboxControls();
  }

  function togglePlayback() {
    if (isPlaying() || isStepping()) {
      stopPlayback();
      return;
    }
    void startPlayback();
  }

  function setStep(index) {
    if (!currentTimeline() || isStepping()) return false;
    return renderSandboxProgress({ progress: index });
  }

  function setProgress(progress) {
    if (!currentTimeline() || isStepping()) return false;
    return renderSandboxProgress({ progress });
  }

  function toStart() {
    if (!currentTimeline() || isStepping()) return;
    stopPlayback({ silent: true, preserveQueue: false });
    renderSandboxProgress({ progress: 0 });
  }

  async function stepBackward() {
    if (!currentTimeline()) return;
    if (isTransportLocked()) {
      enqueueAction("prev");
      return;
    }
    const targetStep = Math.max(0, sandboxState().cursorStepProgress > 0 ? sandboxState().cursorStepIndex : sandboxState().cursorStepIndex - 1);
    const stepMoves = currentTimeline()?.move_steps?.[targetStep] || [];
    await moveBy(-1, { animate: true, resumePlaying: false, durationMs: manualStepDurationMs(stepMoves) });
  }

  async function stepForward() {
    if (!currentTimeline()) return;
    if (isTransportLocked()) {
      enqueueAction("next");
      return;
    }
    const stepMoves = currentTimeline()?.move_steps?.[sandboxState().cursorStepIndex] || [];
    await moveBy(1, { animate: true, resumePlaying: false, durationMs: manualStepDurationMs(stepMoves) });
  }

  function queueTimelinePreview(progress) {
    const normalized = normalizeTimelineProgress(progress);
    store.dispatch({ type: "SET_PENDING_TIMELINE_PROGRESS", progress: normalized });
    if (sandboxState().timelineRafPending) return;
    store.dispatch({ type: "SET_TIMELINE_RAF_PENDING", value: true });
    window.requestAnimationFrame(() => {
      const pending = sandboxState().pendingTimelineProgress;
      store.dispatch({ type: "SET_TIMELINE_RAF_PENDING", value: false });
      if (pending == null || isStepping()) return;
      store.dispatch({ type: "SET_PENDING_TIMELINE_PROGRESS", progress: null });
      renderSandboxProgress({ progress: pending });
    });
  }

  function beginScrubbing() {
    if (!currentTimeline()) return;
    const wasPlaying = isPlaying();
    stopPlayback({ silent: true, preserveQueue: false });
    store.dispatch({ type: "SET_WAS_PLAYING_BEFORE_SCRUB", value: wasPlaying });
    store.dispatch({ type: "SET_PLAYBACK_MODE", mode: "scrubbing" });
    updateSandboxControls();
  }

  async function finishScrubbing(progress) {
    if (!currentTimeline()) return;
    if (isStepping()) {
      window.setTimeout(() => {
        void finishScrubbing(progress);
      }, 20);
      return;
    }

    store.dispatch({ type: "SET_PENDING_TIMELINE_PROGRESS", progress: null });
    renderSandboxProgress({ progress });
    const resumePlaying = sandboxState().wasPlayingBeforeScrub;
    store.dispatch({ type: "SET_WAS_PLAYING_BEFORE_SCRUB", value: false });
    store.dispatch({ type: "SET_PLAYBACK_MODE", mode: "idle" });

    if (resumePlaying) {
      await startPlayback();
    } else {
      updateSandboxControls();
    }
  }

  function resetSandboxData() {
    hardResetOnSwitch({ clearData: true });
  }

  function loadTimeline(timeline, activeFormula) {
    hardResetOnSwitch({ clearData: true });
    const cubeSize = Number(timeline?.cube_size) || inferCubeSizeFromStateSlots(timeline?.state_slots || []);
    const initialModel = createCubeModel(cubeSize, String(timeline?.initial_state || ""), Array.isArray(timeline?.state_slots) ? timeline.state_slots : []);
    const prepared = snapshotsForTimeline(initialModel, timeline?.move_steps || []);
    const playbackConfig = normalizeSandboxPlaybackConfig(timeline?.playback_config);
    const isF2L = String(timeline?.group || "").toUpperCase() === "F2L";

    store.dispatch({
      type: "LOAD_TIMELINE",
      timeline,
      activeFormula,
      cubeSize,
      timelineModels: prepared.models,
      timelineSnapshots: prepared.snapshots,
      playbackConfig,
    });
    syncLegacyState();
    onRenderActiveAlgorithmDisplay(activeFormula || "");

    if (state.sandboxPlayer) {
      state.sandboxPlayer.buildScene?.(cubeSize);
      state.sandboxPlayer.setFaceColors?.(timeline?.face_colors || null);
      state.sandboxPlayer.setStickerlessTopMask?.(isF2L, 0x0b1220);
      window.requestAnimationFrame(() => {
        state.sandboxPlayer?.resize?.();
        renderSandboxProgress({ progress: 0 });
      });
    }

    renderSandboxProgress({ progress: 0 });
  }

  store.subscribe(() => {
    syncLegacyState();
  });
  syncLegacyState();
  updateSandboxControls();

  return {
    updateSandboxControls,
    renderSandboxProgress,
    setPlaybackSpeed,
    cyclePlaybackSpeed,
    stopPlayback,
    hardResetOnSwitch,
    resetSandboxData,
    loadTimeline,
    setStep,
    setProgress,
    toStart,
    stepBackward,
    stepForward,
    queueTimelinePreview,
    beginScrubbing,
    finishScrubbing,
    startPlayback,
    togglePlayback,
    currentSandboxStepCount,
    isPlaying,
    isScrubbing,
    isStepping,
  };
}
