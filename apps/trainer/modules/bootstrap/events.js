import { GROUPS } from "../core/constants.js";

/**
 * @param {Object} deps
 */
export function bindGlobalEvents(deps) {
  const {
    state,
    dom,
    saveProgressSortMap,
    renderCatalog,
    setActiveTab,
    syncProgressSortToggle,
    loadCatalog,
    setCaseStatus,
    profileModal,
    manual,
    shell,
    sandbox,
  } = deps;

  dom.sandboxToStartBtn?.addEventListener("click", () => {
    sandbox.stopPlayback({ silent: true });
    sandbox.toStart();
  });

  dom.sandboxPrevBtn?.addEventListener("click", () => {
    sandbox.stopPlayback({ silent: true, forceUpdate: true });
    void sandbox.stepBackward();
  });

  dom.sandboxPlayPauseBtn?.addEventListener("click", () => {
    sandbox.togglePlayback();
  });

  dom.sandboxNextBtn?.addEventListener("click", () => {
    sandbox.stopPlayback({ silent: true, forceUpdate: true });
    void sandbox.stepForward();
  });

  if (dom.sandboxTimelineSlider) {
    const finishScrub = () => {
      if (!sandbox.isScrubbing()) return;
      void sandbox.finishScrubbing(dom.sandboxTimelineSlider.value);
    };

    dom.sandboxTimelineSlider.addEventListener("pointerdown", () => {
      sandbox.beginScrubbing();
    });

    dom.sandboxTimelineSlider.addEventListener("input", (event) => {
      const target = event.currentTarget;
      if (!(target instanceof HTMLInputElement)) return;
      if (!sandbox.isScrubbing()) {
        sandbox.beginScrubbing();
      }
      sandbox.queueTimelinePreview(target.value);
    });

    dom.sandboxTimelineSlider.addEventListener("change", finishScrub);
    window.addEventListener("pointerup", finishScrub);
  }

  dom.sandboxSpeedToggleBtn?.addEventListener("click", () => {
    sandbox.cyclePlaybackSpeed();
  });

  if (dom.sortProgressToggle) {
    dom.sortProgressToggle.addEventListener("change", (event) => {
      const target = event.currentTarget;
      if (!(target instanceof HTMLInputElement)) return;
      const enabled = Boolean(target.checked);
      state.progressSortByGroup[state.category] = enabled;
      saveProgressSortMap(state.progressSortByGroup);
      renderCatalog();
    });
  }

  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.addEventListener("click", async (event) => {
      const target = event.currentTarget;
      if (!(target instanceof HTMLElement)) return;
      const category = String(target.dataset.category || "").toUpperCase();
      if (!GROUPS.includes(category) || category === state.category) return;
      state.category = category;
      state.activeCaseKey = null;
      state.activeCase = null;
      setActiveTab(category);
      syncProgressSortToggle();
      await loadCatalog();
      shell.openCatalog();
    });
  });

  dom.mStatusGroup.querySelectorAll(".status-btn[data-status]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const status = String(btn.dataset.status || "");
      if (!status) return;
      setCaseStatus(status);
    });
  });

  dom.exportProfileBtn?.addEventListener("click", () => {
    void profileModal.open("export");
  });

  dom.importProfileBtn?.addEventListener("click", () => {
    void profileModal.open("import");
  });

  dom.profileApplyBtn?.addEventListener("click", () => {
    if (profileModal.mode !== "import") return;
    void profileModal.applyImported();
  });

  dom.profileCopyBtn?.addEventListener("click", () => {
    void profileModal.copyPayload();
  });

  dom.profileCloseBtn?.addEventListener("click", () => {
    profileModal.close();
  });

  dom.profileModal?.addEventListener("click", (event) => {
    if (event.target === dom.profileModal) {
      profileModal.close();
    }
  });

  dom.shellBackBtn?.addEventListener("click", () => {
    shell.openCatalog();
  });

  dom.shellSettingsBtn?.addEventListener("click", () => {
    shell.toggleSettings();
  });

  dom.settingsCloseBtn?.addEventListener("click", () => {
    shell.closeSettings();
  });

  dom.settingsBackdrop?.addEventListener("click", () => {
    shell.closeSettings();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && profileModal.isOpen()) {
      profileModal.close();
      return;
    }

    if (event.key === "Escape" && manual?.isOpen()) {
      manual.close();
      return;
    }

    if (event.key === "Escape" && shell.isSettingsOpen()) {
      shell.closeSettings();
      return;
    }

    const target = event.target;
    if (
      target instanceof HTMLElement &&
      (target.closest("input[type='text']") || target.closest("textarea") || target.isContentEditable)
    ) {
      return;
    }

    if (event.key === "?" || (event.key === "/" && event.shiftKey)) {
      event.preventDefault();
      void manual?.open();
      return;
    }

    if (event.key === "Escape" && shell.canReturnToCatalog()) {
      shell.openCatalog();
      return;
    }

    if (!state.sandboxData) return;
    if (event.repeat && event.code === "Space") return;

    if (event.code === "Space") {
      event.preventDefault();
      sandbox.togglePlayback();
      return;
    }
    if (event.code === "ArrowLeft") {
      event.preventDefault();
      sandbox.stopPlayback({ silent: true, forceUpdate: true });
      void sandbox.stepBackward();
      return;
    }
    if (event.code === "ArrowRight") {
      event.preventDefault();
      sandbox.stopPlayback({ silent: true, forceUpdate: true });
      void sandbox.stepForward();
      return;
    }
    if (event.code === "KeyR") {
      event.preventDefault();
      sandbox.stopPlayback({ silent: true, forceUpdate: true });
      sandbox.toStart();
    }
  });
}
