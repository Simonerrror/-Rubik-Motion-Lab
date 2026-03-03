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
    activeDisplayMode: "algorithm",
    activeDisplayFormula: "",
    pollTimer: null,
    pollBackoffIndex: 0,
    pollOutageNotified: false,
    progressSortByGroup: loadProgressSortMap(),
    playbackMode: "video",
    sandboxData: null,
    sandboxStepIndex: 0,
    sandboxRequestToken: 0,
    sandboxPlayer: null,
    sandboxBusy: false,
    sandboxPlaybackSpeed: 1,
    sandboxPlaybackActive: false,
    sandboxPlaybackToken: 0,
    sandboxPlaybackConfig: { ...DEFAULT_SANDBOX_PLAYBACK_CONFIG },
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
    sandboxStepLabel: document.getElementById("sandbox-step-label"),
    mStatusGroup: document.getElementById("m-status-group"),
    mAlgoList: document.getElementById("m-algo-list"),
    activeAlgoDisplay: document.getElementById("active-algo-display"),
    mRenderDraftBtn: document.getElementById("m-render-draft-btn"),
    mRenderBtn: document.getElementById("m-render-btn"),
    toast: document.getElementById("toast"),
  };

  function sandboxSpeedButtons() {
    return Array.from(document.querySelectorAll(".sandbox-speed-btn"));
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

  function setPlaybackMode(mode) {
    const normalized = mode === "sandbox" ? "sandbox" : "video";
    state.playbackMode = normalized;

    const videoActive = normalized === "video";
    DOM.modeVideoBtn?.classList.toggle("active", videoActive);
    DOM.modeSandboxBtn?.classList.toggle("active", !videoActive);
    DOM.mVideo?.classList.toggle("hidden", !videoActive);
    DOM.sandboxFrame?.classList.toggle("hidden", videoActive);

    if (videoActive) {
      stopSandboxPlayback({ silent: true });
    } else if (state.sandboxPlayer) {
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

  function stepLabelText() {
    const total = currentSandboxStepCount();
    const index = Math.min(Math.max(state.sandboxStepIndex, 0), total);
    if (!total) return "Step 0/0";
    if (index === 0) return `Step 0/${total} · Start`;
    const label = state.sandboxData?.highlight_by_step?.[index - 1] || "";
    return label ? `Step ${index}/${total} · ${label}` : `Step ${index}/${total}`;
  }

  function renderSandboxStep(options = {}) {
    if (!state.sandboxData) {
      DOM.sandboxStepLabel.textContent = "Step 0/0";
      return;
    }

    const syncState = options.syncState !== false;
    const total = currentSandboxStepCount();
    state.sandboxStepIndex = Math.min(Math.max(state.sandboxStepIndex, 0), total);
    const nextState = state.sandboxData.states_by_step?.[state.sandboxStepIndex] || "";
    if (syncState && state.sandboxPlayer && nextState) {
      state.sandboxPlayer.setState(nextState);
    }
    DOM.sandboxStepLabel.textContent = stepLabelText();
    updateSandboxControls();
  }

  function updateSandboxControls() {
    const hasTimeline = Boolean(state.sandboxData);
    const total = currentSandboxStepCount();
    const atStart = state.sandboxStepIndex <= 0;
    const atEnd = state.sandboxStepIndex >= total;
    const locked = state.sandboxBusy || state.sandboxPlaybackActive;

    if (DOM.sandboxToStartBtn) {
      DOM.sandboxToStartBtn.disabled = !hasTimeline || atStart || locked;
    }
    if (DOM.sandboxPrevBtn) {
      DOM.sandboxPrevBtn.disabled = !hasTimeline || atStart || locked;
    }
    if (DOM.sandboxPlayPauseBtn) {
      DOM.sandboxPlayPauseBtn.disabled = !hasTimeline || total === 0;
      DOM.sandboxPlayPauseBtn.textContent = state.sandboxPlaybackActive ? "Pause" : "Play";
    }
    if (DOM.sandboxNextBtn) {
      DOM.sandboxNextBtn.disabled = !hasTimeline || atEnd || locked;
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
  }

  function resetSandboxData() {
    stopSandboxPlayback({ silent: true });
    state.sandboxData = null;
    state.sandboxStepIndex = 0;
    state.sandboxBusy = false;
    state.sandboxPlaybackConfig = { ...DEFAULT_SANDBOX_PLAYBACK_CONFIG };
    if (state.sandboxPlayer) {
      state.sandboxPlayer.setSlots([]);
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

      state.sandboxData = sandbox;
      state.sandboxStepIndex = 0;
      state.sandboxBusy = false;
      stopSandboxPlayback({ silent: true });
      state.sandboxPlaybackConfig = normalizeSandboxPlaybackConfig(sandbox.playback_config);
      if (state.sandboxPlayer) {
        state.sandboxPlayer.setSlots(Array.isArray(sandbox.state_slots) ? sandbox.state_slots : []);
        if (state.playbackMode === "sandbox") {
          window.requestAnimationFrame(() => {
            state.sandboxPlayer?.resize();
            renderSandboxStep();
          });
        }
      }
      renderSandboxStep();
    } catch (error) {
      if (requestToken !== state.sandboxRequestToken) return;
      resetSandboxData();
      setPlaybackMode("video");
      showToast(`Sandbox unavailable: ${String(error.message || error)}`);
    }
  }

  async function moveSandboxBy(delta, options = {}) {
    if (!state.sandboxData || state.sandboxBusy) return;

    const total = currentSandboxStepCount();
    const currentIndex = state.sandboxStepIndex;
    const targetIndex = Math.min(Math.max(currentIndex + delta, 0), total);
    if (targetIndex === currentIndex) return;

    const forward = delta > 0;
    const stepIndex = forward ? currentIndex : currentIndex - 1;
    const moveStep = Array.isArray(state.sandboxData.move_steps?.[stepIndex])
      ? state.sandboxData.move_steps[stepIndex]
      : [];
    const animate = options.animate !== false;
    const durationMs = Number(options.durationMs) || sandboxStepDurationMs(moveStep);

    state.sandboxBusy = true;
    updateSandboxControls();

    let animated = false;
    try {
      if (animate && state.sandboxPlayer?.playStep && moveStep.length) {
        animated = await state.sandboxPlayer.playStep(moveStep, {
          reverse: !forward,
          durationMs,
          easing: state.sandboxPlaybackConfig.rate_func,
        });
      }
    } catch (error) {
      console.warn(error);
    }

    state.sandboxStepIndex = targetIndex;
    state.sandboxBusy = false;

    if (animated) {
      DOM.sandboxStepLabel.textContent = stepLabelText();
      updateSandboxControls();
      return true;
    }
    renderSandboxStep();
    return true;
  }

  function sandboxSetStep(index) {
    if (!state.sandboxData || state.sandboxBusy) return;
    const total = currentSandboxStepCount();
    state.sandboxStepIndex = Math.min(Math.max(index, 0), total);
    renderSandboxStep();
  }

  function sandboxToStart() {
    if (!state.sandboxData || state.sandboxBusy) return;
    sandboxSetStep(0);
  }

  async function sandboxStepBackward() {
    if (!state.sandboxData || state.sandboxBusy || state.sandboxPlaybackActive) return;
    await moveSandboxBy(-1, { animate: true });
  }

  async function sandboxStepForward() {
    if (!state.sandboxData || state.sandboxBusy || state.sandboxPlaybackActive) return;
    await moveSandboxBy(1, { animate: true });
  }

  async function startSandboxPlayback() {
    if (!state.sandboxData || state.sandboxPlaybackActive) return;
    const total = currentSandboxStepCount();
    if (total <= 0) return;
    if (state.sandboxStepIndex >= total) {
      sandboxSetStep(0);
    }

    const token = state.sandboxPlaybackToken + 1;
    state.sandboxPlaybackToken = token;
    state.sandboxPlaybackActive = true;
    updateSandboxControls();

    while (state.sandboxPlaybackActive && token === state.sandboxPlaybackToken) {
      const nowTotal = currentSandboxStepCount();
      if (state.sandboxStepIndex >= nowTotal) break;
      if (state.sandboxBusy) {
        const ok = await sleepWithToken(12, token);
        if (!ok) return;
        continue;
      }

      const step = state.sandboxData.move_steps?.[state.sandboxStepIndex] || [];
      const durationMs = sandboxStepDurationMs(step);
      const moved = await moveSandboxBy(1, { animate: true, durationMs });
      if (!moved || token !== state.sandboxPlaybackToken || !state.sandboxPlaybackActive) {
        break;
      }
      if (state.sandboxStepIndex >= nowTotal) {
        break;
      }
      const pauseOk = await sleepWithToken(sandboxInterMovePauseMs(), token);
      if (!pauseOk) return;
    }

    if (token !== state.sandboxPlaybackToken) return;
    state.sandboxPlaybackActive = false;
    if (state.sandboxStepIndex >= currentSandboxStepCount()) {
      sandboxSetStep(0);
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

  function renderActiveAlgorithmDisplay(formula) {
    DOM.activeAlgoDisplay.innerHTML = "";
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
  }

  function appendCatalogCard(grid, item) {
    const card = document.createElement("article");
    card.className = "catalog-card";
    card.setAttribute("data-testid", `case-card-${item.id}`);
    if (item.id === state.activeCaseId) card.classList.add("active");

    const status = isCaseQueued(item) ? "QUEUED" : String(item.status || "NEW");
    card.innerHTML = `
      <div class="status-dot ${status}"></div>
      <div class="catalog-preview"></div>
      <div class="tile-title">${tileTitle(item)}</div>
    `;

    const preview = card.querySelector(".catalog-preview");
    appendRecognizerPreview(preview, item);
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
    const normalized = new URL(src, window.location.origin).href;
    if (videoEl.dataset.currentSrc !== normalized) {
      videoEl.src = src;
      videoEl.dataset.currentSrc = normalized;
    }
  }

  function clearVideoSource(videoEl) {
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
    DOM.mRenderDraftBtn.disabled = true;
    DOM.mRenderDraftBtn.textContent = "Generate Draft";
    DOM.mRenderDraftBtn.classList.remove("render-busy");
    DOM.mRenderBtn.disabled = true;
    DOM.mRenderBtn.textContent = "Request HD Render";
    DOM.mRenderBtn.classList.remove("render-busy");
    DOM.mStatusGroup.querySelectorAll(".status-btn[data-status]").forEach((btn) => {
      btn.classList.remove("active");
      btn.disabled = true;
    });
    DOM.mAlgoList.innerHTML = '<div class="algo-empty">Select case to manage algorithms.</div>';
    setActiveDisplayFormula("", "algorithm");
    resetSandboxData();
    setPlaybackMode("video");
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

    const draftArtifact = c.artifacts?.draft || null;
    const highArtifact = c.artifacts?.high || null;
    const serverActiveJob = getServerActiveJob(c);
    if (serverActiveJob && c.id != null) {
      state.localPendingByCase.delete(c.id);
    }
    const activeJob = serverActiveJob || getLocalPendingJob(c);
    const latestFailedJob = getLatestFailedJob(c);
    const videoUrl = highArtifact?.video_url || draftArtifact?.video_url || null;

    if (videoUrl) {
      setVideoSource(DOM.mVideo, videoUrl);
      DOM.mQueueMsg.style.display = state.playbackMode === "video" && activeJob ? "flex" : "none";
      DOM.mQueueMsg.textContent = activeJob ? `Render queued (${activeJob.quality})...` : "";
    } else {
      clearVideoSource(DOM.mVideo);
      DOM.mQueueMsg.style.display = state.playbackMode === "video" ? "flex" : "none";
      if (activeJob) {
        DOM.mQueueMsg.textContent = `Render queued (${activeJob.quality})...`;
      } else if (latestFailedJob) {
        DOM.mQueueMsg.textContent = "Render failed. Check worker logs and retry.";
      } else {
        DOM.mQueueMsg.textContent = "Video not rendered yet...";
      }
    }

    DOM.mStatusGroup.querySelectorAll(".status-btn[data-status]").forEach((btn) => {
      btn.disabled = false;
      btn.classList.toggle("active", btn.dataset.status === c.status);
    });

    DOM.mRenderDraftBtn.disabled = Boolean(activeJob) || !c.active_algorithm_id;
    DOM.mRenderBtn.disabled = Boolean(activeJob) || !draftArtifact || Boolean(highArtifact) || !c.active_algorithm_id;
    DOM.mRenderDraftBtn.classList.remove("render-busy");
    DOM.mRenderBtn.classList.remove("render-busy");

    if (activeJob?.quality === "draft") {
      DOM.mRenderDraftBtn.textContent = "Draft Queued...";
      DOM.mRenderDraftBtn.classList.add("render-busy");
    } else {
      DOM.mRenderDraftBtn.textContent = "Generate Draft";
    }

    if (highArtifact) {
      DOM.mRenderBtn.textContent = "HD Ready";
    } else if (activeJob?.quality === "high") {
      DOM.mRenderBtn.textContent = "HD Queued...";
      DOM.mRenderBtn.classList.add("render-busy");
    } else {
      DOM.mRenderBtn.textContent = "Request HD Render";
    }

    if (!lockCustomPreview) {
      setActiveDisplayFormula(c.active_formula || "", "algorithm");
    }

    renderAlgorithmsList(c);
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
      const status = await apiGet(`/api/cases/${c.id}/renders/status`);
      const previousActiveJob = getActiveJob(c);
      const nextActiveJob = (status.jobs || []).find((job) => job.status === "PENDING" || job.status === "RUNNING") || null;
      const justCompleted = previousActiveJob && !nextActiveJob;

      const updated = await apiGet(`/api/cases/${c.id}`);
      state.activeCase = updated;
      patchCaseInState(updated);
      renderCatalog();
      updateDetailsPaneState();

      if (justCompleted) {
        showToast("Render finished");
      }
      markPollSuccess();
    } catch (error) {
      markPollFailure();
    }
    scheduleNextPoll();
  }

  function setupEventListeners() {
    DOM.modeVideoBtn?.addEventListener("click", () => {
      setPlaybackMode("video");
      updateDetailsPaneState();
    });
    DOM.modeSandboxBtn?.addEventListener("click", () => {
      if (!state.sandboxData) {
        showToast("Sandbox data not ready yet");
        return;
      }
      setPlaybackMode("sandbox");
      updateDetailsPaneState();
      // Always enter sandbox from the canonical starting position.
      sandboxSetStep(0);
    });
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

    DOM.mRenderDraftBtn.addEventListener("click", async () => {
      try {
        await queueRender("draft");
      } catch (error) {
        showToast(String(error.message || error));
      }
    });

    DOM.mRenderBtn.addEventListener("click", async () => {
      const c = currentCase();
      if (!c?.artifacts?.draft) {
        showToast("Draft is required before HD render");
        return;
      }
      const confirmed = window.confirm("Start HD render?");
      if (!confirmed) return;
      try {
        await queueRender("high");
      } catch (error) {
        showToast(String(error.message || error));
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
    setPlaybackMode("video");
    updateSandboxControls();
    syncProgressSortToggle();
    await loadCatalog();

    scheduleNextPoll();
  }

  void init();
})();
