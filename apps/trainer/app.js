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
import { createSandboxController } from "./modules/sandbox/controller.js";
import { createSandboxMachine } from "./modules/sandbox/machine.js";
import { setActiveTab, renderCatalog, syncProgressSortToggle } from "./modules/ui/catalog-view.js";
import { createDetailsView } from "./modules/ui/details-view.js";
import { createProfileModalController } from "./modules/ui/profile-modal-controller.js";
import { updateSandboxOverlay } from "./modules/ui/sandbox-overlay-view.js";

const dom = queryTrainerDom(document);
const state = createInitialState(loadProgressSortMap());

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

function renderCatalogUI() {
  renderCatalog({
    state,
    dom,
    onSelectCase: selectCase,
    onCycleStatus: updateCatalogCaseProgress,
  });
}

async function loadSandboxForCurrentCase() {
  sandbox.hardResetOnSwitch({ clearData: true });
  const c = currentCase();
  if (!c?.case_key || !state.provider) {
    return;
  }

  try {
    const timeline = state.provider.getSandboxTimeline(c.case_key, c.active_algorithm_id);
    sandbox.loadTimeline(timeline, c.active_formula || "");
  } catch (error) {
    sandbox.resetSandboxData();
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
}

function setCaseStatus(status) {
  const c = currentCase();
  if (!c || !state.provider) return;
  state.provider.setCaseProgress(c.case_key, status);
  refreshCaseCache();
  renderCatalogUI();
  detailsView.updateDetailsPaneState();
}

async function loadCatalog() {
  refreshCaseCache();
  if (!state.cases.length) {
    detailsView.setDetailsDisabled();
    sandbox.resetSandboxData();
    renderCatalogUI();
    return;
  }

  if (!state.activeCaseKey || !state.cases.some((item) => item.case_key === state.activeCaseKey)) {
    state.activeCaseKey = state.cases[0].case_key;
  }

  state.activeCase = state.provider.getCase(state.activeCaseKey);
  await loadSandboxForCurrentCase();
  refreshCaseCache();
  renderCatalogUI();
  detailsView.updateDetailsPaneState();
}

async function init() {
  try {
    if (window.CubeSandbox3D?.createSandbox3D && dom.sandboxCanvas) {
      state.sandboxPlayer = window.CubeSandbox3D.createSandbox3D(dom.sandboxCanvas);
      window.addEventListener("resize", () => {
        state.sandboxPlayer?.resize();
      });
    }

    state.catalog = await loadCatalogPayload();
    if (state.catalog.categories.includes(state.category)) {
      state.category = String(state.category);
    } else {
      state.category = state.catalog.categories[0] || "PLL";
    }

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

    const machine = createSandboxMachine("IDLE", ({ next }) => {
      state.sandboxMachineState = next;
    });
    state.sandboxMachineState = machine.getState();

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
      machine,
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

    setActiveTab(state.category);
    bindGlobalEvents({
      state,
      dom,
      saveProgressSortMap,
      renderCatalog: renderCatalogUI,
      setActiveTab,
      syncProgressSortToggle: () => syncProgressSortToggle(state, dom),
      loadCatalog,
      setCaseStatus,
      profileModal,
      sandbox,
    });

    sandbox.updateSandboxControls();
    syncProgressSortToggle(state, dom);
    await loadCatalog();
  } catch (error) {
    showToast(String(error.message || error));
    console.error(error);
    detailsView?.setDetailsDisabled?.();
    dom.catalog.innerHTML = '<div class="catalog-empty">Catalog unavailable. Run trainer build first.</div>';
  }
}

void init();
