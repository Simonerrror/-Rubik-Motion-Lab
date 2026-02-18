(() => {
  const GROUPS = ["F2L", "OLL", "PLL"];

  const state = {
    category: "OLL",
    cases: [],
    activeCaseId: null,
    activeCase: null,
    pollHandle: null,
  };

  const DOM = {
    catalog: document.getElementById("catalog-container"),
    backdrop: document.getElementById("modal-backdrop"),
    mName: document.getElementById("m-name"),
    mProb: document.getElementById("m-prob"),
    mCaseCode: document.getElementById("m-case-code"),
    mVideo: document.getElementById("m-video"),
    mQueueMsg: document.getElementById("m-queue-msg"),
    mStatusGroup: document.getElementById("m-status-group"),
    mAlgoList: document.getElementById("m-algo-list"),
    mRenderDraftBtn: document.getElementById("m-render-draft-btn"),
    mRenderBtn: document.getElementById("m-render-btn"),
    mClose: document.getElementById("m-close"),
    toast: document.getElementById("toast"),
  };

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

  function showToast(message) {
    DOM.toast.textContent = message;
    DOM.toast.classList.add("show");
    setTimeout(() => DOM.toast.classList.remove("show"), 1800);
  }

  function caseDisplayName(item) {
    if (item.case_number != null) return `${item.group} #${item.case_number}`;
    return item.title || item.case_code;
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

  async function loadCatalog() {
    const data = await apiGet(`/api/cases?group=${encodeURIComponent(state.category)}`);
    state.cases = Array.isArray(data) ? data : [];

    if (state.activeCaseId != null && !state.cases.some((item) => item.id === state.activeCaseId)) {
      state.activeCaseId = null;
      state.activeCase = null;
    }

    renderCatalog();
  }

  function renderCatalog() {
    DOM.catalog.innerHTML = "";
    const grouped = groupBySubgroup(state.cases);

    Object.entries(grouped).forEach(([subgroup, cases]) => {
      const title = document.createElement("h3");
      title.className = "subgroup-title";
      title.textContent = subgroup;
      DOM.catalog.appendChild(title);

      const grid = document.createElement("div");
      grid.className = "grid";

      cases.forEach((item) => {
        const card = document.createElement("div");
        card.className = `card status-${item.status || "NEW"}`;
        if (item.id === state.activeCaseId) card.classList.add("active");

        const prob = item.probability_text || "n/a";
        card.innerHTML = `
          <div class="card-header">
            <div class="preview-box"></div>
            <div class="card-meta">
              <div class="case-name">${caseDisplayName(item)}</div>
              <div class="case-sub">${item.case_code}</div>
              <div class="case-sub">P=${prob}</div>
            </div>
          </div>
          <div class="card-algo">${item.active_formula || "(add algorithm)"}</div>
        `;

        const preview = card.querySelector(".preview-box");
        if (item.recognizer_url) {
          const img = document.createElement("img");
          img.src = item.recognizer_url;
          img.alt = `${item.case_code} recognizer`;
          preview.appendChild(img);
        } else {
          preview.textContent = "SVG";
          preview.style.color = "#888";
          preview.style.fontSize = "0.75rem";
        }

        card.addEventListener("click", () => {
          void openCase(item.id);
        });
        grid.appendChild(card);
      });

      DOM.catalog.appendChild(grid);
    });
  }

  function currentCase() {
    return state.activeCase;
  }

  function getActiveJob(caseItem) {
    return (caseItem?.jobs || []).find((job) => job.status === "PENDING" || job.status === "RUNNING") || null;
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

  function updateModalState() {
    const c = currentCase();
    if (!c) return;

    DOM.mName.textContent = caseDisplayName(c);
    DOM.mProb.textContent = `Probability: ${c.probability_text || "n/a"}`;
    DOM.mCaseCode.textContent = c.case_code || "";

    const draftArtifact = c.artifacts?.draft || null;
    const highArtifact = c.artifacts?.high || null;
    const activeJob = getActiveJob(c);
    const videoUrl = highArtifact?.video_url || draftArtifact?.video_url || null;

    if (videoUrl) {
      setVideoSource(DOM.mVideo, videoUrl);
      DOM.mVideo.style.display = "block";
      DOM.mQueueMsg.style.display = activeJob ? "flex" : "none";
      DOM.mQueueMsg.textContent = activeJob ? `Render queued (${activeJob.quality})...` : "";
    } else {
      clearVideoSource(DOM.mVideo);
      DOM.mVideo.style.display = "none";
      DOM.mQueueMsg.style.display = "flex";
      DOM.mQueueMsg.textContent = activeJob ? `Render queued (${activeJob.quality})...` : "Video not rendered yet...";
    }

    DOM.mStatusGroup.querySelectorAll(".btn[data-status]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.status === c.status);
    });

    DOM.mRenderDraftBtn.disabled = Boolean(activeJob) || !c.active_algorithm_id;
    DOM.mRenderBtn.disabled = Boolean(activeJob) || !draftArtifact || Boolean(highArtifact) || !c.active_algorithm_id;
    DOM.mRenderBtn.textContent = highArtifact ? "HD Ready" : "Request HD Render";

    renderAlgorithmsList(c);
  }

  function renderAlgorithmsList(c) {
    DOM.mAlgoList.innerHTML = "";

    (c.algorithms || []).forEach((algo) => {
      const option = document.createElement("label");
      option.className = "algo-option";
      const checked = algo.id === c.active_algorithm_id ? "checked" : "";
      option.innerHTML = `
        <input type="radio" name="algo_sel" value="${algo.id}" ${checked}>
        <code>${algo.formula || "(empty)"}</code>
      `;
      option.querySelector("input").addEventListener("change", async () => {
        try {
          await activateAlgorithm(c.id, algo.id);
        } catch (error) {
          showToast(String(error.message || error));
        }
      });
      DOM.mAlgoList.appendChild(option);
    });

    const customRow = document.createElement("div");
    customRow.className = "algo-option custom-input";
    customRow.innerHTML = `
      <input type="text" placeholder="Or enter custom algorithm..." id="custom-formula-input">
      <button class="btn" id="custom-formula-apply">Use</button>
    `;

    const input = customRow.querySelector("#custom-formula-input");
    const applyBtn = customRow.querySelector("#custom-formula-apply");
    const submitCustom = async () => {
      const formula = String(input.value || "").trim();
      if (!formula) {
        showToast("Formula is empty");
        return;
      }
      try {
        const updated = await apiPost(`/api/cases/${c.id}/custom`, {
          formula,
          activate: true,
        });
        state.activeCase = updated;
        patchCaseInState(updated);
        renderCatalog();
        updateModalState();
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

    DOM.mAlgoList.appendChild(customRow);
  }

  async function openCase(caseId) {
    state.activeCaseId = caseId;
    const details = await apiGet(`/api/cases/${caseId}`);
    state.activeCase = details;
    patchCaseInState(details);
    renderCatalog();
    updateModalState();
    DOM.backdrop.style.display = "flex";
  }

  function closeModal() {
    DOM.backdrop.style.display = "none";
    clearVideoSource(DOM.mVideo);
  }

  async function activateAlgorithm(caseId, algorithmId) {
    const updated = await apiPost(`/api/cases/${caseId}/activate`, { algorithm_id: algorithmId });
    state.activeCase = updated;
    patchCaseInState(updated);
    renderCatalog();
    updateModalState();
    showToast("Active algorithm updated");
  }

  async function updateProgress(status) {
    const c = currentCase();
    if (!c || !c.active_algorithm_id) return;
    await apiPost("/api/progress", {
      algorithm_id: c.active_algorithm_id,
      status,
    });
    const updated = await apiGet(`/api/cases/${c.id}`);
    state.activeCase = updated;
    patchCaseInState(updated);
    renderCatalog();
    updateModalState();
  }

  async function queueRender(quality) {
    const c = currentCase();
    if (!c) return;
    const response = await apiPost(`/api/cases/${c.id}/queue`, { quality });
    if (response.reused) showToast("Reused existing render");
    else showToast("Job added to queue");

    const updated = await apiGet(`/api/cases/${c.id}`);
    state.activeCase = updated;
    patchCaseInState(updated);
    renderCatalog();
    updateModalState();
  }

  async function pollQueue() {
    const c = currentCase();
    if (!c) return;

    try {
      const status = await apiGet(`/api/queue/status?case_id=${c.id}`);
      const previousActiveJob = getActiveJob(c);
      const nextActiveJob = (status.jobs || []).find((job) => job.status === "PENDING" || job.status === "RUNNING") || null;
      const justCompleted = previousActiveJob && !nextActiveJob;

      const updated = await apiGet(`/api/cases/${c.id}`);
      state.activeCase = updated;
      patchCaseInState(updated);
      renderCatalog();
      updateModalState();

      if (justCompleted) {
        showToast("Render finished");
      }
    } catch (error) {
      console.error(error);
    }
  }

  function setupEventListeners() {
    document.querySelectorAll(".nav-tab").forEach((tab) => {
      tab.addEventListener("click", async (event) => {
        const category = String(event.target.dataset.category || "").toUpperCase();
        if (!GROUPS.includes(category)) return;

        document.querySelectorAll(".nav-tab").forEach((item) => item.classList.remove("active"));
        event.target.classList.add("active");

        state.category = category;
        state.activeCaseId = null;
        state.activeCase = null;
        await loadCatalog();
      });
    });

    DOM.mClose.addEventListener("click", closeModal);
    DOM.backdrop.addEventListener("click", (event) => {
      if (event.target === DOM.backdrop) closeModal();
    });

    DOM.mStatusGroup.querySelectorAll(".btn[data-status]").forEach((btn) => {
      btn.addEventListener("click", async (event) => {
        const status = String(event.target.dataset.status || "");
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
    setupEventListeners();
    await loadCatalog();

    if (state.pollHandle) clearInterval(state.pollHandle);
    state.pollHandle = setInterval(() => {
      void pollQueue();
    }, 5000);
  }

  void init();
})();
