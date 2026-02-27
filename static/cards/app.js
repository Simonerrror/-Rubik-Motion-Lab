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
  };

  const DOM = {
    catalog: document.getElementById("catalog-container"),
    sortProgressToggle: document.getElementById("sort-progress-toggle"),
    mName: document.getElementById("m-name"),
    mProb: document.getElementById("m-prob"),
    mCaseCode: document.getElementById("m-case-code"),
    mVideo: document.getElementById("m-video"),
    mQueueMsg: document.getElementById("m-queue-msg"),
    mStatusGroup: document.getElementById("m-status-group"),
    mAlgoList: document.getElementById("m-algo-list"),
    activeAlgoDisplay: document.getElementById("active-algo-display"),
    mRenderDraftBtn: document.getElementById("m-render-draft-btn"),
    mRenderBtn: document.getElementById("m-render-btn"),
    toast: document.getElementById("toast"),
  };

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
      DOM.mQueueMsg.style.display = activeJob ? "flex" : "none";
      DOM.mQueueMsg.textContent = activeJob ? `Render queued (${activeJob.quality})...` : "";
    } else {
      clearVideoSource(DOM.mVideo);
      DOM.mQueueMsg.style.display = "flex";
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
    patchCaseInState(details);
    renderCatalog();
    updateDetailsPaneState();
  }

  async function activateAlgorithm(caseId, algorithmId) {
    const updated = await apiPost(`/api/cases/${caseId}/active-algorithm`, { algorithm_id: algorithmId });
    state.activeCase = updated;
    patchCaseInState(updated);
    renderCatalog();
    updateDetailsPaneState();
    showToast("Active algorithm updated");
  }

  async function deleteAlgorithm(caseId, algorithmId) {
    const payload = await apiDelete(`/api/cases/${caseId}/alternatives/${algorithmId}?purge_media=true`);
    state.activeCase = payload.case;
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
    setActiveTab(state.category);
    setupEventListeners();
    syncProgressSortToggle();
    await loadCatalog();

    scheduleNextPoll();
  }

  void init();
})();
