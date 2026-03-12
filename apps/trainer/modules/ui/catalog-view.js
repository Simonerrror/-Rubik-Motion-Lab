import { STATUS_SORT_RANK } from "../core/constants.js";
import { sanitizeForTestId } from "../utils/common.js";
import { appendRecognizerPreview, tileTitle } from "./sandbox-overlay-view.js";

function groupBySubgroup(items) {
  return items.reduce((acc, item) => {
    const key = item.subgroup_title || `${item.group} Cases`;
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});
}

function caseSortRank(item) {
  const status = String(item?.status || "NEW");
  return STATUS_SORT_RANK[status] ?? 1;
}

function sortCasesForCatalog(cases, state) {
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

function appendCatalogCard(grid, item, state, onSelectCase, onCycleStatus) {
  const card = document.createElement("article");
  card.className = "catalog-card";
  card.setAttribute("data-testid", `case-card-${sanitizeForTestId(item.case_key)}`);
  if (item.case_key === state.activeCaseKey) card.classList.add("active");

  const status = String(item.status || "NEW");
  card.innerHTML = `
    <button class="status-dot ${status}" type="button" title="Cycle status" aria-label="Cycle status"></button>
    <div class="catalog-preview"></div>
    <div class="tile-title">${tileTitle(item)}</div>
  `;

  const preview = card.querySelector(".catalog-preview");
  appendRecognizerPreview(preview, item, {
    loading: state.layout === "mobile" ? "lazy" : "eager",
    fetchPriority: state.layout === "mobile" ? "low" : "auto",
  });

  const statusDot = card.querySelector(".status-dot");
  if (statusDot) {
    statusDot.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      void onCycleStatus(item.case_key, item.status);
    });
  }

  card.addEventListener("click", () => {
    void onSelectCase(item.case_key);
  });

  grid.appendChild(card);
}

export function setActiveTab(category) {
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.classList.toggle("active", String(tab.dataset.category || "").toUpperCase() === category);
  });
}

export function syncProgressSortToggle(state, dom) {
  if (!dom.sortProgressToggle) return;
  dom.sortProgressToggle.checked = Boolean(state.progressSortByGroup[state.category]);
}

export function renderCatalog({ state, dom, onSelectCase, onCycleStatus }) {
  dom.catalog.innerHTML = "";
  if (!state.cases.length) {
    const empty = document.createElement("div");
    empty.className = "catalog-empty";
    empty.textContent = "No cases in this group.";
    dom.catalog.appendChild(empty);
    return;
  }

  if (state.progressSortByGroup[state.category]) {
    const grid = document.createElement("div");
    grid.className = "catalog-grid";
    sortCasesForCatalog(state.cases, state).forEach((item) => {
      appendCatalogCard(grid, item, state, onSelectCase, onCycleStatus);
    });
    dom.catalog.appendChild(grid);
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

    sortCasesForCatalog(cases, state).forEach((item) => {
      appendCatalogCard(grid, item, state, onSelectCase, onCycleStatus);
    });

    section.appendChild(grid);
    dom.catalog.appendChild(section);
  });
}
