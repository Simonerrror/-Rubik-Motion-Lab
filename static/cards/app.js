(() => {
  const GROUPS = ["F2L", "OLL", "PLL"];
  const PROGRESS_SORT_STORAGE_KEY = "cards_progress_sort_by_group_v1";
  const STATUS_SORT_RANK = {
    IN_PROGRESS: 0,
    NEW: 1,
    LEARNED: 2,
  };
  const RECOGNIZER_CACHE_BUSTER = `r${Date.now()}`;
  const POLL_BACKOFF_STEPS_MS = [5000, 10000, 20000, 30000];
  const DEFAULT_SANDBOX_PLAYBACK_CONFIG = {
    run_time_sec: 0.65,
    double_turn_multiplier: 1.7,
    inter_move_pause_ratio: 0.05,
    rate_func: "ease_in_out_sine",
  };
  const SANDBOX_PLAYBACK_SPEEDS = [1, 1.5, 2];
  const STATUS_CYCLE = ["NEW", "IN_PROGRESS", "LEARNED"];

  function loadProgressSortMap() {
    const defaults = { F2L: false, OLL: false, PLL: false };
    try {
      const raw = localStorage.getItem(PROGRESS_SORT_STORAGE_KEY);
      if (!raw) return defaults;
      const parsed = JSON.parse(raw);
      GROUPS.forEach((group) => {
        if (Object.prototype.hasOwnProperty.call(parsed || {}, group)) {
          defaults[group] = Boolean(parsed[group]);
        }
      });
    } catch (error) {
      console.warn(error);
    }
    return defaults;
  }

  function saveProgressSortMap(map) {
    try {
      localStorage.setItem(PROGRESS_SORT_STORAGE_KEY, JSON.stringify(map));
    } catch (error) {
      console.warn(error);
    }
  }

  const state = {
    category: "PLL",
    cases: [],
    activeCaseId: null,
    activeCase: null,
    localPendingByCase: new Map(),
    pendingStatusByCase: new Set(),
    activeDisplayMode: "algorithm",
    activeDisplayFormula: "",
    pollTimer: null,
    pollBackoffIndex: 0,
    pollOutageNotified: false,
    progressSortByGroup: loadProgressSortMap(),
    playbackMode: "sandbox",
    sandboxData: null,
    sandboxStepIndex: 0,
    sandboxRequestToken: 0,
    sandboxPlayer: null,
    sandboxBusy: false,
    sandboxPlaybackSpeed: 1,
    sandboxPlaybackActive: false,
    sandboxPlaybackToken: 0,
    sandboxPlaybackConfig: { ...DEFAULT_SANDBOX_PLAYBACK_CONFIG },
    sandboxTimelineProgress: 0,
    sandboxScrubbing: false,
    sandboxWasPlayingBeforeScrub: false,
    sandboxTimelineRafPending: false,
    sandboxPendingTimelineProgress: null,
    sandboxCursorStepIndex: 0,
    sandboxCursorStepProgress: 0,
  };

  const DOM = {
    catalog: document.getElementById("catalog-container"),
    sortProgressToggle: document.getElementById("sort-progress-toggle"),
    mName: document.getElementById("m-name"),
    mProb: document.getElementById("m-prob"),
    mCaseCode: document.getElementById("m-case-code"),
    mVideo: document.getElementById("m-video"),
    mQueueMsg: document.getElementById("m-queue-msg"),
    modeVideoBtn: document.getElementById("mode-video-btn"),
    modeSandboxBtn: document.getElementById("mode-sandbox-btn"),
    sandboxFrame: document.getElementById("sandbox-frame"),
    sandboxCanvas: document.getElementById("sandbox-canvas"),
    sandboxToStartBtn: document.getElementById("sandbox-to-start-btn"),
    sandboxPrevBtn: document.getElementById("sandbox-prev-btn"),
    sandboxPlayPauseBtn: document.getElementById("sandbox-play-pause-btn"),
    sandboxNextBtn: document.getElementById("sandbox-next-btn"),
    sandboxSpeedButtons: Array.from(document.querySelectorAll(".sandbox-speed-btn")),
    sandboxTimelineSlider: document.getElementById("sandbox-timeline-slider"),
    sandboxTimelineLabel: document.getElementById("sandbox-timeline-label"),
    sandboxStepLabel: document.getElementById("sandbox-step-label"),
    sandboxOverlayTitle: document.getElementById("sandbox-overlay-title"),
    sandboxOverlaySubtitle: document.getElementById("sandbox-overlay-subtitle"),
    sandboxOverlayTopImage: document.getElementById("sandbox-overlay-top-image"),
    sandboxOverlayFormula: document.getElementById("sandbox-overlay-formula"),
    mStatusGroup: document.getElementById("m-status-group"),
    mAlgoList: document.getElementById("m-algo-list"),
    activeAlgoDisplay: document.getElementById("active-algo-display"),
    toast: document.getElementById("toast"),
  };

  function sandboxSpeedButtons() {
    return Array.from(document.querySelectorAll(".sandbox-speed-btn"));
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function sandboxOverlayFormula(caseItem) {
    const active = String(state.activeDisplayFormula || "").trim();
    if (state.activeDisplayMode === "custom" && active) return active;
    return active || String(caseItem?.active_formula || "").trim();
  }

  function formatSandboxFormulaOverlay(formula) {
    const allMoves = tokenizeFormula(formula);
    if (!allMoves.length) return "";
    const maxMoves = 24;
    const rowSize = 8;
    const truncated = allMoves.length > maxMoves;
    const moves = allMoves.slice(0, maxMoves);
    const rows = [];
    for (let index = 0; index < moves.length; index += rowSize) {
      rows.push(moves.slice(index, index + rowSize).join(" "));
    }
    if (truncated && rows.length) {
      rows[rows.length - 1] = `${rows[rows.length - 1]} ...`;
    }
    return rows.join("\n");
  }

  function updateSandboxOverlay(caseItem = currentCase()) {
    if (DOM.sandboxOverlayTitle) {
      DOM.sandboxOverlayTitle.textContent = caseItem ? detailTitle(caseItem) : "Select Case";
    }
    if (DOM.sandboxOverlaySubtitle) {
      DOM.sandboxOverlaySubtitle.textContent = caseItem
        ? [caseShortLabel(caseItem), caseItem.subgroup_title].filter(Boolean).join(" · ")
        : "-";
    }
    if (DOM.sandboxOverlayFormula) {
      const formula = caseItem ? sandboxOverlayFormula(caseItem) : "";
      const formatted = formatSandboxFormulaOverlay(formula);
      DOM.sandboxOverlayFormula.textContent = formatted || "-";
      DOM.sandboxOverlayFormula.title = formula || "";
    }
    if (DOM.sandboxOverlayTopImage) {
      const recognizerUrl = caseItem ? String(caseItem.recognizer_url || "").trim() : "";
      if (recognizerUrl) {
        const sep = recognizerUrl.includes("?") ? "&" : "?";
        DOM.sandboxOverlayTopImage.src = `${recognizerUrl}${sep}v=${RECOGNIZER_CACHE_BUSTER}`;
        DOM.sandboxOverlayTopImage.style.visibility = "visible";
      } else {
        DOM.sandboxOverlayTopImage.removeAttribute("src");
        DOM.sandboxOverlayTopImage.style.visibility = "hidden";
      }
    }
  }

  function clearPollingTimer() {
    if (state.pollTimer) {
      clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
  }

  function getCurrentPollDelayMs() {
    return POLL_BACKOFF_STEPS_MS[Math.min(state.pollBackoffIndex, POLL_BACKOFF_STEPS_MS.length - 1)];
  }

  function scheduleNextPoll() {
    clearPollingTimer();
    state.pollTimer = setTimeout(() => {
      void pollQueue();
    }, getCurrentPollDelayMs());
  }

  function markPollFailure() {
    if (!state.pollOutageNotified) {
      showToast("Cards API unavailable. Retrying...");
      state.pollOutageNotified = true;
    }
    if (state.pollBackoffIndex < POLL_BACKOFF_STEPS_MS.length - 1) {
      state.pollBackoffIndex += 1;
    }
  }

  function markPollSuccess() {
    state.pollBackoffIndex = 0;
    state.pollOutageNotified = false;
  }

  function normalizeSandboxPlaybackConfig(raw) {
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

  function stopSandboxPlayback(options = {}) {
    const hadPlayback = state.sandboxPlaybackActive;
    state.sandboxPlaybackActive = false;
    state.sandboxPlaybackToken += 1;
    if (!options.silent && (hadPlayback || options.forceUpdate)) {
      updateSandboxControls();
    }
  }

  function setSandboxPlaybackSpeed(rawSpeed) {
    const parsed = Number(rawSpeed);
    const next = SANDBOX_PLAYBACK_SPEEDS.includes(parsed) ? parsed : 1;
    state.sandboxPlaybackSpeed = next;
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

  function isDoubleTurnMove(move) {
    return /2'?$/.test(String(move || "").trim());
  }

  function sandboxStepDurationMs(stepMoves) {
    const cfg = state.sandboxPlaybackConfig || DEFAULT_SANDBOX_PLAYBACK_CONFIG;
    const speed = state.sandboxPlaybackSpeed || 1;
    const step = Array.isArray(stepMoves) ? stepMoves : [];
    const allDoubleTurns = step.length > 0 && step.every(isDoubleTurnMove);
    const runTimeSec = allDoubleTurns
      ? cfg.run_time_sec * cfg.double_turn_multiplier
      : cfg.run_time_sec;
    return Math.max(80, Math.round((runTimeSec * 1000) / speed));
  }

  function sandboxInterMovePauseMs() {
    const cfg = state.sandboxPlaybackConfig || DEFAULT_SANDBOX_PLAYBACK_CONFIG;
    const speed = state.sandboxPlaybackSpeed || 1;
    const pauseSec = (cfg.run_time_sec * cfg.inter_move_pause_ratio) / speed;
    return Math.max(0, Math.round(pauseSec * 1000));
  }

  function setPlaybackMode() {
    state.playbackMode = "sandbox";
    DOM.modeVideoBtn?.classList.remove("active");
    DOM.modeSandboxBtn?.classList.add("active");
    DOM.mVideo?.classList.add("hidden");
    DOM.sandboxFrame?.classList.remove("hidden");
    if (state.sandboxPlayer) {
      window.requestAnimationFrame(() => {
        state.sandboxPlayer?.resize();
        renderSandboxStep();
      });
    }
    updateSandboxControls();
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
    if (DOM.sandboxTimelineSlider) {
      DOM.sandboxTimelineSlider.max = String(total);
      DOM.sandboxTimelineSlider.value = String(normalizeTimelineProgress(state.sandboxTimelineProgress));
    }
    if (DOM.sandboxTimelineLabel) {
      DOM.sandboxTimelineLabel.textContent = timelineLabelText();
    }
  }

  function updateActiveAlgorithmStepHighlight() {
    const activeStep = timelineCurrentStepForHighlight();
    DOM.activeAlgoDisplay.querySelectorAll(".move-tile[data-step-index]").forEach((tile) => {
      const index = Number(tile.getAttribute("data-step-index"));
      tile.classList.toggle("current", index === activeStep);
    });
  }

  function renderSandboxProgress(options = {}) {
    if (!state.sandboxData) {
      DOM.sandboxStepLabel.textContent = "Step 0/0";
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
    DOM.sandboxStepLabel.textContent = stepLabelText();
    updateTimelineDisplay();
    updateActiveAlgorithmStepHighlight();
    updateSandboxControls();
    return true;
  }

  function renderSandboxStep(options = {}) {
    const progress = options.progress != null ? options.progress : state.sandboxTimelineProgress;
    return renderSandboxProgress({
      progress,
      syncState: options.syncState,
    });
  }

  function updateSandboxControls() {
    const hasTimeline = Boolean(state.sandboxData);
    const total = currentSandboxStepCount();
    const progress = normalizeTimelineProgress(state.sandboxTimelineProgress);
    const atStart = progress <= 0.000001;
    const atEnd = progress >= total - 0.000001;
    const locked = state.sandboxBusy || state.sandboxPlaybackActive || state.sandboxScrubbing;

    if (DOM.sandboxToStartBtn) {
      DOM.sandboxToStartBtn.disabled = !hasTimeline || atStart || locked;
      DOM.sandboxToStartBtn.title = "Back to start";
      DOM.sandboxToStartBtn.setAttribute("aria-label", "Back to start");
    }
    if (DOM.sandboxPrevBtn) {
      DOM.sandboxPrevBtn.disabled = !hasTimeline || atStart || locked;
      DOM.sandboxPrevBtn.title = "Previous step";
      DOM.sandboxPrevBtn.setAttribute("aria-label", "Previous step");
    }
    if (DOM.sandboxPlayPauseBtn) {
      DOM.sandboxPlayPauseBtn.disabled = !hasTimeline || total === 0;
      const isPlaying = state.sandboxPlaybackActive;
      DOM.sandboxPlayPauseBtn.textContent = isPlaying ? "⏸" : "▶";
      DOM.sandboxPlayPauseBtn.title = isPlaying ? "Pause" : "Play";
      DOM.sandboxPlayPauseBtn.setAttribute("aria-label", isPlaying ? "Pause" : "Play");
    }
    if (DOM.sandboxNextBtn) {
      DOM.sandboxNextBtn.disabled = !hasTimeline || atEnd || locked;
      DOM.sandboxNextBtn.title = "Next step";
      DOM.sandboxNextBtn.setAttribute("aria-label", "Next step");
    }
    if (DOM.sandboxTimelineSlider) {
      DOM.sandboxTimelineSlider.disabled = !hasTimeline || total === 0;
    }
    const speedButtons = sandboxSpeedButtons();
    if (speedButtons.length) {
      speedButtons.forEach((btn) => {
        const speedValue = Number(btn.dataset.speed || "1");
        btn.classList.toggle("active", speedValue === state.sandboxPlaybackSpeed);
        btn.disabled = !hasTimeline || total === 0;
      });
    }
    if (!hasTimeline) {
      DOM.sandboxStepLabel.textContent = "Step 0/0";
    }
    updateTimelineDisplay();
    updateActiveAlgorithmStepHighlight();
  }

  function resetSandboxData() {
    stopSandboxPlayback({ silent: true });
    state.sandboxData = null;
    state.sandboxStepIndex = 0;
    state.sandboxTimelineProgress = 0;
    state.sandboxCursorStepIndex = 0;
    state.sandboxCursorStepProgress = 0;
    state.sandboxScrubbing = false;
    state.sandboxWasPlayingBeforeScrub = false;
    state.sandboxTimelineRafPending = false;
    state.sandboxPendingTimelineProgress = null;
    state.sandboxBusy = false;
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

  async function loadSandboxForCurrentCase() {
    const c = currentCase();
    if (!c?.id) {
      resetSandboxData();
      return;
    }

    const requestToken = state.sandboxRequestToken + 1;
    state.sandboxRequestToken = requestToken;
    try {
      const sandbox = await apiGet(`/api/cases/${c.id}/sandbox`);
      if (requestToken !== state.sandboxRequestToken) return;
      const isF2L = String(sandbox.group || "").toUpperCase() === "F2L";

      state.sandboxData = sandbox;
      state.sandboxStepIndex = 0;
      state.sandboxTimelineProgress = 0;
      state.sandboxCursorStepIndex = 0;
      state.sandboxCursorStepProgress = 0;
      state.sandboxBusy = false;
      stopSandboxPlayback({ silent: true });
      state.sandboxPlaybackConfig = normalizeSandboxPlaybackConfig(sandbox.playback_config);
      renderActiveAlgorithmDisplay(state.activeDisplayFormula);
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
        if (state.playbackMode === "sandbox") {
          window.requestAnimationFrame(() => {
            state.sandboxPlayer?.resize();
            renderSandboxProgress({ progress: 0, syncState: true });
          });
        }
      }
      renderSandboxProgress({ progress: 0, syncState: true });
    } catch (error) {
      if (requestToken !== state.sandboxRequestToken) return;
      resetSandboxData();
      setPlaybackMode();
      showToast(`Sandbox unavailable: ${String(error.message || error)}`);
    }
  }

  async function moveSandboxBy(delta, options = {}) {
    if (!state.sandboxData || state.sandboxBusy || state.sandboxScrubbing) return false;
    const total = currentSandboxStepCount();
    if (total <= 0) return false;
    const animate = options.animate !== false;

    if (delta < 0) {
      const currentProgress = normalizeTimelineProgress(state.sandboxTimelineProgress);
      if (currentProgress <= 0.000001) return false;
      if (state.sandboxCursorStepProgress > 0) {
        return renderSandboxProgress({ progress: state.sandboxCursorStepIndex, syncState: true });
      }

      const targetStep = Math.max(0, state.sandboxCursorStepIndex - 1);
      const moveStep = Array.isArray(state.sandboxData.move_steps?.[targetStep]) ? state.sandboxData.move_steps[targetStep] : [];
      const durationMs = Number(options.durationMs) || sandboxStepDurationMs(moveStep);
      if (animate && state.sandboxPlayer?.playStep && moveStep.length) {
        state.sandboxBusy = true;
        updateSandboxControls();
        let animated = false;
        try {
          animated = await state.sandboxPlayer.playStep(moveStep, {
            reverse: true,
            durationMs,
            easing: state.sandboxPlaybackConfig.rate_func,
          });
        } catch (error) {
          console.warn(error);
        }
        state.sandboxBusy = false;
        if (animated) {
          return renderSandboxProgress({ progress: targetStep, syncState: false });
        }
      }
      return renderSandboxProgress({ progress: targetStep, syncState: true });
    }

    if (delta > 0) {
      const stepIndex = state.sandboxCursorStepIndex;
      if (stepIndex >= total) return false;
      const stepProgress = state.sandboxCursorStepProgress;
      const moveStep = Array.isArray(state.sandboxData.move_steps?.[stepIndex]) ? state.sandboxData.move_steps[stepIndex] : [];
      const durationMs = Number(options.durationMs) || sandboxStepDurationMs(moveStep);
      const baseState = state.sandboxData.states_by_step?.[stepIndex] || "";
      if (animate && state.sandboxPlayer?.playStep && moveStep.length) {
        state.sandboxBusy = true;
        updateSandboxControls();
        let animated = false;
        try {
          animated = await state.sandboxPlayer.playStep(moveStep, {
            durationMs,
            easing: state.sandboxPlaybackConfig.rate_func,
            baseState,
            startProgress: stepProgress,
            onProgress: (progress01) => {
              setCursorFromTimelineProgress(stepIndex + progress01);
              DOM.sandboxStepLabel.textContent = stepLabelText();
              updateTimelineDisplay();
              updateActiveAlgorithmStepHighlight();
            },
          });
        } catch (error) {
          console.warn(error);
        }
        state.sandboxBusy = false;
        if (animated) {
          return renderSandboxProgress({ progress: Math.min(stepIndex + 1, total), syncState: false });
        }
      }
      return renderSandboxProgress({ progress: Math.min(stepIndex + 1, total), syncState: true });
    }

    return false;
  }

  function sandboxSetStep(index) {
    if (!state.sandboxData || state.sandboxBusy) return false;
    return renderSandboxProgress({ progress: index, syncState: true });
  }

  function sandboxSetProgress(progress) {
    if (!state.sandboxData || state.sandboxBusy) return false;
    return renderSandboxProgress({ progress, syncState: true });
  }

  function sandboxToStart() {
    if (!state.sandboxData || state.sandboxBusy) return;
    sandboxSetProgress(0);
  }

  async function sandboxStepBackward() {
    if (!state.sandboxData || state.sandboxBusy || state.sandboxPlaybackActive) return;
    await moveSandboxBy(-1, { animate: true });
  }

  async function sandboxStepForward() {
    if (!state.sandboxData || state.sandboxBusy || state.sandboxPlaybackActive) return;
    await moveSandboxBy(1, { animate: true });
  }

  function queueTimelinePreview(progress) {
    state.sandboxPendingTimelineProgress = normalizeTimelineProgress(progress);
    if (state.sandboxTimelineRafPending) return;
    state.sandboxTimelineRafPending = true;
    window.requestAnimationFrame(() => {
      state.sandboxTimelineRafPending = false;
      const pending = state.sandboxPendingTimelineProgress;
      if (pending == null) return;
      if (state.sandboxBusy) return;
      state.sandboxPendingTimelineProgress = null;
      renderSandboxProgress({ progress: pending, syncState: true });
    });
  }

  function beginSandboxScrubbing() {
    if (!state.sandboxData) return;
    state.sandboxWasPlayingBeforeScrub = state.sandboxPlaybackActive;
    if (state.sandboxPlaybackActive) {
      stopSandboxPlayback({ silent: true, forceUpdate: true });
    }
    state.sandboxScrubbing = true;
    updateSandboxControls();
  }

  async function finishSandboxScrubbing(progress) {
    if (!state.sandboxData) return;
    if (state.sandboxBusy) {
      window.setTimeout(() => {
        void finishSandboxScrubbing(progress);
      }, 20);
      return;
    }
    state.sandboxScrubbing = false;
    state.sandboxPendingTimelineProgress = null;
    renderSandboxProgress({ progress, syncState: true });
    const shouldResume = state.sandboxWasPlayingBeforeScrub;
    state.sandboxWasPlayingBeforeScrub = false;
    if (shouldResume) {
      await startSandboxPlayback();
    } else {
      updateSandboxControls();
    }
  }

  async function startSandboxPlayback() {
    if (!state.sandboxData || state.sandboxPlaybackActive || state.sandboxScrubbing) return;
    const total = currentSandboxStepCount();
    if (total <= 0) return;
    if (state.sandboxTimelineProgress >= total) {
      renderSandboxProgress({ progress: 0, syncState: true });
    }

    const token = state.sandboxPlaybackToken + 1;
    state.sandboxPlaybackToken = token;
    state.sandboxPlaybackActive = true;
    updateSandboxControls();

    while (state.sandboxPlaybackActive && token === state.sandboxPlaybackToken) {
      const nowTotal = currentSandboxStepCount();
      if (state.sandboxTimelineProgress >= nowTotal - 0.000001) break;
      if (state.sandboxBusy || state.sandboxScrubbing) {
        const ok = await sleepWithToken(12, token);
        if (!ok) return;
        continue;
      }

      const stepIndex = state.sandboxCursorStepIndex;
      if (stepIndex >= nowTotal) break;
      const step = state.sandboxData.move_steps?.[stepIndex] || [];
      const durationMs = sandboxStepDurationMs(step);
      const moved = await moveSandboxBy(1, { animate: true, durationMs });
      if (!moved || token !== state.sandboxPlaybackToken || !state.sandboxPlaybackActive) {
        break;
      }
      if (state.sandboxTimelineProgress >= nowTotal - 0.000001) {
        break;
      }
      const pauseOk = await sleepWithToken(sandboxInterMovePauseMs(), token);
      if (!pauseOk) return;
    }

    if (token !== state.sandboxPlaybackToken) return;
    state.sandboxPlaybackActive = false;
    if (state.sandboxTimelineProgress >= currentSandboxStepCount() - 0.000001) {
      renderSandboxProgress({ progress: 0, syncState: true });
    }
    updateSandboxControls();
  }

  function toggleSandboxPlayback() {
    if (state.sandboxPlaybackActive) {
      stopSandboxPlayback();
      return;
    }
    void startSandboxPlayback();
  }

  async function apiGet(url) {
    const res = await fetch(url);
    const payload = await res.json();
    if (!res.ok || !payload.ok) {
      throw new Error(payload.detail || payload.error?.message || "Request failed");
    }
    return payload.data;
  }

  async function apiPost(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await res.json();
    if (!res.ok || !payload.ok) {
      throw new Error(payload.detail || payload.error?.message || "Request failed");
    }
    return payload.data;
  }

  async function apiDelete(url) {
    const res = await fetch(url, { method: "DELETE" });
    const payload = await res.json();
    if (!res.ok || !payload.ok) {
      throw new Error(payload.detail || payload.error?.message || "Request failed");
    }
    return payload.data;
  }

  async function apiPatch(url, body) {
    const res = await fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await res.json();
    if (!res.ok || !payload.ok) {
      throw new Error(payload.detail || payload.error?.message || "Request failed");
    }
    return payload.data;
  }

  function showToast(message) {
    DOM.toast.textContent = message;
    DOM.toast.classList.add("show");
    setTimeout(() => DOM.toast.classList.remove("show"), 1800);
  }

  function tileTitle(item) {
    return String(
      item.tile_title ||
        item.display_name ||
        item.title ||
        item.case_code ||
        (item.case_number != null ? `${item.group} #${item.case_number}` : "Case")
    );
  }

  function detailTitle(item) {
    return String(
      item.detail_title ||
        item.title ||
        item.display_name ||
        (item.case_number != null ? `${item.group} #${item.case_number}` : item.case_code || "Case")
    );
  }

  function caseShortLabel(item) {
    if (item.case_number != null) return `${item.group} #${item.case_number}`;
    return item.case_code || "-";
  }

  function groupBySubgroup(items) {
    return items.reduce((acc, item) => {
      const key = item.subgroup_title || `${item.group} Cases`;
      if (!acc[key]) acc[key] = [];
      acc[key].push(item);
      return acc;
    }, {});
  }

  function patchCaseInState(updated) {
    const idx = state.cases.findIndex((item) => item.id === updated.id);
    if (idx >= 0) state.cases[idx] = { ...state.cases[idx], ...updated };
  }

  function setActiveTab(category) {
    document.querySelectorAll(".nav-tab").forEach((tab) => {
      tab.classList.toggle("active", String(tab.dataset.category || "").toUpperCase() === category);
    });
    syncProgressSortToggle();
  }

  function syncProgressSortToggle() {
    if (!DOM.sortProgressToggle) return;
    DOM.sortProgressToggle.checked = Boolean(state.progressSortByGroup[state.category]);
  }

  function caseSortRank(item) {
    const status = String(item?.status || "NEW");
    return STATUS_SORT_RANK[status] ?? 1;
  }

  function sortCasesForCatalog(cases) {
    const sorted = [...cases];
    if (!state.progressSortByGroup[state.category]) return sorted;
    sorted.sort((a, b) => {
      const rankDiff = caseSortRank(a) - caseSortRank(b);
      if (rankDiff !== 0) return rankDiff;

      const aNum = Number.isFinite(Number(a.case_number)) ? Number(a.case_number) : Number.MAX_SAFE_INTEGER;
      const bNum = Number.isFinite(Number(b.case_number)) ? Number(b.case_number) : Number.MAX_SAFE_INTEGER;
      if (aNum !== bNum) return aNum - bNum;

      const codeA = String(a.case_code || "");
      const codeB = String(b.case_code || "");
      return codeA.localeCompare(codeB);
    });
    return sorted;
  }

  function appendRecognizerPreview(container, item) {
    if (item.recognizer_url) {
      const img = document.createElement("img");
      const sep = item.recognizer_url.includes("?") ? "&" : "?";
      img.src = `${item.recognizer_url}${sep}v=${RECOGNIZER_CACHE_BUSTER}`;
      img.alt = `${item.case_code} recognizer`;
      container.appendChild(img);
      return;
    }
    container.textContent = "No image";
    container.classList.add("catalog-preview-empty");
  }

  function tokenizeFormula(formula) {
    return String(formula || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
  }

  function nextProgressStatus(status) {
    const normalized = String(status || "NEW").toUpperCase();
    const idx = STATUS_CYCLE.indexOf(normalized);
    if (idx < 0) return STATUS_CYCLE[0];
    return STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
  }

  async function updateCatalogCaseProgress(caseId, currentStatus) {
    const id = Number(caseId);
    if (!Number.isFinite(id) || id <= 0) return;
    if (state.pendingStatusByCase.has(id)) return;

    const nextStatus = nextProgressStatus(currentStatus);
    state.pendingStatusByCase.add(id);
    renderCatalog();
    try {
      const updated = await apiPatch(`/api/cases/${id}/progress`, { status: nextStatus });
      patchCaseInState(updated);
      if (state.activeCaseId === id) {
        state.activeCase = updated;
        updateDetailsPaneState();
      }
      renderCatalog();
    } catch (error) {
      showToast(String(error.message || error));
      renderCatalog();
    } finally {
      state.pendingStatusByCase.delete(id);
      renderCatalog();
    }
  }

  function renderActiveAlgorithmDisplay(formula) {
    DOM.activeAlgoDisplay.innerHTML = "";
    const timelineSteps = Array.isArray(state.sandboxData?.highlight_by_step)
      ? state.sandboxData.highlight_by_step.filter((step) => String(step || "").trim())
      : [];
    if (timelineSteps.length) {
      const chunk = 8;
      for (let offset = 0; offset < timelineSteps.length; offset += chunk) {
        const row = document.createElement("div");
        row.className = "algo-line";
        timelineSteps.slice(offset, offset + chunk).forEach((stepLabel, localIndex) => {
          const stepIndex = offset + localIndex;
          const tile = document.createElement("button");
          const inverse = String(stepLabel).includes("'");
          tile.className = `move-tile ${inverse ? "inverse" : "base"}`;
          tile.type = "button";
          tile.textContent = stepLabel;
          tile.setAttribute("data-step-index", String(stepIndex));
          tile.title = `Go to step ${stepIndex + 1}`;
          tile.setAttribute("aria-label", `Go to step ${stepIndex + 1}`);
          tile.addEventListener("click", () => {
            stopSandboxPlayback({ silent: true, forceUpdate: true });
            sandboxSetStep(stepIndex);
          });
          row.appendChild(tile);
        });
        DOM.activeAlgoDisplay.appendChild(row);
      }
      updateActiveAlgorithmStepHighlight();
      return;
    }

    const moves = tokenizeFormula(formula);
    if (!moves.length) {
      DOM.activeAlgoDisplay.innerHTML = '<div class="algo-placeholder">No algorithm selected</div>';
      return;
    }

    const first = moves.slice(0, 8);
    const second = moves.slice(8);
    const lines = [first];
    if (second.length) lines.push(second);

    lines.forEach((lineMoves) => {
      const row = document.createElement("div");
      row.className = "algo-line";
      lineMoves.forEach((move) => {
        const tile = document.createElement("span");
        const inverse = move.includes("'");
        tile.className = `move-tile ${inverse ? "inverse" : "base"}`;
        tile.textContent = move;
        row.appendChild(tile);
      });
      DOM.activeAlgoDisplay.appendChild(row);
    });
    updateActiveAlgorithmStepHighlight();
  }

  function syncActiveAlgorithmSummary(formula, mode = "algorithm") {
    // Summary line removed from layout; keep function for compatibility with previous flow.
    void formula;
    void mode;
  }

  function setActiveDisplayFormula(formula, mode = "algorithm") {
    state.activeDisplayMode = mode;
    state.activeDisplayFormula = String(formula || "").trim();
    syncActiveAlgorithmSummary(state.activeDisplayFormula, state.activeDisplayMode);
    renderActiveAlgorithmDisplay(state.activeDisplayFormula);
    updateSandboxOverlay(currentCase());
  }

  function appendCatalogCard(grid, item) {
    const card = document.createElement("article");
    card.className = "catalog-card";
    card.setAttribute("data-testid", `case-card-${item.id}`);
    if (item.id === state.activeCaseId) card.classList.add("active");

    const status = isCaseQueued(item) ? "QUEUED" : String(item.status || "NEW");
    const statusPending = state.pendingStatusByCase.has(Number(item.id));
    card.innerHTML = `
      <button class="status-dot ${status}" type="button" title="Cycle status" aria-label="Cycle status" ${statusPending ? "disabled" : ""}></button>
      <div class="catalog-preview"></div>
      <div class="tile-title">${tileTitle(item)}</div>
    `;

    const preview = card.querySelector(".catalog-preview");
    appendRecognizerPreview(preview, item);
    const statusDot = card.querySelector(".status-dot");
    if (statusDot) {
      statusDot.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (status === "QUEUED") return;
        void updateCatalogCaseProgress(item.id, item.status);
      });
    }
    card.addEventListener("click", () => {
      void selectCase(item.id);
    });
    grid.appendChild(card);
  }

  function renderCatalog() {
    DOM.catalog.innerHTML = "";
    if (!state.cases.length) {
      const empty = document.createElement("div");
      empty.className = "catalog-empty";
      empty.textContent = "No cases in this group.";
      DOM.catalog.appendChild(empty);
      return;
    }

    if (state.progressSortByGroup[state.category]) {
      const grid = document.createElement("div");
      grid.className = "catalog-grid";
      sortCasesForCatalog(state.cases).forEach((item) => {
        appendCatalogCard(grid, item);
      });
      DOM.catalog.appendChild(grid);
      return;
    }

    const grouped = groupBySubgroup(state.cases);
    Object.entries(grouped).forEach(([subgroup, cases]) => {
      const section = document.createElement("section");
      section.className = "subgroup-section";

      const title = document.createElement("div");
      title.className = "subgroup-title";
      title.textContent = subgroup;
      section.appendChild(title);

      const grid = document.createElement("div");
      grid.className = "catalog-grid";

      sortCasesForCatalog(cases).forEach((item) => {
        appendCatalogCard(grid, item);
      });

      section.appendChild(grid);
      DOM.catalog.appendChild(section);
    });
  }

  function currentCase() {
    return state.activeCase;
  }

  function getServerActiveJob(caseItem) {
    return (caseItem?.jobs || []).find((job) => job.status === "PENDING" || job.status === "RUNNING") || null;
  }

  function getLocalPendingJob(caseItem) {
    if (!caseItem?.id) return null;
    const quality = state.localPendingByCase.get(caseItem.id);
    if (!quality) return null;
    return {
      id: null,
      quality,
      status: "PENDING",
      local: true,
    };
  }

  function getActiveJob(caseItem) {
    return getServerActiveJob(caseItem) || getLocalPendingJob(caseItem);
  }

  function getLatestFailedJob(caseItem) {
    return (caseItem?.jobs || []).find((job) => job.status === "FAILED") || null;
  }

  function isCaseQueued(item) {
    if (!item?.id) return false;
    if (state.localPendingByCase.has(item.id)) return true;
    if (state.activeCase && state.activeCase.id === item.id) {
      return Boolean(getServerActiveJob(state.activeCase));
    }
    return false;
  }

  function setVideoSource(videoEl, src) {
    if (!videoEl) return;
    const normalized = new URL(src, window.location.origin).href;
    if (videoEl.dataset.currentSrc !== normalized) {
      videoEl.src = src;
      videoEl.dataset.currentSrc = normalized;
    }
  }

  function clearVideoSource(videoEl) {
    if (!videoEl) return;
    videoEl.pause();
    videoEl.removeAttribute("src");
    delete videoEl.dataset.currentSrc;
  }

  function setDetailsDisabled() {
    DOM.mName.textContent = "Select Case";
    DOM.mCaseCode.textContent = "-";
    DOM.mProb.textContent = "Probability: n/a";
    clearVideoSource(DOM.mVideo);
    DOM.mQueueMsg.style.display = "flex";
    DOM.mQueueMsg.textContent = "Select case";
    DOM.mStatusGroup.querySelectorAll(".status-btn[data-status]").forEach((btn) => {
      btn.classList.remove("active");
      btn.disabled = true;
    });
    DOM.mAlgoList.innerHTML = '<div class="algo-empty">Select case to manage algorithms.</div>';
    setActiveDisplayFormula("", "algorithm");
    resetSandboxData();
    setPlaybackMode();
    updateSandboxOverlay(null);
  }

  function updateDetailsPaneState() {
    const c = currentCase();
    if (!c) {
      setDetailsDisabled();
      return;
    }

    DOM.mName.textContent = detailTitle(c);
    DOM.mProb.textContent = `Probability: ${c.probability_text || "n/a"}`;
    DOM.mCaseCode.textContent = [caseShortLabel(c), c.subgroup_title].filter(Boolean).join(" · ");
    const lockCustomPreview = state.activeDisplayMode === "custom" && isCustomFormulaInputFocused();
    if (lockCustomPreview) {
      syncActiveAlgorithmSummary(state.activeDisplayFormula || c.active_formula || "", "custom");
    } else {
      syncActiveAlgorithmSummary(c.active_formula || "", "algorithm");
    }

    DOM.mStatusGroup.querySelectorAll(".status-btn[data-status]").forEach((btn) => {
      btn.disabled = false;
      btn.classList.toggle("active", btn.dataset.status === c.status);
    });

    const hasSandbox = Boolean(state.sandboxData);
    DOM.mQueueMsg.style.display = hasSandbox ? "none" : "flex";
    DOM.mQueueMsg.textContent = hasSandbox ? "" : "Sandbox data not ready yet...";

    if (!lockCustomPreview) {
      setActiveDisplayFormula(c.active_formula || "", "algorithm");
    }

    renderAlgorithmsList(c);
    updateSandboxOverlay(c);
  }

  function renderAlgorithmsList(c) {
    const prevInput = DOM.mAlgoList.querySelector("#custom-formula-input");
    const prevValue = prevInput ? String(prevInput.value || "") : "";
    const prevFocused = prevInput ? document.activeElement === prevInput : false;
    const prevSelectionStart = prevInput && prevInput.selectionStart != null ? prevInput.selectionStart : null;
    const prevSelectionEnd = prevInput && prevInput.selectionEnd != null ? prevInput.selectionEnd : null;

    DOM.mAlgoList.innerHTML = "";
    const canDelete = (c.algorithms || []).length > 1;

    (c.algorithms || []).forEach((algo) => {
      const activeClass = algo.id === c.active_algorithm_id ? "algo-option-active" : "algo-option-inactive";
      const option = document.createElement("label");
      option.className = `algo-option ${activeClass}`;
      const checked = algo.id === c.active_algorithm_id ? "checked" : "";
      option.innerHTML = `
        <div class="algo-main">
          <input type="radio" name="algo_sel" value="${algo.id}" ${checked} class="algo-radio" data-testid="algo-radio-${algo.id}">
          <code>${algo.formula || "(empty)"}</code>
        </div>
        ${canDelete ? `<button class="algo-delete-btn" data-action="delete" data-testid="delete-algo-${algo.id}" type="button">Delete</button>` : ""}
      `;
      option.querySelector("input").addEventListener("change", async () => {
        try {
          setActiveDisplayFormula(algo.formula || "", "algorithm");
          await activateAlgorithm(c.id, algo.id);
        } catch (error) {
          showToast(String(error.message || error));
        }
      });

      const deleteBtn = option.querySelector("[data-action='delete']");
      if (deleteBtn) {
        deleteBtn.addEventListener("click", async (event) => {
          event.preventDefault();
          event.stopPropagation();
          const confirmed = window.confirm("Delete this algorithm and its cached renders?");
          if (!confirmed) return;
          try {
            await deleteAlgorithm(c.id, algo.id);
          } catch (error) {
            showToast(String(error.message || error));
          }
        });
      }
      DOM.mAlgoList.appendChild(option);
    });

    const customWrap = document.createElement("div");
    customWrap.className = "custom-algo-form";
    customWrap.innerHTML = `
      <input id="custom-formula-input" data-testid="custom-formula-input" type="text" placeholder="Enter custom algorithm..." class="custom-formula-input" />
      <button id="custom-formula-apply" data-testid="custom-formula-apply" type="button" class="custom-formula-apply">Use</button>
    `;

    const input = customWrap.querySelector("#custom-formula-input");
    const applyBtn = customWrap.querySelector("#custom-formula-apply");

    input.value = prevValue;
    if (prevFocused) {
      input.focus();
      if (prevSelectionStart != null && prevSelectionEnd != null) {
        input.setSelectionRange(prevSelectionStart, prevSelectionEnd);
      }
    }

    const submitCustom = async () => {
      const formula = String(input.value || "").trim();
      if (!formula) {
        showToast("Formula is empty");
        return;
      }
      try {
        const updated = await apiPost(`/api/cases/${c.id}/alternatives`, { formula, activate: true });
        state.activeCase = updated;
        patchCaseInState(updated);
        await loadSandboxForCurrentCase();
        renderCatalog();
        updateDetailsPaneState();
      } catch (error) {
        showToast(String(error.message || error));
      }
    };

    applyBtn.addEventListener("click", () => {
      void submitCustom();
    });

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        void submitCustom();
      }
    });

    input.addEventListener("input", () => {
      const liveFormula = String(input.value || "");
      setActiveDisplayFormula(liveFormula, "custom");
    });

    input.addEventListener("blur", () => {
      const activeCase = currentCase();
      if (!activeCase) return;
      if (!String(input.value || "").trim()) {
        setActiveDisplayFormula(activeCase.active_formula || "", "algorithm");
      }
    });

    DOM.mAlgoList.appendChild(customWrap);
  }

  function isCustomFormulaInputFocused() {
    const input = DOM.mAlgoList.querySelector("#custom-formula-input");
    return Boolean(input) && document.activeElement === input;
  }

  async function selectCase(caseId) {
    state.activeCaseId = caseId;
    const details = await apiGet(`/api/cases/${caseId}`);
    state.activeCase = details;
    state.activeDisplayMode = "algorithm";
    state.activeDisplayFormula = details.active_formula || "";
    await loadSandboxForCurrentCase();
    patchCaseInState(details);
    renderCatalog();
    updateDetailsPaneState();
  }

  async function activateAlgorithm(caseId, algorithmId) {
    const updated = await apiPost(`/api/cases/${caseId}/active-algorithm`, { algorithm_id: algorithmId });
    state.activeCase = updated;
    await loadSandboxForCurrentCase();
    patchCaseInState(updated);
    renderCatalog();
    updateDetailsPaneState();
    showToast("Active algorithm updated");
  }

  async function deleteAlgorithm(caseId, algorithmId) {
    const payload = await apiDelete(`/api/cases/${caseId}/alternatives/${algorithmId}?purge_media=true`);
    state.activeCase = payload.case;
    await loadSandboxForCurrentCase();
    patchCaseInState(payload.case);
    renderCatalog();
    updateDetailsPaneState();
    showToast("Algorithm deleted");
  }

  async function updateProgress(status) {
    const c = currentCase();
    if (!c || !c.active_algorithm_id) return;
    await apiPatch(`/api/cases/${c.id}/progress`, { status });
    const updated = await apiGet(`/api/cases/${c.id}`);
    state.activeCase = updated;
    patchCaseInState(updated);
    renderCatalog();
    updateDetailsPaneState();
  }

  async function queueRender(quality) {
    const c = currentCase();
    if (!c) return;

    state.localPendingByCase.set(c.id, quality);
    renderCatalog();
    updateDetailsPaneState();

    try {
      const response = await apiPost(`/api/cases/${c.id}/renders`, { quality });
      if (response.reused || response.job?.status === "DONE") {
        state.localPendingByCase.delete(c.id);
        showToast("Reused existing render");
      } else {
        showToast("Job added to queue");
      }

      const updated = await apiGet(`/api/cases/${c.id}`);
      state.activeCase = updated;
      patchCaseInState(updated);
      if (!getServerActiveJob(updated) && response.job?.status === "DONE") {
        state.localPendingByCase.delete(updated.id);
      }
      renderCatalog();
      updateDetailsPaneState();
    } catch (error) {
      state.localPendingByCase.delete(c.id);
      renderCatalog();
      updateDetailsPaneState();
      throw error;
    }
  }

  async function loadCatalog() {
    const data = await apiGet(`/api/cases?group=${encodeURIComponent(state.category)}`);
    state.cases = Array.isArray(data) ? data : [];

    if (!state.cases.length) {
      state.activeCaseId = null;
      state.activeCase = null;
      resetSandboxData();
      renderCatalog();
      updateDetailsPaneState();
      return;
    }

    if (state.activeCaseId == null || !state.cases.some((item) => item.id === state.activeCaseId)) {
      await selectCase(state.cases[0].id);
      return;
    }

    const updated = await apiGet(`/api/cases/${state.activeCaseId}`);
    state.activeCase = updated;
    await loadSandboxForCurrentCase();
    patchCaseInState(updated);
    renderCatalog();
    updateDetailsPaneState();
  }

  async function pollQueue() {
    const c = currentCase();
    if (!c || isCustomFormulaInputFocused()) {
      scheduleNextPoll();
      return;
    }

    try {
      const updated = await apiGet(`/api/cases/${c.id}`);
      state.activeCase = updated;
      patchCaseInState(updated);
      renderCatalog();
      updateDetailsPaneState();
      markPollSuccess();
    } catch (error) {
      markPollFailure();
    }
    scheduleNextPoll();
  }

  function setupEventListeners() {
    DOM.sandboxToStartBtn?.addEventListener("click", () => {
      stopSandboxPlayback({ silent: true });
      sandboxToStart();
    });
    DOM.sandboxPrevBtn?.addEventListener("click", () => {
      void sandboxStepBackward();
    });
    DOM.sandboxPlayPauseBtn?.addEventListener("click", () => {
      toggleSandboxPlayback();
    });
    DOM.sandboxNextBtn?.addEventListener("click", () => {
      void sandboxStepForward();
    });
    if (DOM.sandboxTimelineSlider) {
      const finishScrub = () => {
        if (!state.sandboxScrubbing) return;
        void finishSandboxScrubbing(DOM.sandboxTimelineSlider.value);
      };
      DOM.sandboxTimelineSlider.addEventListener("pointerdown", () => {
        beginSandboxScrubbing();
      });
      DOM.sandboxTimelineSlider.addEventListener("input", (event) => {
        const target = event.currentTarget;
        if (!(target instanceof HTMLInputElement)) return;
        if (!state.sandboxScrubbing) {
          beginSandboxScrubbing();
        }
        queueTimelinePreview(target.value);
      });
      DOM.sandboxTimelineSlider.addEventListener("change", finishScrub);
      window.addEventListener("pointerup", finishScrub);
    }
    const onSpeedClick = (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const speedBtn = target.closest(".sandbox-speed-btn");
      if (!speedBtn) return;
      setSandboxPlaybackSpeed(speedBtn.dataset.speed || "1");
    };
    DOM.sandboxFrame?.addEventListener("click", onSpeedClick);
    sandboxSpeedButtons().forEach((btn) => {
      btn.addEventListener("click", onSpeedClick);
    });

    if (DOM.sortProgressToggle) {
      DOM.sortProgressToggle.addEventListener("change", (event) => {
        const enabled = Boolean(event.currentTarget.checked);
        state.progressSortByGroup[state.category] = enabled;
        saveProgressSortMap(state.progressSortByGroup);
        renderCatalog();
      });
    }

    document.querySelectorAll(".nav-tab").forEach((tab) => {
      tab.addEventListener("click", async (event) => {
        const category = String(event.currentTarget.dataset.category || "").toUpperCase();
        if (!GROUPS.includes(category) || category === state.category) return;
        state.category = category;
        state.activeCaseId = null;
        state.activeCase = null;
        setActiveTab(category);
        await loadCatalog();
      });
    });

    DOM.mStatusGroup.querySelectorAll(".status-btn[data-status]").forEach((btn) => {
      btn.addEventListener("click", async (event) => {
        const status = String(event.currentTarget.dataset.status || "");
        if (!status) return;
        try {
          await updateProgress(status);
        } catch (error) {
          showToast(String(error.message || error));
        }
      });
    });

    document.addEventListener("keydown", (event) => {
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.closest("input[type='text']") || target.closest("textarea") || target.isContentEditable)
      ) {
        return;
      }
      if (!state.sandboxData) return;
      if (event.repeat && event.code === "Space") return;

      if (event.code === "Space") {
        event.preventDefault();
        toggleSandboxPlayback();
        return;
      }
      if (event.code === "ArrowLeft") {
        event.preventDefault();
        stopSandboxPlayback({ silent: true, forceUpdate: true });
        void sandboxStepBackward();
        return;
      }
      if (event.code === "ArrowRight") {
        event.preventDefault();
        stopSandboxPlayback({ silent: true, forceUpdate: true });
        void sandboxStepForward();
        return;
      }
      if (event.code === "KeyR") {
        event.preventDefault();
        stopSandboxPlayback({ silent: true, forceUpdate: true });
        sandboxToStart();
      }
    });

  }

  async function init() {
    if (window.CubeSandbox3D?.createSandbox3D && DOM.sandboxCanvas) {
      state.sandboxPlayer = window.CubeSandbox3D.createSandbox3D(DOM.sandboxCanvas);
      window.addEventListener("resize", () => {
        state.sandboxPlayer?.resize();
      });
    }
    setActiveTab(state.category);
    setupEventListeners();
    setPlaybackMode();
    updateSandboxControls();
    syncProgressSortToggle();
    await loadCatalog();

    scheduleNextPoll();
  }

  void init();
})();
