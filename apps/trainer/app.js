import { CATALOG_SCHEMA_VERSION, CATALOG_URL } from "./modules/core/constants.js";
import { queryTrainerDom } from "./modules/core/dom.js";
import { createInitialState } from "./modules/core/state.js";
import { bindGlobalEvents } from "./modules/bootstrap/events.js";
import { createTrainerCatalogProvider } from "./modules/domain/catalog-provider.js";
import { exportTrainerProfile, importTrainerProfile } from "./modules/domain/profile-codec.js";
import {
  baseProfile,
  loadProfileFromStorage,
  loadProgressSortMap,
  mergeProfile,
  nextProgressStatus,
  normalizeProfile,
  saveProfile,
  saveProgressSortMap,
} from "./modules/domain/profile-storage.js";
import { getSandboxPreviewAsset } from "./modules/sandbox/preview-assets.js";
import { createSandboxController } from "./modules/sandbox/controller.js";
import {
  ensureSandboxPlayerReady,
  isSandboxRuntimeReady,
  preloadSandboxRuntime,
} from "./modules/sandbox/runtime-loader.js";
import { createSandboxStore } from "./modules/sandbox/store.js";
import { renderCategoryTabs, setActiveTab, renderCatalog, syncProgressSortToggle } from "./modules/ui/catalog-view.js";
import { createDetailsView } from "./modules/ui/details-view.js";
import { createManualController } from "./modules/ui/manual-controller.js";
import { createProfileModalController } from "./modules/ui/profile-modal-controller.js";
import { createShellController } from "./modules/ui/shell-controller.js";
import { updateSandboxOverlay } from "./modules/ui/sandbox-overlay-view.js";

const dom = queryTrainerDom(document);
const state = createInitialState(loadProgressSortMap());
const shell = createShellController({ state, dom });
let sandboxResizeBound = false;
let sandboxPreloadScheduled = false;
let sandboxLoadToken = 0;
let sandboxInteractionUnbind = null;

function showToast(message) {
  dom.toast.textContent = String(message || "");
  dom.toast.classList.add("show");
  window.clearTimeout(state._toastTimer);
  state._toastTimer = window.setTimeout(() => {
    dom.toast.classList.remove("show");
  }, 1800);
}

function currentCase() {
  return state.activeCase;
}

function normalizePreviewGroup(group) {
  const normalized = String(group || "").toUpperCase();
  const categories = catalogCategories();
  if (categories.includes(normalized)) {
    return normalized;
  }
  return categories[0] || "PLL";
}

function catalogCategories() {
  return Array.isArray(state.catalog?.categories)
    ? state.catalog.categories.map((item) => String(item || "").trim().toUpperCase()).filter(Boolean)
    : [];
}

function setSandboxPreviewGroup(group) {
  const nextGroup = normalizePreviewGroup(group);
  state.sandboxPreviewGroup = nextGroup;
  if (dom.sandboxPreviewImage) {
    const nextAsset = getSandboxPreviewAsset(nextGroup);
    if (dom.sandboxPreviewImage.getAttribute("src") !== nextAsset.src) {
      dom.sandboxPreviewImage.src = nextAsset.src;
    }
    dom.sandboxPreviewImage.srcset = nextAsset.srcset;
    dom.sandboxPreviewImage.sizes = nextAsset.sizes;
    dom.sandboxPreviewImage.dataset.group = nextGroup;
  }
}

function syncSandboxPreview(options = {}) {
  if (!dom.sandboxPreview) return;
  const visible = options.visible != null
    ? Boolean(options.visible)
    : !(state.sandboxPlayer && state.sandboxData);
  const status = String(options.status || state.sandboxRuntimeStatus || "idle");
  dom.sandboxPreview.dataset.visible = visible ? "true" : "false";
  dom.sandboxPreview.dataset.status = status;
  if (!dom.sandboxPreviewLabel) return;
  if (status === "loading") {
    dom.sandboxPreviewLabel.textContent = "Loading 3D cube...";
    return;
  }
  if (status === "error") {
    dom.sandboxPreviewLabel.textContent = "3D runtime unavailable";
    return;
  }
  dom.sandboxPreviewLabel.textContent = "";
}

function setSandboxRuntimeStatus(status, error = null) {
  state.sandboxRuntimeStatus = status;
  state.sandboxRuntimeError = error ? String(error.message || error) : null;
  syncSandboxPreview();
}

async function ensureSandboxRuntimeLoaded() {
  if (state.sandboxRuntimeStatus === "ready" && state.sandboxPlayer) {
    return state.sandboxPlayer;
  }
  if (state.sandboxRuntimePromise) {
    await state.sandboxRuntimePromise;
    if (state.sandboxPlayer) {
      return state.sandboxPlayer;
    }
  }
  const loadPromise = (async () => {
    setSandboxRuntimeStatus("loading");
    const player = await ensureSandboxPlayerReady(dom.sandboxCanvas);
    if (!state.sandboxPlayer) {
      state.sandboxPlayer = player;
    }
    if (!sandboxResizeBound) {
      sandboxResizeBound = true;
      window.addEventListener("resize", () => {
        state.sandboxPlayer?.resize?.();
      });
    }
    setSandboxRuntimeStatus("ready");
    return state.sandboxPlayer;
  })()
    .catch((error) => {
      setSandboxRuntimeStatus("error", error);
      throw error;
    })
    .finally(() => {
      state.sandboxRuntimePromise = null;
    });
  state.sandboxRuntimePromise = loadPromise.then(() => undefined);
  return loadPromise;
}

function clearSandboxInteractionPreload() {
  if (typeof sandboxInteractionUnbind === "function") {
    sandboxInteractionUnbind();
    sandboxInteractionUnbind = null;
  }
}

function startSandboxRuntimePreload() {
  clearSandboxInteractionPreload();
  sandboxPreloadScheduled = false;
  if (state.sandboxRuntimeStatus === "ready" || state.sandboxRuntimePromise) {
    return;
  }
  const promise = (async () => {
    setSandboxRuntimeStatus("loading");
    await preloadSandboxRuntime();
    setSandboxRuntimeStatus("ready");
  })()
    .catch((error) => {
      setSandboxRuntimeStatus("error", error);
      showToast(`3D runtime unavailable: ${String(error.message || error)}`);
    })
    .finally(() => {
      state.sandboxRuntimePromise = null;
    });
  state.sandboxRuntimePromise = promise.then(() => undefined);
  void promise.then(async () => {
    if (!currentCase() || !isSandboxRuntimeReady()) {
      syncSandboxPreview();
      return;
    }
    await loadSandboxForCurrentCase();
  });
}

function bindSandboxInteractionPreload() {
  if (sandboxInteractionUnbind || state.sandboxRuntimeStatus === "ready" || state.sandboxRuntimePromise) {
    return;
  }
  const trigger = () => {
    startSandboxRuntimePreload();
  };
  const frame = dom.sandboxFrame;
  if (!frame) return;
  const events = ["pointerdown", "touchstart"];
  events.forEach((eventName) => {
    frame.addEventListener(eventName, trigger, { passive: true, once: true });
  });
  sandboxInteractionUnbind = () => {
    events.forEach((eventName) => {
      frame.removeEventListener(eventName, trigger);
    });
  };
}

function scheduleSandboxRuntimePreload() {
  if (sandboxPreloadScheduled || state.sandboxRuntimeStatus === "ready" || state.sandboxRuntimePromise) {
    return;
  }
  if (state.layout === "mobile") {
    bindSandboxInteractionPreload();
    return;
  }
  sandboxPreloadScheduled = true;
  const start = () => {
    startSandboxRuntimePreload();
  };
  if (typeof window.requestIdleCallback === "function") {
    window.requestIdleCallback(() => start(), { timeout: 1200 });
    return;
  }
  window.setTimeout(start, 120);
}

function refreshCaseCache() {
  if (!state.provider) {
    state.cases = [];
    state.activeCase = null;
    state.activeCaseKey = null;
    return;
  }

  state.cases = state.provider.listCases(state.category);
  if (!state.cases.length) {
    state.activeCaseKey = null;
    state.activeCase = null;
    return;
  }

  if (!state.activeCaseKey || !state.cases.some((item) => item.case_key === state.activeCaseKey)) {
    state.activeCaseKey = state.cases[0].case_key;
  }

  state.activeCase = state.provider.getCase(state.activeCaseKey);
}

async function loadCatalogPayload() {
  const response = await fetch(CATALOG_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Catalog load failed (${response.status})`);
  }
  const payload = await response.json();
  if (!payload || payload.schema_version !== CATALOG_SCHEMA_VERSION) {
    throw new Error("Invalid trainer catalog schema");
  }
  if (!Array.isArray(payload.cases)) {
    throw new Error("Catalog cases must be an array");
  }
  if (!Array.isArray(payload.categories)) {
    throw new Error("Catalog categories must be an array");
  }
  return payload;
}

let detailsView = null;
let sandbox = null;
let profileModal = null;
let manualController = null;

function shouldDeferCatalogRender() {
  return state.layout === "mobile" && state.view === "details";
}

function renderCatalogUI(options = {}) {
  if (!options.force && shouldDeferCatalogRender()) {
    return;
  }
  renderCatalog({
    state,
    dom,
    onSelectCase: selectCase,
    onCycleStatus: updateCatalogCaseProgress,
  });
}

function openCatalogView() {
  renderCatalogUI({ force: true });
  shell.openCatalog();
}

async function loadSandboxForCurrentCase() {
  const token = ++sandboxLoadToken;
  sandbox.hardResetOnSwitch({ clearData: true });
  const c = currentCase();
  if (!c?.case_key || !state.provider) {
    syncSandboxPreview({ visible: true });
    return;
  }

  try {
    syncSandboxPreview({ visible: true, status: "loading" });
    await ensureSandboxRuntimeLoaded();
    if (token !== sandboxLoadToken) {
      return;
    }
    const liveCase = currentCase();
    if (!liveCase?.case_key || liveCase.case_key !== c.case_key) {
      return;
    }
    const timeline = state.provider.getSandboxTimeline(c.case_key, c.active_algorithm_id);
    sandbox.loadTimeline(timeline, c.active_formula || "");
    syncSandboxPreview({ visible: false, status: "ready" });
  } catch (error) {
    if (token !== sandboxLoadToken) {
      return;
    }
    sandbox.resetSandboxData();
    syncSandboxPreview({ visible: true, status: "error" });
    showToast(`Sandbox unavailable: ${String(error.message || error)}`);
  }
}

async function updateCatalogCaseProgress(caseKey, currentStatus) {
  if (!state.provider) return;
  const nextStatus = nextProgressStatus(currentStatus);
  state.provider.setCaseProgress(caseKey, nextStatus);
  refreshCaseCache();
  renderCatalogUI();
  detailsView.updateDetailsPaneState();
  shell.syncTitle();
}

async function selectCase(caseKey) {
  if (!state.provider) return;
  sandbox.hardResetOnSwitch({ clearData: true });
  state.activeCaseKey = caseKey;
  state.activeCase = state.provider.getCase(caseKey);
  state.activeDisplayMode = "algorithm";
  state.activeDisplayFormula = state.activeCase?.active_formula || "";
  await loadSandboxForCurrentCase();
  refreshCaseCache();
  renderCatalogUI();
  detailsView.updateDetailsPaneState();
  shell.openDetails();
}

function setCaseStatus(status) {
  const c = currentCase();
  if (!c || !state.provider) return;
  state.provider.setCaseProgress(c.case_key, status);
  refreshCaseCache();
  renderCatalogUI();
  detailsView.updateDetailsPaneState();
  shell.syncTitle();
}

async function loadCatalog() {
  setSandboxPreviewGroup(state.category);
  refreshCaseCache();
  if (!state.cases.length) {
    detailsView.setDetailsDisabled();
    sandbox.resetSandboxData();
    renderCatalogUI();
    syncSandboxPreview({ visible: true });
    openCatalogView();
    return;
  }

  if (!state.activeCaseKey || !state.cases.some((item) => item.case_key === state.activeCaseKey)) {
    state.activeCaseKey = state.cases[0].case_key;
  }

  state.activeCase = state.provider.getCase(state.activeCaseKey);
  refreshCaseCache();
  renderCatalogUI();
  detailsView.updateDetailsPaneState();
  shell.syncLayout();
  shell.syncTitle();
  if (state.sandboxRuntimeStatus === "ready" && isSandboxRuntimeReady()) {
    await loadSandboxForCurrentCase();
    return;
  }
  sandbox.resetSandboxData();
  syncSandboxPreview({ visible: true });
}

async function init() {
  try {
    shell.init();

    state.catalog = await loadCatalogPayload();
    if (catalogCategories().includes(state.category)) {
      state.category = String(state.category);
    } else {
      state.category = catalogCategories()[0] || "PLL";
    }
    renderCategoryTabs(dom, state.catalog, state.category);
    setSandboxPreviewGroup(state.category);
    syncSandboxPreview({ visible: true });

    const initialProfile = loadProfileFromStorage();
    state.provider = createTrainerCatalogProvider(
      state.catalog,
      initialProfile,
      (nextProfile) => {
        state.profile = normalizeProfile(nextProfile);
        saveProfile(state.profile);
      },
      state.customTimelineCache
    );
    state.profile = state.provider.getProfile();

    const sandboxStore = createSandboxStore();
    state.sandboxStore = sandboxStore;
    state.sandboxMachineState = sandboxStore.getState().playbackMode.toUpperCase();

    detailsView = createDetailsView({
      state,
      dom,
      showToast,
      getCurrentCase: currentCase,
      updateSandboxOverlay: (caseItem) => updateSandboxOverlay(dom, state, caseItem),
      onGoToStep: (stepIndex) => {
        sandbox.stopPlayback({ silent: true, forceUpdate: true });
        sandbox.setStep(stepIndex);
      },
      onSelectAlgorithm: async (algorithmId) => {
        const c = currentCase();
        if (!c) return;
        sandbox.hardResetOnSwitch({ clearData: true });
        state.provider.setActiveAlgorithm(c.case_key, algorithmId);
        refreshCaseCache();
        state.activeCase = state.provider.getCase(c.case_key);
        detailsView.setActiveDisplayFormula(state.activeCase?.active_formula || "", "algorithm");
        await loadSandboxForCurrentCase();
        renderCatalogUI();
        detailsView.updateDetailsPaneState();
        showToast("Active algorithm updated");
      },
      onDeleteAlgorithm: async (algorithmId) => {
        const c = currentCase();
        if (!c) return;
        sandbox.hardResetOnSwitch({ clearData: true });
        const payload = state.provider.deleteAlgorithm(c.case_key, algorithmId);
        if (!payload.deleted) {
          showToast("Only custom algorithms can be deleted");
          return;
        }
        refreshCaseCache();
        state.activeCase = state.provider.getCase(c.case_key);
        await loadSandboxForCurrentCase();
        renderCatalogUI();
        detailsView.updateDetailsPaneState();
        showToast("Algorithm deleted");
      },
      onApplyCustomFormula: async (formula) => {
        const c = currentCase();
        if (!c) return;
        sandbox.hardResetOnSwitch({ clearData: true });
        const result = state.provider.createCustomAlgorithm(c.case_key, formula, "", true);
        refreshCaseCache();
        state.activeCase = state.provider.getCase(c.case_key);
        detailsView.setActiveDisplayFormula(result.algorithm?.formula || formula, "algorithm");
        await loadSandboxForCurrentCase();
        renderCatalogUI();
        detailsView.updateDetailsPaneState();
      },
    });

    sandbox = createSandboxController({
      state,
      dom,
      store: sandboxStore,
      onRenderActiveAlgorithmDisplay: (formula) => {
        detailsView.renderActiveAlgorithmDisplay(formula);
      },
      onUpdateActiveAlgorithmStepHighlight: (activeStep) => {
        detailsView.updateActiveAlgorithmStepHighlight(activeStep);
      },
    });

    profileModal = createProfileModalController({
      dom,
      exportTrainerProfile,
      importTrainerProfile,
      mergeProfile,
      baseProfile,
      getProfile: () => state.provider?.getProfile() || state.profile || baseProfile(),
      applyProfile: async (mergedProfile) => {
        state.provider.replaceProfile(mergedProfile);
        state.profile = state.provider.getProfile();
        state.customTimelineCache.clear();
        refreshCaseCache();
        await loadCatalog();
      },
      showToast,
    });

    manualController = createManualController({
      state,
      dom,
      shell,
      showToast,
    });
    manualController.init();

    setActiveTab(state.category);
    bindGlobalEvents({
      state,
      dom,
      saveProgressSortMap,
      renderCatalog: renderCatalogUI,
      openCatalogView,
      setActiveTab,
      syncProgressSortToggle: () => syncProgressSortToggle(state, dom),
      loadCatalog,
      setCaseStatus,
      profileModal,
      manual: manualController,
      shell,
      sandbox,
    });

    window.addEventListener("resize", () => {
      if (state.layout !== "mobile") {
        scheduleSandboxRuntimePreload();
      }
    });

    sandbox.updateSandboxControls();
    syncProgressSortToggle(state, dom);
    await loadCatalog();
    scheduleSandboxRuntimePreload();
  } catch (error) {
    showToast(String(error.message || error));
    console.error(error);
    detailsView?.setDetailsDisabled?.();
    dom.catalog.innerHTML = '<div class="catalog-empty">Catalog unavailable. Run trainer build first.</div>';
  }
}

void init();
