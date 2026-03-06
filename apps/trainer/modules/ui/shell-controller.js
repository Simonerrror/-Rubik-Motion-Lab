import { DESKTOP_LAYOUT_MIN_WIDTH, MOBILE_LAYOUT_MAX_WIDTH } from "../core/constants.js";

function parseLayoutPreference() {
  const params = new URLSearchParams(window.location.search);
  const raw = String(params.get("layout") || "auto").trim().toLowerCase();
  if (raw === "desktop" || raw === "mobile") {
    return raw;
  }
  return "auto";
}

function resolveLayout(layoutPreference, viewportWidth) {
  if (layoutPreference === "desktop" || layoutPreference === "mobile") {
    return layoutPreference;
  }
  if (viewportWidth <= MOBILE_LAYOUT_MAX_WIDTH) {
    return "mobile";
  }
  if (viewportWidth >= DESKTOP_LAYOUT_MIN_WIDTH) {
    return "desktop";
  }
  return "tablet";
}

/**
 * @param {Object} deps
 */
export function createShellController(deps) {
  const { state, dom } = deps;

  function syncTitle() {
    if (!dom.shellViewTitle) return;
    const caseTitle = String(dom.mName?.textContent || "").trim();
    if (state.layout === "mobile" && state.view === "details") {
      dom.shellViewTitle.textContent = caseTitle || "Case Details";
      return;
    }
    dom.shellViewTitle.textContent = `${state.category} Catalog`;
  }

  function applyShellState() {
    if (!dom.shellRoot) return;
    dom.shellRoot.dataset.layout = state.layout;
    dom.shellRoot.dataset.view = state.view;
    dom.shellRoot.dataset.sheet = state.sheet;
    dom.shellRoot.dataset.layoutPreference = state.layoutPreference;

    if (dom.detailsPane) {
      const isHidden = state.layout === "mobile" && state.view !== "details";
      dom.detailsPane.setAttribute("aria-hidden", isHidden ? "true" : "false");
    }
    if (dom.sidebar) {
      const isHidden = state.layout === "mobile" && state.view !== "catalog";
      dom.sidebar.setAttribute("aria-hidden", isHidden ? "true" : "false");
    }
    if (dom.shellBackBtn) {
      dom.shellBackBtn.hidden = !(state.layout === "mobile" && state.view === "details" && state.sheet === "none");
    }
    if (dom.shellSettingsBtn) {
      dom.shellSettingsBtn.hidden = state.layout !== "mobile" || state.view !== "details";
      dom.shellSettingsBtn.setAttribute("aria-expanded", state.sheet === "settings" ? "true" : "false");
    }
    if (dom.settingsBackdrop) {
      dom.settingsBackdrop.setAttribute("aria-hidden", state.sheet === "settings" ? "false" : "true");
    }
    syncTitle();
  }

  function syncLayout() {
    const nextLayout = resolveLayout(state.layoutPreference, window.innerWidth);
    if (state.layout !== nextLayout) {
      state.layout = nextLayout;
      if (state.layout !== "mobile" && state.sheet === "settings") {
        state.sheet = "none";
      }
      if (state.layout !== "mobile") {
        state.view = "details";
      } else if (!state.activeCase && state.view === "details") {
        state.view = "catalog";
      }
    }
    applyShellState();
  }

  function setView(nextView) {
    state.view = nextView;
    if (nextView === "catalog" || (state.layout !== "mobile" && state.sheet === "settings")) {
      state.sheet = "none";
    }
    applyShellState();
  }

  function setSheet(nextSheet) {
    state.sheet = nextSheet;
    applyShellState();
  }

  function openCatalog() {
    setView("catalog");
  }

  function openDetails() {
    state.view = "details";
    if (state.sheet === "settings") {
      state.sheet = "none";
    }
    applyShellState();
  }

  function closeSettings() {
    if (state.sheet !== "settings") return;
    state.sheet = "none";
    applyShellState();
  }

  function toggleSettings() {
    if (state.layout !== "mobile" || state.view !== "details") return;
    state.sheet = state.sheet === "settings" ? "none" : "settings";
    applyShellState();
  }

  function canReturnToCatalog() {
    return state.layout === "mobile" && state.view === "details" && state.sheet === "none";
  }

  function init() {
    state.layoutPreference = parseLayoutPreference();
    state.layout = resolveLayout(state.layoutPreference, window.innerWidth);
    state.view = state.layout === "mobile" && !state.activeCase ? "catalog" : "details";
    state.sheet = "none";
    applyShellState();
    window.addEventListener("resize", syncLayout);
  }

  return {
    init,
    syncLayout,
    syncTitle,
    setView,
    setSheet,
    openCatalog,
    openDetails,
    closeSettings,
    toggleSettings,
    canReturnToCatalog,
    isSettingsOpen: () => state.sheet === "settings",
  };
}
