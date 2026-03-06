import {
  DEFAULT_SANDBOX_PLAYBACK_CONFIG,
  SANDBOX_PLAYBACK_SPEEDS,
  SANDBOX_RESTART_DELAY_MS,
} from "../core/constants.js";
import { clamp } from "../utils/common.js";
import { normalizeSandboxPlaybackConfig } from "../domain/timeline-builder.js";

/**
 * @param {Object} deps
 */
export function createSandboxController(deps) {
  const { state, dom, machine, onRenderActiveAlgorithmDisplay, onUpdateActiveAlgorithmStepHighlight } = deps;
  const PLAY_ICON =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><polygon class="fill-icon" points="8,6 18,12 8,18"></polygon></svg>';
  const PAUSE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6V18"></path><path d="M15 6V18"></path></svg>';

  function transition(event, payload = {}) {
    machine.send(event, payload);
    state.sandboxMachineState = machine.getState();
    return state.sandboxMachineState;
  }

  function currentSandboxStepCount() {
    const steps = state.sandboxData?.move_steps;
    return Array.isArray(steps) ? steps.length : 0;
  }

  function normalizeTimelineProgress(rawProgress) {
    const total = currentSandboxStepCount();
    const numeric = Number(rawProgress);
    if (!Number.isFinite(numeric)) return 0;
    return clamp(numeric, 0, total);
  }

  function isDoubleTurnMove(move) {
    return /2'?$/.test(String(move || "").trim());
  }

  function sandboxStepDurationMs(stepMoves) {
    const cfg = state.sandboxPlaybackConfig || DEFAULT_SANDBOX_PLAYBACK_CONFIG;
    const speed = state.sandboxPlaybackSpeed || 1;
    const step = Array.isArray(stepMoves) ? stepMoves : [];
    const allDoubleTurns = step.length > 0 && step.every(isDoubleTurnMove);
    const runTimeSec = allDoubleTurns ? cfg.run_time_sec * cfg.double_turn_multiplier : cfg.run_time_sec;
    return Math.max(80, Math.round((runTimeSec * 1000) / speed));
  }

  function sandboxInterMovePauseMs() {
    const cfg = state.sandboxPlaybackConfig || DEFAULT_SANDBOX_PLAYBACK_CONFIG;
    const speed = state.sandboxPlaybackSpeed || 1;
    const pauseSec = (cfg.run_time_sec * cfg.inter_move_pause_ratio) / speed;
    return Math.max(0, Math.round(pauseSec * 1000));
  }

  function setCursorFromTimelineProgress(rawProgress) {
    const total = currentSandboxStepCount();
    const clamped = normalizeTimelineProgress(rawProgress);
    let stepIndex = Math.floor(clamped);
    let stepProgress = 0;
    if (stepIndex >= total) {
      stepIndex = total;
      stepProgress = 0;
    } else {
      stepProgress = clamp(clamped - stepIndex, 0, 0.999999);
      if (stepProgress >= 0.999999) {
        stepIndex = Math.min(stepIndex + 1, total);
        stepProgress = 0;
      }
    }
    state.sandboxTimelineProgress = clamped;
    state.sandboxCursorStepIndex = stepIndex;
    state.sandboxCursorStepProgress = stepProgress;
    state.sandboxStepIndex = stepIndex;
  }

  function timelineCurrentStepForHighlight() {
    const total = currentSandboxStepCount();
    const stepIndex = state.sandboxCursorStepIndex;
    if (stepIndex < total && state.sandboxCursorStepProgress > 0) {
      return stepIndex;
    }
    return -1;
  }

  function timelineLabelText() {
    const total = currentSandboxStepCount();
    const progress = normalizeTimelineProgress(state.sandboxTimelineProgress);
    return `${progress.toFixed(2)} / ${total}`;
  }

  function stepLabelText() {
    const total = currentSandboxStepCount();
    const stepIndex = state.sandboxCursorStepIndex;
    const stepProgress = state.sandboxCursorStepProgress;
    if (!total) return "Step 0/0";
    if (stepIndex >= total && stepProgress <= 0) return `Step ${total}/${total} · Done`;
    if (stepProgress > 0 && stepIndex < total) {
      const label = state.sandboxData?.highlight_by_step?.[stepIndex] || "";
      const percent = Math.round(stepProgress * 100);
      return label
        ? `Step ${stepIndex + 1}/${total} · ${label} (${percent}%)`
        : `Step ${stepIndex + 1}/${total} (${percent}%)`;
    }
    if (stepIndex === 0) return `Step 0/${total} · Start`;
    const label = state.sandboxData?.highlight_by_step?.[stepIndex - 1] || "";
    return label ? `Step ${stepIndex}/${total} · ${label}` : `Step ${stepIndex}/${total}`;
  }

  function updateTimelineDisplay() {
    const total = currentSandboxStepCount();
    if (dom.sandboxTimelineSlider) {
      dom.sandboxTimelineSlider.max = String(total);
      dom.sandboxTimelineSlider.value = String(normalizeTimelineProgress(state.sandboxTimelineProgress));
    }
    if (dom.sandboxTimelineLabel) {
      dom.sandboxTimelineLabel.textContent = timelineLabelText();
    }
  }

  function updateActiveAlgorithmStepHighlight() {
    const activeStep = timelineCurrentStepForHighlight();
    onUpdateActiveAlgorithmStepHighlight(activeStep);
  }

  function isPlaying() {
    return machine.is("PLAYING");
  }

  function isStepping() {
    return machine.is("STEPPING");
  }

  function isScrubbing() {
    return machine.is("SCRUBBING");
  }

  function renderSandboxProgress(options = {}) {
    if (!state.sandboxData) {
      dom.sandboxStepLabel.textContent = "Step 0/0";
      state.sandboxTimelineProgress = 0;
      updateTimelineDisplay();
      updateActiveAlgorithmStepHighlight();
      return false;
    }

    const progress = options.progress != null ? options.progress : state.sandboxTimelineProgress;
    const syncState = options.syncState !== false;
    setCursorFromTimelineProgress(progress);

    const total = currentSandboxStepCount();
    const stepIndex = state.sandboxCursorStepIndex;
    const stepProgress = state.sandboxCursorStepProgress;

    if (syncState && state.sandboxPlayer) {
      const baseState = state.sandboxData.states_by_step?.[stepIndex] || "";
      if (baseState) {
        state.sandboxPlayer.setState(baseState);
        if (stepProgress > 0 && stepIndex < total && state.sandboxPlayer.previewStepFromState) {
          const stepMoves = Array.isArray(state.sandboxData.move_steps?.[stepIndex]) ? state.sandboxData.move_steps[stepIndex] : [];
          state.sandboxPlayer.previewStepFromState(baseState, stepMoves, {
            progress: stepProgress,
            easing: state.sandboxPlaybackConfig.rate_func,
          });
        }
      }
    }

    dom.sandboxStepLabel.textContent = stepLabelText();
    updateTimelineDisplay();
    updateActiveAlgorithmStepHighlight();
    updateSandboxControls();
    return true;
  }

  function updateSandboxControls() {
    const hasTimeline = Boolean(state.sandboxData);
    const total = currentSandboxStepCount();
    const progress = normalizeTimelineProgress(state.sandboxTimelineProgress);
    const atStart = progress <= 0.000001;
    const atEnd = progress >= total - 0.000001;
    const locked = isStepping() || isPlaying() || isScrubbing();

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
    if (dom.sandboxTimelineSlider) {
      dom.sandboxTimelineSlider.disabled = !hasTimeline || total === 0;
    }

    const speedButtons = Array.from(document.querySelectorAll(".sandbox-speed-btn"));
    if (speedButtons.length) {
      speedButtons.forEach((btn) => {
        const speedValue = Number(btn.dataset.speed || "1");
        btn.classList.toggle("active", speedValue === state.sandboxPlaybackSpeed);
        btn.disabled = !hasTimeline || total === 0;
      });
    }

    if (!hasTimeline) {
      dom.sandboxStepLabel.textContent = "Step 0/0";
    }

    updateTimelineDisplay();
    updateActiveAlgorithmStepHighlight();
  }

  function setPlaybackSpeed(rawSpeed) {
    const parsed = Number(rawSpeed);
    state.sandboxPlaybackSpeed = SANDBOX_PLAYBACK_SPEEDS.includes(parsed) ? parsed : 1;
    updateSandboxControls();
  }

  function sleepWithToken(delayMs, token) {
    const ms = Math.max(0, Math.round(delayMs));
    if (!ms) {
      return Promise.resolve(state.sandboxPlaybackToken === token);
    }
    return new Promise((resolve) => {
      window.setTimeout(() => {
        resolve(state.sandboxPlaybackToken === token);
      }, ms);
    });
  }

  function stopPlayback(options = {}) {
    const hadPlayback = isPlaying();
    if (hadPlayback) {
      transition("PLAY_TOGGLE");
    }
    state.sandboxPlaybackToken += 1;
    if (!options.silent && (hadPlayback || options.forceUpdate)) {
      updateSandboxControls();
    }
  }

  function hardResetOnSwitch(options = {}) {
    const clearData = options.clearData !== false;
    stopPlayback({ silent: true, forceUpdate: true });
    transition("RESET");
    if (clearData) {
      state.sandboxData = null;
    }
    state.sandboxStepIndex = 0;
    state.sandboxTimelineProgress = 0;
    state.sandboxCursorStepIndex = 0;
    state.sandboxCursorStepProgress = 0;
    state.sandboxTimelineRafPending = false;
    state.sandboxPendingTimelineProgress = null;
    state.sandboxWasPlayingBeforeScrub = false;
    state.sandboxPlaybackConfig = { ...DEFAULT_SANDBOX_PLAYBACK_CONFIG };
    if (state.sandboxPlayer) {
      state.sandboxPlayer.setSlots([]);
      if (state.sandboxPlayer.setStickerlessTopMask) {
        state.sandboxPlayer.setStickerlessTopMask(false);
      }
      state.sandboxPlayer.setState("");
    }
    updateSandboxControls();
  }

  async function moveBy(delta, options = {}) {
    if (!state.sandboxData || isStepping() || isScrubbing()) return false;
    const total = currentSandboxStepCount();
    if (total <= 0) return false;
    const animate = options.animate !== false;
    const resumePlaying = Boolean(options.resumePlaying);

    if (delta < 0) {
      const currentProgress = normalizeTimelineProgress(state.sandboxTimelineProgress);
      if (currentProgress <= 0.000001) return false;
      if (state.sandboxCursorStepProgress > 0) {
        transition("STEP_PREV");
        const rendered = renderSandboxProgress({ progress: state.sandboxCursorStepIndex, syncState: true });
        transition("ANIM_DONE", { resumePlaying });
        return rendered;
      }

      const targetStep = Math.max(0, state.sandboxCursorStepIndex - 1);
      const moveStep = Array.isArray(state.sandboxData.move_steps?.[targetStep]) ? state.sandboxData.move_steps[targetStep] : [];
      const durationMs = Number(options.durationMs) || sandboxStepDurationMs(moveStep);

      transition("STEP_PREV");
      if (!isStepping()) return false;

      if (animate && state.sandboxPlayer?.playStep && moveStep.length) {
        let animated = false;
        try {
          animated = await state.sandboxPlayer.playStep(moveStep, {
            reverse: true,
            durationMs,
            easing: state.sandboxPlaybackConfig.rate_func,
          });
        } catch (error) {
          transition("ANIM_FAIL", { error, recover: true });
          return renderSandboxProgress({ progress: targetStep, syncState: true });
        }
        if (animated) {
          const rendered = renderSandboxProgress({ progress: targetStep, syncState: false });
          transition("ANIM_DONE", { resumePlaying });
          return rendered;
        }
      }

      const rendered = renderSandboxProgress({ progress: targetStep, syncState: true });
      transition("ANIM_DONE", { resumePlaying });
      return rendered;
    }

    if (delta > 0) {
      const stepIndex = state.sandboxCursorStepIndex;
      if (stepIndex >= total) return false;
      const stepProgress = state.sandboxCursorStepProgress;
      const moveStep = Array.isArray(state.sandboxData.move_steps?.[stepIndex]) ? state.sandboxData.move_steps[stepIndex] : [];
      const durationMs = Number(options.durationMs) || sandboxStepDurationMs(moveStep);
      const baseState = state.sandboxData.states_by_step?.[stepIndex] || "";

      transition("STEP_NEXT");
      if (!isStepping()) return false;

      if (animate && state.sandboxPlayer?.playStep && moveStep.length) {
        let animated = false;
        try {
          animated = await state.sandboxPlayer.playStep(moveStep, {
            durationMs,
            easing: state.sandboxPlaybackConfig.rate_func,
            baseState,
            startProgress: stepProgress,
            onProgress: (progress01) => {
              setCursorFromTimelineProgress(stepIndex + progress01);
              dom.sandboxStepLabel.textContent = stepLabelText();
              updateTimelineDisplay();
              updateActiveAlgorithmStepHighlight();
            },
          });
        } catch (error) {
          transition("ANIM_FAIL", { error, recover: true });
          return renderSandboxProgress({ progress: Math.min(stepIndex + 1, total), syncState: true });
        }

        if (animated) {
          const rendered = renderSandboxProgress({ progress: Math.min(stepIndex + 1, total), syncState: false });
          transition("ANIM_DONE", { resumePlaying });
          return rendered;
        }
      }

      const rendered = renderSandboxProgress({ progress: Math.min(stepIndex + 1, total), syncState: true });
      transition("ANIM_DONE", { resumePlaying });
      return rendered;
    }

    return false;
  }

  async function startPlayback() {
    if (!state.sandboxData || isPlaying() || isScrubbing() || isStepping()) return;
    const total = currentSandboxStepCount();
    if (total <= 0) return;

    if (state.sandboxTimelineProgress >= total) {
      renderSandboxProgress({ progress: 0, syncState: true });
    }

    transition("PLAY_TOGGLE");
    const token = state.sandboxPlaybackToken + 1;
    state.sandboxPlaybackToken = token;
    updateSandboxControls();

    while (machine.is("PLAYING") && token === state.sandboxPlaybackToken) {
      const nowTotal = currentSandboxStepCount();
      if (state.sandboxTimelineProgress >= nowTotal - 0.000001) break;
      if (isStepping() || isScrubbing()) {
        const ok = await sleepWithToken(12, token);
        if (!ok) return;
        continue;
      }

      const stepIndex = state.sandboxCursorStepIndex;
      if (stepIndex >= nowTotal) break;
      const step = state.sandboxData.move_steps?.[stepIndex] || [];
      const durationMs = sandboxStepDurationMs(step);
      const moved = await moveBy(1, { animate: true, durationMs, resumePlaying: true });
      if (!moved || token !== state.sandboxPlaybackToken || !machine.is("PLAYING")) {
        break;
      }
      if (state.sandboxTimelineProgress >= nowTotal - 0.000001) {
        break;
      }
      const pauseOk = await sleepWithToken(sandboxInterMovePauseMs(), token);
      if (!pauseOk) return;
    }

    if (token !== state.sandboxPlaybackToken) return;
    if (machine.is("PLAYING")) {
      transition("PLAY_TOGGLE");
    }
    if (state.sandboxTimelineProgress >= currentSandboxStepCount() - 0.000001) {
      const restartDelayOk = await sleepWithToken(SANDBOX_RESTART_DELAY_MS, token);
      if (!restartDelayOk) return;
      renderSandboxProgress({ progress: 0, syncState: true });
    }
    updateSandboxControls();
  }

  function togglePlayback() {
    if (isPlaying()) {
      stopPlayback();
      return;
    }
    void startPlayback();
  }

  function setStep(index) {
    if (!state.sandboxData || isStepping()) return false;
    return renderSandboxProgress({ progress: index, syncState: true });
  }

  function setProgress(progress) {
    if (!state.sandboxData || isStepping()) return false;
    return renderSandboxProgress({ progress, syncState: true });
  }

  function toStart() {
    if (!state.sandboxData || isStepping()) return;
    transition("TO_START");
    setProgress(0);
  }

  async function stepBackward() {
    if (!state.sandboxData || isStepping() || isPlaying() || isScrubbing()) return;
    await moveBy(-1, { animate: true, resumePlaying: false });
  }

  async function stepForward() {
    if (!state.sandboxData || isStepping() || isPlaying() || isScrubbing()) return;
    await moveBy(1, { animate: true, resumePlaying: false });
  }

  function queueTimelinePreview(progress) {
    state.sandboxPendingTimelineProgress = normalizeTimelineProgress(progress);
    if (state.sandboxTimelineRafPending) return;
    state.sandboxTimelineRafPending = true;
    window.requestAnimationFrame(() => {
      state.sandboxTimelineRafPending = false;
      const pending = state.sandboxPendingTimelineProgress;
      if (pending == null || isStepping()) return;
      state.sandboxPendingTimelineProgress = null;
      transition("SCRUB_UPDATE");
      renderSandboxProgress({ progress: pending, syncState: true });
    });
  }

  function beginScrubbing() {
    if (!state.sandboxData) return;
    state.sandboxPlaybackToken += 1;
    transition("SCRUB_BEGIN");
    updateSandboxControls();
  }

  async function finishScrubbing(progress) {
    if (!state.sandboxData) return;
    if (isStepping()) {
      window.setTimeout(() => {
        void finishScrubbing(progress);
      }, 20);
      return;
    }

    state.sandboxPendingTimelineProgress = null;
    renderSandboxProgress({ progress, syncState: true });
    const wasPlaying = machine.getContext().wasPlayingBeforeScrub;
    transition("SCRUB_END");

    if (wasPlaying && machine.is("PLAYING")) {
      await startPlayback();
    } else {
      updateSandboxControls();
    }
  }

  function resetSandboxData() {
    hardResetOnSwitch({ clearData: true });
  }

  function loadTimeline(sandbox, activeFormula) {
    hardResetOnSwitch({ clearData: true });
    const isF2L = String(sandbox.group || "").toUpperCase() === "F2L";
    state.sandboxData = sandbox;
    state.sandboxStepIndex = 0;
    state.sandboxTimelineProgress = 0;
    state.sandboxCursorStepIndex = 0;
    state.sandboxCursorStepProgress = 0;
    state.sandboxPlaybackConfig = normalizeSandboxPlaybackConfig(sandbox.playback_config);
    transition("LOAD_TIMELINE");
    onRenderActiveAlgorithmDisplay(activeFormula || "");

    if (state.sandboxPlayer) {
      state.sandboxPlayer.setSlots(Array.isArray(sandbox.state_slots) ? sandbox.state_slots : []);
      if (state.sandboxPlayer.setFaceColors) {
        state.sandboxPlayer.setFaceColors(null);
        if (sandbox.face_colors) {
          state.sandboxPlayer.setFaceColors(sandbox.face_colors);
        }
        if (isF2L && !state.sandboxPlayer.setStickerlessTopMask) {
          state.sandboxPlayer.setFaceColors({ U: 0x0b1220 });
        }
      }
      if (state.sandboxPlayer.setStickerlessTopMask) {
        state.sandboxPlayer.setStickerlessTopMask(isF2L, 0x0b1220);
      }
      window.requestAnimationFrame(() => {
        state.sandboxPlayer?.resize();
        renderSandboxProgress({ progress: 0, syncState: true });
      });
    }

    renderSandboxProgress({ progress: 0, syncState: true });
  }

  return {
    updateSandboxControls,
    renderSandboxProgress,
    setPlaybackSpeed,
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
