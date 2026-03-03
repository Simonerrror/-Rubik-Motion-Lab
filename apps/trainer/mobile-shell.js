(() => {
  const body = document.body;
  const backBtn = document.getElementById("mobile-back-btn");
  const mobileTitle = document.getElementById("mobile-view-title");
  const caseTitle = document.getElementById("m-name");
  const settingsBtn = document.getElementById("mobile-settings-btn");
  const settingsCloseBtn = document.getElementById("mobile-settings-close-btn");
  const settingsBackdrop = document.getElementById("mobile-settings-backdrop");
  const settingsSheet = document.getElementById("mobile-settings-sheet");

  function openCatalog() {
    closeSettings();
    body.classList.remove("details-open");
  }

  function openDetails() {
    body.classList.add("details-open");
    closeSettings();
  }

  function closeSettings() {
    body.classList.remove("settings-open");
    settingsSheet?.setAttribute("aria-hidden", "true");
    settingsBackdrop?.setAttribute("aria-hidden", "true");
  }

  function openSettings() {
    if (!body.classList.contains("details-open")) return;
    body.classList.add("settings-open");
    settingsSheet?.setAttribute("aria-hidden", "false");
    settingsBackdrop?.setAttribute("aria-hidden", "false");
  }

  function toggleSettings() {
    if (body.classList.contains("settings-open")) {
      closeSettings();
      return;
    }
    openSettings();
  }

  function syncTitle() {
    if (!mobileTitle || !caseTitle) return;
    const text = String(caseTitle.textContent || "").trim();
    mobileTitle.textContent = text || "Sandbox";
  }

  backBtn?.addEventListener("click", () => {
    if (body.classList.contains("settings-open")) {
      closeSettings();
      return;
    }
    openCatalog();
  });

  settingsBtn?.addEventListener("click", () => {
    toggleSettings();
  });

  settingsCloseBtn?.addEventListener("click", () => {
    closeSettings();
  });

  settingsBackdrop?.addEventListener("click", () => {
    closeSettings();
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    if (target.closest("[data-testid^='case-card-']")) {
      window.setTimeout(() => {
        syncTitle();
        openDetails();
      }, 0);
      return;
    }

    if (target.closest(".nav-tab")) {
      openCatalog();
      closeSettings();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (body.classList.contains("settings-open")) {
        closeSettings();
        return;
      }
      openCatalog();
    }
  });

  if (caseTitle && mobileTitle) {
    const observer = new MutationObserver(syncTitle);
    observer.observe(caseTitle, { childList: true, characterData: true, subtree: true });
  }

  syncTitle();
  openCatalog();
  closeSettings();
})();
