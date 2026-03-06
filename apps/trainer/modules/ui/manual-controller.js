import { MANUAL_CONTENT_URL } from "../core/constants.js";
import { sanitizeForTestId } from "../utils/common.js";

function parseManualHash() {
  const value = decodeURIComponent(String(window.location.hash || "").replace(/^#/, "").trim());
  if (!value.startsWith("manual")) {
    return null;
  }
  const [, rawSection] = value.split("/", 2);
  return {
    sectionId: rawSection || null,
  };
}

/**
 * @param {Object} deps
 */
export function createManualController(deps) {
  const { state, dom, shell, showToast } = deps;
  let contentPromise = null;
  let activeSectionId = "overview";

  function availableLanguages() {
    return ["ru", "en"];
  }

  function isOpen() {
    return Boolean(dom.manualModal && !dom.manualModal.classList.contains("hidden"));
  }

  function sectionList() {
    return Array.isArray(state.manualContent?.sections) ? state.manualContent.sections : [];
  }

  function getSection(sectionId) {
    const sections = sectionList();
    return sections.find((item) => item.id === sectionId) || sections[0] || null;
  }

  function replaceHash(sectionId) {
    const url = new URL(window.location.href);
    url.hash = sectionId ? `manual/${sectionId}` : "manual";
    window.history.replaceState({}, "", url);
  }

  function clearHash() {
    const url = new URL(window.location.href);
    url.hash = "";
    window.history.replaceState({}, "", url);
  }

  function renderSectionArticle(section, language) {
    const article = document.createElement("article");
    article.className = "manual-section";
    article.id = `manual-section-${section.id}`;
    article.setAttribute("data-section-id", section.id);
    article.setAttribute("data-testid", `help-section-${sanitizeForTestId(section.id)}`);

    const heading = document.createElement("h3");
    heading.className = "manual-section-title";
    heading.textContent = String(section.title?.[language] || section.title?.ru || section.id);
    article.appendChild(heading);

    const lead = String(section.lead?.[language] || section.lead?.ru || "").trim();
    if (lead) {
      const leadNode = document.createElement("p");
      leadNode.className = "manual-section-lead";
      leadNode.textContent = lead;
      article.appendChild(leadNode);
    }

    const items = Array.isArray(section.items?.[language]) ? section.items[language] : [];
    if (items.length) {
      const list = document.createElement("ul");
      list.className = "manual-list";
      items.forEach((item) => {
        const listItem = document.createElement("li");
        listItem.textContent = String(item);
        list.appendChild(listItem);
      });
      article.appendChild(list);
    }

    return article;
  }

  function render() {
    if (!state.manualContent || !dom.manualToc || !dom.manualContent) return;
    const language = availableLanguages().includes(state.manualLanguage) ? state.manualLanguage : "ru";

    dom.manualToc.innerHTML = "";
    dom.manualContent.innerHTML = "";

    sectionList().forEach((section) => {
      const tocButton = document.createElement("button");
      tocButton.type = "button";
      tocButton.className = "manual-toc-link";
      tocButton.setAttribute("data-section-id", section.id);
      tocButton.textContent = String(section.title?.[language] || section.title?.ru || section.id);
      tocButton.addEventListener("click", () => {
        setActiveSection(section.id, { updateHash: true, scroll: true });
      });
      dom.manualToc.appendChild(tocButton);

      dom.manualContent.appendChild(renderSectionArticle(section, language));
    });

    dom.manualLangRuBtn?.classList.toggle("active", language === "ru");
    dom.manualLangEnBtn?.classList.toggle("active", language === "en");
    setActiveSection(activeSectionId, { updateHash: false, scroll: false });
  }

  function setActiveSection(sectionId, options = {}) {
    const { updateHash = false, scroll = false } = options;
    const section = getSection(sectionId);
    if (!section) return;
    activeSectionId = section.id;

    dom.manualToc?.querySelectorAll("[data-section-id]").forEach((item) => {
      item.classList.toggle("active", item.getAttribute("data-section-id") === activeSectionId);
    });
    dom.manualContent?.querySelectorAll("[data-section-id]").forEach((item) => {
      item.classList.toggle("active", item.getAttribute("data-section-id") === activeSectionId);
    });

    if (scroll) {
      const node = dom.manualContent?.querySelector(`[data-section-id="${activeSectionId}"]`);
      node?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (updateHash && isOpen()) {
      replaceHash(activeSectionId);
    }
  }

  async function ensureContent() {
    if (state.manualContent) return state.manualContent;
    if (!contentPromise) {
      contentPromise = fetch(MANUAL_CONTENT_URL, { cache: "no-store" })
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Manual load failed (${response.status})`);
          }
          return response.json();
        })
        .then((payload) => {
          state.manualContent = payload;
          if (!availableLanguages().includes(state.manualLanguage)) {
            state.manualLanguage = String(payload.default_language || "ru");
          }
          render();
          return payload;
        })
        .catch((error) => {
          contentPromise = null;
          throw error;
        });
    }
    return contentPromise;
  }

  async function open(sectionId = null, options = {}) {
    const { updateHash = true } = options;
    try {
      await ensureContent();
      render();
      dom.manualModal?.classList.remove("hidden");
      dom.manualModal?.setAttribute("aria-hidden", "false");
      shell.setSheet("manual");
      setActiveSection(sectionId || activeSectionId, { updateHash, scroll: true });
    } catch (error) {
      showToast(String(error.message || error));
    }
  }

  function close(options = {}) {
    const { updateHash = true } = options;
    dom.manualModal?.classList.add("hidden");
    dom.manualModal?.setAttribute("aria-hidden", "true");
    if (state.sheet === "manual") {
      shell.setSheet("none");
    }
    if (updateHash && parseManualHash()) {
      clearHash();
    }
  }

  function setLanguage(language) {
    if (!availableLanguages().includes(language)) return;
    state.manualLanguage = language;
    render();
    setActiveSection(activeSectionId, { updateHash: isOpen(), scroll: false });
  }

  function syncFromHash() {
    const payload = parseManualHash();
    if (!payload) {
      if (isOpen()) {
        close({ updateHash: false });
      }
      return;
    }
    void open(payload.sectionId, { updateHash: false });
  }

  function init() {
    dom.helpOpenBtn?.addEventListener("click", () => {
      void open(activeSectionId, { updateHash: true });
    });
    dom.manualCloseBtn?.addEventListener("click", () => {
      close({ updateHash: true });
    });
    dom.manualLangRuBtn?.addEventListener("click", () => {
      setLanguage("ru");
    });
    dom.manualLangEnBtn?.addEventListener("click", () => {
      setLanguage("en");
    });
    dom.manualModal?.addEventListener("click", (event) => {
      if (event.target === dom.manualModal) {
        close({ updateHash: true });
      }
    });
    window.addEventListener("hashchange", syncFromHash);
    syncFromHash();
  }

  return {
    init,
    open,
    close,
    isOpen,
    setLanguage,
    syncFromHash,
  };
}
