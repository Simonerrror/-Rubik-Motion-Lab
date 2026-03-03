(() => {
  const body = document.body;
  const backBtn = document.getElementById("mobile-back-btn");
  const mobileTitle = document.getElementById("mobile-view-title");
  const caseTitle = document.getElementById("m-name");

  function openCatalog() {
    body.classList.remove("details-open");
  }

  function openDetails() {
    body.classList.add("details-open");
  }

  function syncTitle() {
    if (!mobileTitle || !caseTitle) return;
    const text = String(caseTitle.textContent || "").trim();
    mobileTitle.textContent = text || "Sandbox";
  }

  backBtn?.addEventListener("click", () => {
    openCatalog();
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
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      openCatalog();
    }
  });

  if (caseTitle && mobileTitle) {
    const observer = new MutationObserver(syncTitle);
    observer.observe(caseTitle, { childList: true, characterData: true, subtree: true });
  }

  syncTitle();
  openCatalog();
})();
